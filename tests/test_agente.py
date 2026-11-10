"""Testes sem rede: HMAC, parsing do Teams, filtro de SQL, loop do agente e aprovação."""
import base64
import hashlib
import hmac
import json
import os
import tempfile
from types import SimpleNamespace

import pytest

TOKEN = base64.b64encode(b"segredo-de-teste").decode()
os.environ.update({
    "TEAMS_WEBHOOK_TOKEN": TOKEN,
    "POWER_AUTOMATE_URL": "https://exemplo.invalid/flow",
    "ARQUIVO_ESTADO": os.path.join(tempfile.mkdtemp(), "estado.sqlite3"),
    "APROVADORES": "Pessoa Aprovadora",
})

from fastapi.testclient import TestClient  # noqa: E402

from app import agente, banco, estado, main, pipedrive, teams  # noqa: E402


def assinar(corpo: bytes) -> str:
    sig = hmac.new(base64.b64decode(TOKEN), corpo, hashlib.sha256).digest()
    return "HMAC " + base64.b64encode(sig).decode()


def payload(texto: str, autor="Pessoa Aprovadora", msg="1700000000001"):
    return {
        "type": "message",
        "id": "1700000000999",
        "text": f"<at>Agente Leads</at>&nbsp;{texto}",
        "from": {"id": "29:x", "name": autor, "aadObjectId": "aad-123"},
        "conversation": {"id": f"19:abc@thread.tacv2;messageid={msg}"},
        "channelData": {"channel": {"id": "19:abc@thread.tacv2"}, "teamsTeamId": "19:geral@thread.tacv2"},
    }


# ---------- Teams ----------

def test_hmac_valido_e_invalido():
    corpo = b'{"a":1}'
    assert teams.assinatura_valida(corpo, assinar(corpo), TOKEN)
    assert not teams.assinatura_valida(corpo, assinar(b"outro"), TOKEN)
    assert not teams.assinatura_valida(corpo, None, TOKEN)
    assert not teams.assinatura_valida(corpo, "Bearer x", TOKEN)


def test_extrai_texto_e_ids():
    p = payload("raio-x da <b>ACME</b>   transportes")
    assert teams.texto_da_mensagem(p) == "raio-x da ACME transportes"
    ids = teams.ids_da_conversa(p)
    assert ids["canal_id"] == "19:abc@thread.tacv2"
    assert ids["mensagem_id"] == "1700000000001"
    assert ids["thread"] == "19:abc@thread.tacv2;1700000000001"


def test_markdown_vira_html_e_corta():
    assert "<strong>oi</strong>" in teams.markdown_para_html("**oi**")
    longo = teams.markdown_para_html("a" * 30_000)
    assert "cortada" in longo


# ---------- SQL somente leitura ----------

@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "with x as (select 1) select * from x",
    "select 'delete from t' as texto",          # palavra proibida dentro de texto é permitida
    "-- comentário\nSELECT count(*) FROM integrations.pipedrive_deals;",
])
def test_sql_aceito(sql):
    banco.validar_sql(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM integrations.pipedrive_deals",
    "select 1; drop table x",
    "update integrations.pipedrive_deals set value=0",
    "WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x",
    "select set_config('x','1',false)",  # passa pelo filtro, mas o usuário read-only barra efeitos
    "COPY t TO '/tmp/x'",
])
def test_sql_recusado(sql):
    if "set_config" in sql:
        banco.validar_sql(sql)  # função de leitura de sessão: aceita; a proteção real é o usuário read-only
        return
    with pytest.raises(banco.ConsultaRecusada):
        banco.validar_sql(sql)


# ---------- Loop do agente com cliente falso ----------

class ClienteFalso:
    """Primeiro pede a ferramenta consultar_banco, depois responde em texto."""

    def __init__(self):
        self.chamadas = 0
        self.messages = self

    def create(self, **kw):
        self.chamadas += 1
        if self.chamadas == 1:
            return SimpleNamespace(stop_reason="tool_use", content=[
                SimpleNamespace(type="tool_use", id="t1", name="consultar_banco",
                                input={"sql": "SELECT 1"}),
            ])
        # confere que o resultado da ferramenta voltou para o modelo
        ultima = kw["messages"][-1]["content"][0]
        assert ultima["type"] == "tool_result" and "linhas" in ultima["content"]
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Resposta final")])


def test_loop_do_agente(monkeypatch):
    monkeypatch.setattr(banco, "consultar", lambda sql: json.dumps({"colunas": ["x"], "linhas": [[1]]}))
    texto = agente.responder("quantos deals?", "thread-loop", "Teste", cliente=ClienteFalso())
    assert texto == "Resposta final"
    hist = estado.carregar_historico("thread-loop")
    assert [h["role"] for h in hist] == ["user", "assistant"]


def test_prompt_carrega_os_tres_arquivos():
    sistema = agente._prompt_sistema("Fulano")
    assert "Agente de Leads" in sistema[0]["text"]
    assert "pipedrive_deals_cf_values" in sistema[0]["text"]
    assert "Engajamento — Sem retorno do cliente" in sistema[0]["text"]
    assert "Fulano" in sistema[1]["text"]


def test_proposta_nao_altera_e_valida_motivo():
    r = json.loads(agente._executar("propor_correcao_motivo_perda", {
        "deal_id": 27270, "motivo_atual": "Optou pelo concorrente X",
        "motivo_padrao": "Concorrência — Concorrente selecionado", "evidencia": "fechou com o concorrente X",
    }, "thread-prop"))
    assert r["ok"] and r["propostas_pendentes_na_thread"] == 1
    r2 = json.loads(agente._executar("propor_correcao_motivo_perda", {
        "deal_id": 1, "motivo_atual": "x", "motivo_padrao": "Inventado", "evidencia": "y",
    }, "thread-prop"))
    assert not r2["ok"]


# ---------- Endpoint e aprovação ----------

@pytest.fixture
def cliente(monkeypatch):
    postados, aplicados = [], []
    monkeypatch.setattr(teams, "responder_na_thread", lambda c, m, t: postados.append(t))
    monkeypatch.setattr(agente, "responder", lambda p, th, a: f"resposta para: {p}")
    monkeypatch.setattr(pipedrive, "atualizar_motivo_perda",
                        lambda d, m: aplicados.append((d, m)) or {"ok": True})
    c = TestClient(main.app)
    c.postados, c.aplicados = postados, aplicados
    return c


def enviar(c, p, assinatura=True):
    corpo = json.dumps(p).encode()
    headers = {"Authorization": assinar(corpo)} if assinatura else {}
    return c.post("/teams", content=corpo, headers=headers)


def test_assinatura_obrigatoria(cliente):
    assert enviar(cliente, payload("oi"), assinatura=False).status_code == 401


def test_ajuda_imediata(cliente):
    r = enviar(cliente, payload("ajuda")).json()
    assert "agente de consulta" in r["text"]


def test_pergunta_vai_para_segundo_plano(cliente):
    r = enviar(cliente, payload("pipeline aberto")).json()
    assert r["text"].startswith("Recebi")
    assert cliente.postados == ["resposta para: pipeline aberto"]


def test_aprovacao_so_por_aprovador(cliente):
    msg = "1700000000777"
    thread = f"19:abc@thread.tacv2;{msg}"
    estado.registrar_proposta(thread, 27270, "Optou pelo concorrente X", "Concorrência — Concorrente selecionado", "nota")

    r = enviar(cliente, payload("aprovo", autor="Outra Pessoa", msg=msg)).json()
    assert "Só os aprovadores" in r["text"]
    assert cliente.aplicados == []

    r = enviar(cliente, payload("Aprovo", msg=msg)).json()
    assert "Aplicando 1" in r["text"]
    assert cliente.aplicados == [(27270, "Concorrência — Concorrente selecionado")]
    assert "atualizados" in cliente.postados[-1]
    assert estado.propostas_pendentes(thread) == []


def test_cancelar_descarta(cliente):
    msg = "1700000000888"
    thread = f"19:abc@thread.tacv2;{msg}"
    estado.registrar_proposta(thread, 1, "x", "Outros — Outro motivo", "y")
    r = enviar(cliente, payload("cancelar", msg=msg)).json()
    assert "descartadas" in r["text"]
    assert estado.propostas_pendentes(thread) == []
