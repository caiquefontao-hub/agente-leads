"""Integração com o Microsoft Teams.

Entrada: webhook de saída (Outgoing Webhook) do Teams. O Teams envia um POST
quando alguém menciona o webhook num canal e espera resposta em até 5 segundos.
Saída: fluxo do Power Automate que responde na thread como "Flow bot".
"""
import base64
import hashlib
import hmac
import html
import re

import httpx
import markdown as md

from .config import cfg

LIMITE_MENSAGEM = 25_000  # o Teams aceita cerca de 28 KB por mensagem


def assinatura_valida(corpo: bytes, cabecalho_auth: str | None, token_b64: str) -> bool:
    """Confere o HMAC-SHA256 enviado pelo Teams no cabeçalho Authorization."""
    if not cabecalho_auth or not token_b64:
        return False
    partes = cabecalho_auth.split(" ", 1)
    if len(partes) != 2 or partes[0] != "HMAC":
        return False
    try:
        chave = base64.b64decode(token_b64)
    except Exception:
        return False
    esperado = base64.b64encode(hmac.new(chave, corpo, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(esperado, partes[1].strip())


def texto_da_mensagem(payload: dict) -> str:
    """Tira a menção <at>...</at>, as tags HTML e os espaços extras."""
    bruto = payload.get("text") or ""
    sem_mencao = re.sub(r"<at>.*?</at>", " ", bruto, flags=re.S)
    sem_tags = re.sub(r"<[^>]+>", " ", sem_mencao)
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def ids_da_conversa(payload: dict) -> dict:
    """Extrai canal, mensagem raiz da thread e autor."""
    conversa = (payload.get("conversation") or {}).get("id", "")
    canal, _, resto = conversa.partition(";")
    m = re.search(r"messageid=(\d+)", resto)
    mensagem_raiz = m.group(1) if m else (payload.get("id") or "")
    dados_canal = payload.get("channelData") or {}
    canal_id = (dados_canal.get("channel") or {}).get("id") or dados_canal.get("teamsChannelId") or canal
    autor = payload.get("from") or {}
    return {
        "thread": f"{canal_id};{mensagem_raiz}",
        "canal_id": canal_id,
        "mensagem_id": mensagem_raiz,
        "autor_nome": autor.get("name", ""),
        "autor_aad": autor.get("aadObjectId", ""),
    }


def resposta_imediata(texto: str) -> dict:
    """Formato que o webhook de saída aceita como resposta síncrona."""
    return {"type": "message", "text": texto}


def markdown_para_html(texto: str) -> str:
    corpo = md.markdown(texto, extensions=["tables", "sane_lists"])
    if len(corpo) > LIMITE_MENSAGEM:
        corpo = corpo[:LIMITE_MENSAGEM] + "<p><em>(resposta cortada pelo limite do Teams)</em></p>"
    return corpo


def responder_na_thread(canal_id: str, mensagem_id: str, texto_markdown: str) -> None:
    """Envia a resposta ao Power Automate, que posta na thread do canal."""
    if not cfg.POWER_AUTOMATE_URL:
        raise RuntimeError("POWER_AUTOMATE_URL não configurada")
    corpo = {
        "canal_id": canal_id,
        "mensagem_id": mensagem_id,
        "html": markdown_para_html(texto_markdown),
    }
    with httpx.Client(timeout=30) as cliente:
        r = cliente.post(cfg.POWER_AUTOMATE_URL, json=corpo)
        r.raise_for_status()
