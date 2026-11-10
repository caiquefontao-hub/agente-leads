-- Usuário somente leitura para o agente.
-- Rode conectado ao banco de integrações com o usuário dono das tabelas.
-- Troque TROQUE_A_SENHA e NOME_DO_BANCO antes de rodar.

CREATE ROLE agente_leitura LOGIN PASSWORD 'TROQUE_A_SENHA';

GRANT CONNECT ON DATABASE NOME_DO_BANCO TO agente_leitura;
GRANT USAGE ON SCHEMA integrations TO agente_leitura;
GRANT SELECT ON ALL TABLES IN SCHEMA integrations TO agente_leitura;

-- tabelas e views criadas depois também ficam legíveis
ALTER DEFAULT PRIVILEGES IN SCHEMA integrations GRANT SELECT ON TABLES TO agente_leitura;

-- toda sessão desse usuário é somente leitura e tem tempo limite
ALTER ROLE agente_leitura SET default_transaction_read_only = on;
ALTER ROLE agente_leitura SET statement_timeout = '30s';
ALTER ROLE agente_leitura CONNECTION LIMIT 5;

-- conferência: deve listar as tabelas e views do schema integrations
-- SET ROLE agente_leitura; SELECT count(*) FROM integrations.pipedrive_deals; RESET ROLE;
