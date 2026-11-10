"""Histórico por thread e propostas de correção pendentes (SQLite local)."""
import json
import sqlite3
import time
from contextlib import contextmanager

from .config import cfg

MAX_TURNOS = 8  # pares pergunta/resposta guardados por thread


@contextmanager
def _con():
    con = sqlite3.connect(cfg.ARQUIVO_ESTADO)
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS historico (
            thread TEXT, papel TEXT, texto TEXT, criado REAL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS propostas (
            thread TEXT, deal_id INTEGER, motivo_atual TEXT, motivo_novo TEXT,
            evidencia TEXT, criado REAL, PRIMARY KEY (thread, deal_id))""")
        yield con
        con.commit()
    finally:
        con.close()


def carregar_historico(thread: str) -> list[dict]:
    with _con() as con:
        linhas = con.execute(
            "SELECT papel, texto FROM historico WHERE thread=? ORDER BY criado DESC LIMIT ?",
            (thread, MAX_TURNOS * 2),
        ).fetchall()
    return [{"role": p, "content": t} for p, t in reversed(linhas)]


def salvar_turno(thread: str, pergunta: str, resposta: str) -> None:
    agora = time.time()
    with _con() as con:
        con.execute("INSERT INTO historico VALUES (?,?,?,?)", (thread, "user", pergunta, agora))
        con.execute("INSERT INTO historico VALUES (?,?,?,?)", (thread, "assistant", resposta, agora + 0.001))


def registrar_proposta(thread: str, deal_id: int, motivo_atual: str, motivo_novo: str, evidencia: str) -> int:
    with _con() as con:
        con.execute("INSERT OR REPLACE INTO propostas VALUES (?,?,?,?,?,?)",
                    (thread, deal_id, motivo_atual, motivo_novo, evidencia, time.time()))
        return con.execute("SELECT COUNT(*) FROM propostas WHERE thread=?", (thread,)).fetchone()[0]


def propostas_pendentes(thread: str) -> list[dict]:
    with _con() as con:
        linhas = con.execute(
            "SELECT deal_id, motivo_atual, motivo_novo, evidencia FROM propostas WHERE thread=? ORDER BY criado",
            (thread,),
        ).fetchall()
    return [dict(zip(("deal_id", "motivo_atual", "motivo_novo", "evidencia"), l)) for l in linhas]


def limpar_propostas(thread: str) -> None:
    with _con() as con:
        con.execute("DELETE FROM propostas WHERE thread=?", (thread,))


def exportar(thread: str) -> str:
    return json.dumps({"historico": carregar_historico(thread), "propostas": propostas_pendentes(thread)},
                      ensure_ascii=False)
