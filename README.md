# Agente de Leads para RevOps

Um agente de IA que responde, dentro de um canal do Microsoft Teams, perguntas sobre leads e negociações:

- *"Por que perdemos deals no Inbound nos últimos 90 dias?"*
- *"Raio-X da empresa ACME"* (origem, campanha, conversa com o SDR, notas e motivo real da perda)
- *"Leads, MQLs e custo por SQL do Meta em outubro"*
- *"Quais deals estão parados em Proposta há mais de 30 dias?"*

Ele usa o Claude (API da Anthropic) com duas fontes: um **Postgres de integrações**, que guarda RD Station, Meetime, Pipedrive, Google Ads e Meta Ads, e o **Pipedrive ao vivo**. A regra de trabalho é **contar no banco e explicar no Pipedrive**: os números vêm do banco, e o porquê vem das notas, atividades e e-mails de cada negociação.

## Como funciona

```
Teams (@Agente Leads) ──webhook de saída──► seu servidor: /agente-leads/teams
                                               │  responde "Recebi…" em até 5 s
                                               ▼
                               Claude + ferramentas (Postgres somente leitura, Pipedrive)
                                               │
                                               ▼
                       Power Automate (gatilho de webhook do Teams) ──► responde na thread
```

- **Entrada:** webhook de saída do Teams, com validação HMAC. O Teams exige resposta em até 5 segundos, então o serviço confirma na hora e trabalha em segundo plano.
- **Saída:** um fluxo do Power Automate posta a resposta na mesma thread, como Bot de fluxo. Não precisa de licença Premium.
- **Memória:** as últimas 8 trocas de cada thread ficam em SQLite, então dá para continuar o assunto mencionando o agente na mesma thread.

## Segurança

- **Banco somente leitura em três camadas:** usuário do Postgres com SELECT e transação read-only, transação `READ ONLY` com tempo limite de 30 s em cada consulta e filtro que só aceita uma instrução `SELECT`/`WITH`.
- **Uma única escrita possível:** corrigir o motivo de perda de deals perdidos para a lista padrão. O agente só propõe. A correção acontece quando alguém da lista `APROVADORES` responde `@Agente Leads aprovo` na thread, e quem aplica é o próprio serviço, sem passar pelo modelo. Até 20 por thread.
- **Endpoint protegido:** só aceita chamadas assinadas com o token do webhook.
- **Exposição:** qualquer pessoa do time do Teams consegue perguntar e ver o que o banco e o usuário do Pipedrive enxergam. Use contas dedicadas e escopo mínimo.

## Motivos de perda

Na prática, o motivo de perda do CRM costuma ser texto livre ou de uma lista antiga. O agente normaliza cada motivo para uma lista padrão de 31 motivos em 14 famílias (Engajamento, Prioridade, Concorrência, Comercial, Aderência / ICP etc.). Antes de analisar, ele separa saneamento de CRM, duplicidade e cancelamento pós-venda. A tabela de normalização fica em [`prompt/motivos-perda.md`](prompt/motivos-perda.md).

## Adaptar para a sua empresa

| Arquivo | O que ajustar |
|---|---|
| `prompt/agente.md` | Funil, regras de negócio (CAC, exclusões, impostos de mídia) e limites conhecidos dos dados |
| `prompt/mapa-sql.md` | Tabelas e colunas do seu banco e chaves dos campos personalizados do Pipedrive |
| `prompt/motivos-perda.md` | Sua lista padrão de motivos e a tradução dos textos antigos |
| `app/motivos.py` | Texto exato dos motivos que podem ser aplicados na correção |
| `.env` | Chaves, URLs, nome da empresa e aprovadores |

## O que você vai precisar

| Item | Onde conseguir |
|---|---|
| Chave da API do Claude | console.anthropic.com → API Keys |
| Dono (owner) de um time no Teams | Para criar o webhook de saída. O admin do Microsoft 365 precisa permitir webhooks de saída |
| Power Automate | Para o fluxo que posta a resposta |
| Usuário do Pipedrive para o agente | Leitura dos deals e, para a correção de motivo de perda, permissão de editar deals |
| Servidor com Docker e um proxy HTTPS (ex.: nginx) | Onde o serviço vai rodar, com acesso ao Postgres |

## Implantação

### 1. Usuário somente leitura no Postgres

Edite `deploy/usuario_leitura.sql` (senha e nome do banco) e rode com o usuário dono das tabelas:

```bash
psql -U <dono> -d <banco> < deploy/usuario_leitura.sql
```

### 2. Subir o serviço

```bash
cp .env.example .env && nano .env
mkdir -p data && chown 10001:10001 data
chmod 600 .env
docker compose up -d --build
curl -s http://127.0.0.1:8090/saude    # {"ok":true}
```

O `docker-compose.yml` usa a rede do host: o serviço escuta só em `127.0.0.1:8090` e acessa o Postgres em `127.0.0.1:5432`. Ajuste se o seu banco estiver em outra rede.

### 3. Proxy HTTPS

Cole `deploy/nginx-agente.conf` no `server` HTTPS do seu domínio e recarregue o nginx:

```bash
nginx -t && systemctl reload nginx
curl -s https://seu-dominio.com/agente-leads/saude
```

### 4. Fluxo no Power Automate

1. **Criar → Fluxo da nuvem automatizado**.
2. Gatilho: **Quando uma solicitação de webhook do Teams for recebida**. Em "Quem pode disparar o fluxo", escolha **Qualquer pessoa**.
3. Ação **Analisar JSON**, com o corpo do gatilho e este esquema:
   ```json
   {"type":"object","properties":{"canal_id":{"type":"string"},"mensagem_id":{"type":"string"},"html":{"type":"string"}}}
   ```
4. Ação **Responder com uma mensagem em um canal**: Postar como **Bot de fluxo**; Postar em **Canal**; Equipe: o time do agente; Canal: valor personalizado `canal_id`; Mensagem: `html`; ID da mensagem: `mensagem_id`.
5. Salve e copie a URL do gatilho para `POWER_AUTOMATE_URL` no `.env`.

### 5. Webhook de saída no Teams

1. No time: **⋯ → Gerenciar equipe → Aplicativos → Criar um webhook de saída**.
2. Nome: `Agente Leads`. URL de retorno: `https://seu-dominio.com/agente-leads/teams`.
3. Copie o token de segurança (aparece uma vez só) para `TEAMS_WEBHOOK_TOKEN` e reinicie: `docker compose up -d`.

### 6. Testar

Num canal do time: `@Agente Leads ajuda`. Logs: `docker logs -f agente_leads_teams`.

## Desenvolvimento

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
```

Os testes rodam sem rede: validação HMAC, leitura das mensagens do Teams, filtro de SQL, ciclo do agente com um cliente falso e o fluxo de aprovação.

## Estrutura

```
app/main.py        endpoint do Teams, aprovação e fila em segundo plano
app/agente.py      ciclo do Claude e ferramentas
app/banco.py       SQL somente leitura
app/pipedrive.py   leitura do Pipedrive e a correção aprovada
app/teams.py       HMAC, leitura da mensagem e envio ao Power Automate
app/estado.py      histórico por thread e propostas (SQLite)
prompt/            instruções do agente, mapa do banco e motivos de perda
deploy/            usuário de leitura no Postgres e regra do nginx
tests/             testes sem rede (pytest)
```

## Licença

MIT. Veja [LICENSE](LICENSE).
