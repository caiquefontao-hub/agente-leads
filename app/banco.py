"""Consultas ao banco de integrações, somente leitura.

Três camadas de proteção:
1. O usuário do Postgres só tem SELECT e transação somente leitura (ver deploy/usuario_leitura.sql).
2. Cada consulta roda numa transação READ ONLY com tempo limite.
3. Este módulo só aceita uma instrução SELECT/WITH por vez.
"""
import json
import re
from datetime import date, datetime
from decimal import Decimal

import psycopg

from .config import cfg

_PROIBIDAS = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|call|do|"
    r"vacuum|analyze|refresh|reindex|cluster|comment|lock|set|reset|listen|notify|prepare|execute)\b",
    re.I,
)


class ConsultaRecusada(ValueError):
    pass


def validar_sql(sql: str) -> str:
    limpo = re.sub(r"--[^\n]*", " ", sql)
    limpo = re.sub(r"/\*.*?\*/", " ", limpo, flags=re.S).strip().rstrip(";").strip()
    if ";" in limpo:
        raise ConsultaRecusada("Envie uma única consulta, sem ponto e vírgula no meio.")
    if not re.match(r"^(select|with)\b", limpo, re.I):
        raise ConsultaRecusada("Só são aceitas consultas que começam com SELECT ou WITH.")
    # remove textos entre aspas simples antes de procurar palavras proibidas
    sem_textos = re.sub(r"'(?:[^']|'')*'", "''", limpo)
    proibida = _PROIBIDAS.search(sem_textos)
    if proibida:
        raise ConsultaRecusada(f"Palavra não permitida na consulta: {proibida.group(0).upper()}.")
    return limpo


def _serializar(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return valor


def consultar(sql: str) -> str:
    """Executa e devolve até DB_MAX_LINHAS linhas em JSON compacto."""
    consulta = validar_sql(sql)
    limite = cfg.DB_MAX_LINHAS
    with psycopg.connect(cfg.DB_DSN, autocommit=False) as con:
        with con.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '30s'")
            cur.execute(consulta)
            colunas = [d.name for d in cur.description] if cur.description else []
            linhas = cur.fetchmany(limite + 1)
        con.rollback()
    cortado = len(linhas) > limite
    linhas = linhas[:limite]
    resultado = {
        "colunas": colunas,
        "linhas": [[_serializar(v) for v in linha] for linha in linhas],
        "total_linhas_mostradas": len(linhas),
        "cortado": cortado,
    }
    if cortado:
        resultado["aviso"] = f"Mais de {limite} linhas. Agregue ou filtre melhor."
    return json.dumps(resultado, ensure_ascii=False, default=str)
