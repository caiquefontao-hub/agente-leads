"""Loop do agente: Claude decide quais ferramentas usar até ter a resposta."""
import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from . import banco, estado, pipedrive
from .config import cfg
from .motivos import MOTIVOS_PADRAO

log = logging.getLogger("agente")
PASTA_PROMPT = Path(__file__).resolve().parent.parent / "prompt"
MAX_PROPOSTAS_POR_THREAD = 20

FERRAMENTAS = [
    {
        "name": "consultar_banco",
        "description": (
            "Executa UMA consulta SQL somente leitura (SELECT ou WITH) no Postgres de integrações, "
            "schema `integrations`. Devolve até 200 linhas em JSON. Use para contagens, funil, "
            "motivos de perda agregados, CAC, investimento e listas de deals. Sempre agregue no SQL "
            "em vez de trazer linhas brutas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "Consulta SELECT/WITH, schema integrations."},
                "objetivo": {"type": "string", "description": "Em poucas palavras, o que esta consulta responde."},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "pipedrive_buscar_deals",
        "description": "Busca deals no Pipedrive ao vivo por nome, organização, pessoa, e-mail ou texto das notas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "won", "lost"]},
                "limite": {"type": "integer", "default": 10},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "pipedrive_deal",
        "description": "Detalhes atuais de um deal: status, etapa, valores, datas, motivo de perda, contagens e campos personalizados.",
        "input_schema": {"type": "object", "properties": {"deal_id": {"type": "integer"}}, "required": ["deal_id"]},
    },
    {
        "name": "pipedrive_notas",
        "description": "Notas de um deal, mais recentes primeiro. Inclui a nota de handoff do Meetime (origem, SDR, qualificação).",
        "input_schema": {
            "type": "object",
            "properties": {"deal_id": {"type": "integer"}, "limite": {"type": "integer", "default": 10}},
            "required": ["deal_id"],
        },
    },
    {
        "name": "pipedrive_atividades",
        "description": "Atividades de um deal (ligações, reuniões, tarefas), feitas e pendentes.",
        "input_schema": {
            "type": "object",
            "properties": {"deal_id": {"type": "integer"}, "limite": {"type": "integer", "default": 20}},
            "required": ["deal_id"],
        },
    },
    {
        "name": "pipedrive_emails",
        "description": "E-mails ligados a um deal (assunto, data, remetente e trecho).",
        "input_schema": {
            "type": "object",
            "properties": {"deal_id": {"type": "integer"}, "limite": {"type": "integer", "default": 10}},
            "required": ["deal_id"],
        },
    },
    {
        "name": "propor_correcao_motivo_perda",
        "description": (
            "Registra uma PROPOSTA de correção do motivo de perda de um deal perdido. NÃO altera nada: "
            "a alteração só acontece se um aprovador responder 'aprovo' na thread. Use somente quando a "
            "pessoa pedir correção ou revisão de motivos. Máximo de 20 propostas por thread."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "integer"},
                "motivo_atual": {"type": "string"},
                "motivo_padrao": {"type": "string", "enum": list(MOTIVOS_PADRAO)},
                "evidencia": {"type": "string", "description": "Trecho curto da nota ou atividade que justifica."},
            },
            "required": ["deal_id", "motivo_atual", "motivo_padrao", "evidencia"],
        },
    },
]


def _prompt_sistema(autor: str) -> list[dict]:
    partes = [(PASTA_PROMPT / nome).read_text(encoding="utf-8")
              for nome in ("agente.md", "mapa-sql.md", "motivos-perda.md")]
    fixo = "\n\n---\n\n".join(partes).replace("{{EMPRESA}}", cfg.NOME_EMPRESA)
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    variavel = f"Hoje é {agora:%d/%m/%Y} ({agora:%A}), {agora:%H:%M} em Brasília. Quem pergunta: {autor or 'não identificado'}."
    return [
        {"type": "text", "text": fixo, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": variavel},
    ]


def _executar(nome: str, entrada: dict, thread: str) -> str:
    try:
        if nome == "consultar_banco":
            return banco.consultar(entrada["sql"])
        if nome == "pipedrive_buscar_deals":
            return pipedrive.buscar_deals(entrada["termo"], entrada.get("status"), entrada.get("limite", 10))
        if nome == "pipedrive_deal":
            return pipedrive.obter_deal(int(entrada["deal_id"]))
        if nome == "pipedrive_notas":
            return pipedrive.notas_do_deal(int(entrada["deal_id"]), entrada.get("limite", 10))
        if nome == "pipedrive_atividades":
            return pipedrive.atividades_do_deal(int(entrada["deal_id"]), entrada.get("limite", 20))
        if nome == "pipedrive_emails":
            return pipedrive.emails_do_deal(int(entrada["deal_id"]), entrada.get("limite", 10))
        if nome == "propor_correcao_motivo_perda":
            if entrada.get("motivo_padrao") not in MOTIVOS_PADRAO:
                return json.dumps({"ok": False, "erro": "Motivo fora da lista padrão."}, ensure_ascii=False)
            if len(estado.propostas_pendentes(thread)) >= MAX_PROPOSTAS_POR_THREAD:
                return json.dumps({"ok": False, "erro": "Limite de 20 propostas pendentes nesta thread."}, ensure_ascii=False)
            total = estado.registrar_proposta(thread, int(entrada["deal_id"]), entrada.get("motivo_atual", ""),
                                              entrada["motivo_padrao"], entrada.get("evidencia", ""))
            return json.dumps({"ok": True, "propostas_pendentes_na_thread": total,
                               "lembrete": "Nada foi alterado. Peça 'aprovo' de um aprovador na thread."},
                              ensure_ascii=False)
        return json.dumps({"erro": f"Ferramenta desconhecida: {nome}"})
    except banco.ConsultaRecusada as e:
        return json.dumps({"erro": str(e)}, ensure_ascii=False)
    except Exception as e:  # devolve o erro ao modelo para ele corrigir a consulta
        log.exception("Falha na ferramenta %s", nome)
        return json.dumps({"erro": f"{type(e).__name__}: {str(e)[:500]}"}, ensure_ascii=False)


def responder(pergunta: str, thread: str, autor: str, cliente: anthropic.Anthropic | None = None) -> str:
    cliente = cliente or anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    mensagens = estado.carregar_historico(thread) + [{"role": "user", "content": pergunta}]
    sistema = _prompt_sistema(autor)

    for _ in range(cfg.MAX_ITERACOES):
        r = cliente.messages.create(
            model=cfg.MODELO,
            max_tokens=4096,
            system=sistema,
            tools=FERRAMENTAS,
            messages=mensagens,
        )
        if r.stop_reason != "tool_use":
            texto = "\n".join(b.text for b in r.content if b.type == "text").strip()
            texto = texto or "Não consegui montar uma resposta. Pode reformular a pergunta?"
            estado.salvar_turno(thread, pergunta, texto)
            return texto

        mensagens.append({"role": "assistant", "content": r.content})
        resultados = []
        for bloco in r.content:
            if bloco.type == "tool_use":
                log.info("ferramenta=%s entrada=%s", bloco.name, json.dumps(bloco.input, ensure_ascii=False)[:500])
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloco.id,
                    "content": _executar(bloco.name, bloco.input, thread),
                })
        mensagens.append({"role": "user", "content": resultados})

    aviso = ("A análise ficou longa demais e parei antes de concluir. "
             "Tente uma pergunta mais específica (período, funil ou empresa).")
    estado.salvar_turno(thread, pergunta, aviso)
    return aviso
