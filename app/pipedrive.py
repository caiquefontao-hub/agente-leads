"""Leitura do Pipedrive (API v1) com o token do usuário dedicado do agente.

A única escrita é atualizar_motivo_perda, chamada pelo código de aprovação,
nunca diretamente pelo modelo.
"""
import html
import json
import re

import httpx

from .config import cfg
from .motivos import MOTIVOS_PADRAO

BASE = "https://api.pipedrive.com/v1"
LIMITE_TEXTO = 4_000


def _limpar_html(texto: str | None) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.I)
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = html.unescape(texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return texto[:LIMITE_TEXTO] + ("…" if len(texto) > LIMITE_TEXTO else "")


def _get(caminho: str, params: dict | None = None) -> dict:
    params = {**(params or {}), "api_token": cfg.PIPEDRIVE_TOKEN}
    with httpx.Client(timeout=30) as cliente:
        r = cliente.get(f"{BASE}{caminho}", params=params)
    if r.status_code >= 400:
        return {"erro": f"Pipedrive respondeu {r.status_code}", "detalhe": r.text[:500]}
    return r.json()


def link_deal(deal_id: int) -> str:
    return f"https://{cfg.PIPEDRIVE_EMPRESA}.pipedrive.com/deal/{deal_id}"


def buscar_deals(termo: str, status: str | None = None, limite: int = 10) -> str:
    params = {"term": termo, "limit": min(limite, 50)}
    if status in ("open", "won", "lost"):
        params["status"] = status
    dados = _get("/deals/search", params)
    if "erro" in dados:
        return json.dumps(dados, ensure_ascii=False)
    itens = []
    for item in (dados.get("data") or {}).get("items", []):
        d = item.get("item") or {}
        itens.append({
            "deal_id": d.get("id"),
            "titulo": d.get("title"),
            "status": d.get("status"),
            "valor": d.get("value"),
            "etapa": (d.get("stage") or {}).get("name"),
            "organizacao": (d.get("organization") or {}).get("name"),
            "pessoa": (d.get("person") or {}).get("name"),
            "dono": (d.get("owner") or {}).get("name") if isinstance(d.get("owner"), dict) else None,
            "link": link_deal(d.get("id")) if d.get("id") else None,
        })
    return json.dumps({"deals": itens}, ensure_ascii=False)


_CAMPOS_DEAL = (
    "id", "title", "status", "value", "currency", "add_time", "update_time", "stage_change_time",
    "won_time", "lost_time", "close_time", "expected_close_date", "lost_reason", "pipeline_id",
    "stage_id", "probability", "next_activity_date", "next_activity_subject", "last_activity_date",
    "last_incoming_mail_time", "last_outgoing_mail_time", "notes_count", "activities_count",
    "done_activities_count", "email_messages_count", "origin", "label",
)


def obter_deal(deal_id: int) -> str:
    dados = _get(f"/deals/{deal_id}")
    if "erro" in dados:
        return json.dumps(dados, ensure_ascii=False)
    d = dados.get("data") or {}
    saida = {k: d.get(k) for k in _CAMPOS_DEAL}
    saida["organizacao"] = (d.get("org_id") or {}).get("name") if isinstance(d.get("org_id"), dict) else d.get("org_name")
    saida["pessoa"] = (d.get("person_id") or {}).get("name") if isinstance(d.get("person_id"), dict) else d.get("person_name")
    saida["dono"] = (d.get("user_id") or {}).get("name") if isinstance(d.get("user_id"), dict) else d.get("owner_name")
    saida["link"] = link_deal(deal_id)
    # campos personalizados vêm com chave hash; os nomes estão no prompt
    personalizados = {k: v for k, v in d.items() if re.fullmatch(r"[0-9a-f]{40}", k) and v not in (None, "")}
    saida["campos_personalizados"] = personalizados
    return json.dumps(saida, ensure_ascii=False, default=str)


def notas_do_deal(deal_id: int, limite: int = 10) -> str:
    dados = _get("/notes", {"deal_id": deal_id, "limit": min(limite, 50), "sort": "add_time DESC"})
    if "erro" in dados:
        return json.dumps(dados, ensure_ascii=False)
    notas = []
    for n in dados.get("data") or []:
        conteudo = _limpar_html(n.get("content"))
        if conteudo.startswith("Como foi sua reunião com"):
            continue  # pedido automático de feedback do Meetime
        notas.append({
            "data": n.get("add_time"),
            "autor": (n.get("user") or {}).get("name"),
            "fixada": bool(n.get("pinned_to_deal_flag")),
            "conteudo": conteudo,
        })
    return json.dumps({"notas": notas}, ensure_ascii=False)


def atividades_do_deal(deal_id: int, limite: int = 20) -> str:
    dados = _get(f"/deals/{deal_id}/activities", {"limit": min(limite, 100)})
    if "erro" in dados:
        return json.dumps(dados, ensure_ascii=False)
    itens = [{
        "tipo": a.get("type"),
        "assunto": a.get("subject"),
        "feita": a.get("done"),
        "data": a.get("due_date"),
        "responsavel": a.get("owner_name"),
        "nota": _limpar_html(a.get("note"))[:800],
    } for a in dados.get("data") or []]
    return json.dumps({"atividades": itens}, ensure_ascii=False)


def emails_do_deal(deal_id: int, limite: int = 10) -> str:
    dados = _get(f"/deals/{deal_id}/mailMessages", {"limit": min(limite, 50)})
    if "erro" in dados:
        return json.dumps(dados, ensure_ascii=False)
    itens = []
    for e in dados.get("data") or []:
        m = e.get("data") or {}
        itens.append({
            "assunto": m.get("subject"),
            "data": m.get("message_time"),
            "de": ", ".join(p.get("email_address", "") for p in m.get("from") or []),
            "resumo": (m.get("snippet") or "")[:500],
        })
    return json.dumps({"emails": itens}, ensure_ascii=False)


def atualizar_motivo_perda(deal_id: int, motivo: str) -> dict:
    """Única escrita permitida. Chamada só depois da aprovação."""
    if motivo not in MOTIVOS_PADRAO:
        return {"ok": False, "erro": "Motivo fora da lista padrão"}
    with httpx.Client(timeout=30) as cliente:
        r = cliente.put(f"{BASE}/deals/{deal_id}", params={"api_token": cfg.PIPEDRIVE_TOKEN},
                        json={"lost_reason": motivo})
    if r.status_code >= 400:
        return {"ok": False, "erro": f"Pipedrive respondeu {r.status_code}"}
    return {"ok": True}
