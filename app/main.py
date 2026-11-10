"""Serviço HTTP do Agente de Leads para o Microsoft Teams."""
import json
import logging
import re
import unicodedata

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from . import agente, estado, pipedrive, teams
from .config import cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("main")

app = FastAPI(title="Agente de Leads", docs_url=None, redoc_url=None)

AJUDA = (
    "Sou o agente de consulta de leads. Exemplos:\n"
    "- *raio-x da empresa ACME*\n"
    "- *por que perdemos deals no último trimestre?*\n"
    "- *funil e CAC do Meta em outubro*\n"
    "- *deals parados em Proposta há mais de 30 dias*\n\n"
    "Respondo na thread. Para continuar o assunto, me mencione na mesma thread."
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", sem_acento.lower()).strip()


def _eh_aprovador(ids: dict) -> bool:
    nome = (ids["autor_nome"] or "").strip().lower()
    aad = (ids["autor_aad"] or "").strip().lower()
    return bool(cfg.APROVADORES) and (nome in cfg.APROVADORES or aad in cfg.APROVADORES)


def _aplicar_propostas(ids: dict) -> str:
    propostas = estado.propostas_pendentes(ids["thread"])
    linhas, falhas = [], 0
    for p in propostas:
        r = pipedrive.atualizar_motivo_perda(p["deal_id"], p["motivo_novo"])
        link = pipedrive.link_deal(p["deal_id"])
        if r.get("ok"):
            linhas.append(f"- [{p['deal_id']}]({link}): {p['motivo_novo']}")
        else:
            falhas += 1
            linhas.append(f"- [{p['deal_id']}]({link}): **não alterado** ({r.get('erro')})")
    estado.limpar_propostas(ids["thread"])
    titulo = f"Motivos de perda atualizados por aprovação de {ids['autor_nome']}:"
    if falhas:
        titulo += f" ({falhas} com erro)"
    return titulo + "\n" + "\n".join(linhas)


def _processar(pergunta: str, ids: dict) -> None:
    """Roda em segundo plano depois que o Teams já recebeu a confirmação."""
    try:
        resposta = agente.responder(pergunta, ids["thread"], ids["autor_nome"])
    except Exception:
        log.exception("Falha ao responder")
        resposta = "Tive um erro ao consultar os dados. Tente de novo em alguns minutos; se continuar, avise o RevOps."
    try:
        teams.responder_na_thread(ids["canal_id"], ids["mensagem_id"], resposta)
    except Exception:
        log.exception("Falha ao postar no Teams via Power Automate")


def _aplicar_e_postar(ids: dict) -> None:
    """Aplica as correções aprovadas e posta o resultado (em segundo plano)."""
    try:
        texto = _aplicar_propostas(ids)
    except Exception:
        log.exception("Falha ao aplicar correções")
        texto = "Tive um erro ao aplicar as correções. Confira no Pipedrive antes de tentar de novo."
    try:
        teams.responder_na_thread(ids["canal_id"], ids["mensagem_id"], texto)
    except Exception:
        log.exception("Falha ao postar no Teams via Power Automate")


@app.get("/saude")
def saude():
    return {"ok": True}


@app.post("/teams")
async def webhook_teams(request: Request, tarefas: BackgroundTasks):
    corpo = await request.body()
    if not teams.assinatura_valida(corpo, request.headers.get("Authorization"), cfg.TEAMS_WEBHOOK_TOKEN):
        log.warning("Assinatura HMAC inválida")
        return JSONResponse({"type": "message", "text": "Assinatura inválida."}, status_code=401)

    payload = json.loads(corpo)
    pergunta = teams.texto_da_mensagem(payload)
    ids = teams.ids_da_conversa(payload)
    comando = _normalizar(pergunta)
    log.info("thread=%s autor=%s pergunta=%s", ids["thread"], ids["autor_nome"], pergunta[:200])

    if not pergunta or comando in ("ajuda", "help", "oi", "ola"):
        return teams.resposta_imediata(AJUDA)

    pendentes = estado.propostas_pendentes(ids["thread"])
    if pendentes and comando in ("aprovo", "aprovado", "pode aplicar", "aplicar", "aprovo tudo"):
        if not _eh_aprovador(ids):
            return teams.resposta_imediata(
                "Só os aprovadores definidos pelo RevOps podem aplicar correções no Pipedrive.")
        tarefas.add_task(_aplicar_e_postar, ids)
        return teams.resposta_imediata(f"Aplicando {len(pendentes)} correção(ões) no Pipedrive…")

    if pendentes and comando in ("recuso", "cancelar", "cancela", "nao aprovo", "descartar"):
        estado.limpar_propostas(ids["thread"])
        return teams.resposta_imediata("Propostas descartadas. Nada foi alterado no Pipedrive.")

    tarefas.add_task(_processar, pergunta, ids)
    return teams.resposta_imediata("Recebi. Estou consultando os dados e respondo aqui na thread.")
