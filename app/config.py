"""Configuração lida das variáveis de ambiente (arquivo .env)."""
import os


def _req(nome: str) -> str:
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {nome}")
    return valor


def _lista(nome: str) -> list[str]:
    return [v.strip().lower() for v in os.environ.get(nome, "").split(",") if v.strip()]


class Config:
    # Claude (API da Anthropic)
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    MODELO = os.environ.get("MODELO_CLAUDE", "claude-sonnet-5-5")
    MAX_ITERACOES = int(os.environ.get("MAX_ITERACOES", "20"))

    # Teams: token de segurança do webhook de saída (mostrado uma vez ao criar)
    TEAMS_WEBHOOK_TOKEN = os.environ.get("TEAMS_WEBHOOK_TOKEN", "")
    # Power Automate: URL do gatilho "Quando uma solicitação de webhook do Teams for recebida"
    POWER_AUTOMATE_URL = os.environ.get("POWER_AUTOMATE_URL", "")

    # Banco de integrações (usuário SOMENTE LEITURA)
    DB_DSN = os.environ.get("DB_DSN", "")
    DB_MAX_LINHAS = int(os.environ.get("DB_MAX_LINHAS", "200"))

    # Pipedrive (token do usuário dedicado do agente)
    PIPEDRIVE_TOKEN = os.environ.get("PIPEDRIVE_TOKEN", "")
    PIPEDRIVE_EMPRESA = os.environ.get("PIPEDRIVE_EMPRESA", "suaempresa")
    # Nome da empresa usado nas instruções do agente
    NOME_EMPRESA = os.environ.get("NOME_EMPRESA", "a empresa")

    # Quem pode aprovar correções de motivo de perda (nomes ou aadObjectId, separados por vírgula)
    APROVADORES = _lista("APROVADORES")

    # Arquivo local para histórico das threads e propostas pendentes
    ARQUIVO_ESTADO = os.environ.get("ARQUIVO_ESTADO", "/data/estado.sqlite3")


cfg = Config()
