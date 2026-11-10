# Mapa do banco (schema `integrations`)

> Exemplo de schema. As views `vw_*` são as do projeto original; troque pelos nomes e colunas do seu banco.

Sempre qualifique com o schema: `integrations.<tabela>`. Datas e horas estão em UTC (`timestamptz`); para agrupar por dia ou mês no horário de Brasília, use `(coluna AT TIME ZONE 'America/Sao_Paulo')`.

## Leads e funil de marketing

**`vw_leads_campanha`**: uma linha por pessoa + canal + campanha.
`data_conversao` (date), `canal`, `tipo` (pago ou orgânico), `campanha`, `formulario`, `anuncio`, `nome`, `telefone`, `email`, `empresa`, `cargo`, `faturamento_anual`, `custo_logistico_anual`, `entregas_dia`, `gasto_mensal_frete`, `colaboradores_logistica`, `erp`, `outras_respostas`, `primeira_conversao` ('Sim'/'Não'), `etapa_funil`, `mql`, `sal`, `data_sal`, `sql_status`, `data_sql`, `etapa_pipedrive`, `status_deal`, `plataforma`, `conjunto_meta`, `campanha_meta`.
Confira os valores possíveis de `mql`, `sal` e `sql_status` com `SELECT DISTINCT` antes de filtrar.

**`vw_resumo_campanhas`**: por dia + mídia + campanha.
`dia`, `midia`, `campanha`, `investimento` (Meta sem imposto), `cliques`, `impressoes`, `leads`, `mqls`, `sals`, `sqls`, `propostas`, `validacao_tecnica`, `negociacao`, `analise_juridica`, `fechamento`, `wons`, `receita`.

**`vw_custos_marketing`**: gasto diário por canal (Google, Meta, ChatGPT Ads). Sem imposto do Meta e sem LinkedIn. Descubra as colunas antes de usar.

**`vw_cac_midia_real`**: gasto e deals pagos por dia e canal, na mesma coluna de data. Descubra as colunas antes de usar.

**`vw_won_origem_real`**: só deals **ganhos**, com o canal real reconstruído.
`deal_id`, `empresa`, `vendedor`, `canal_pipedrive`, `canal_real`, `situacao`, `encontrado_por`, `confianca`, `tipo_pipedrive`, `tipo_real`, `campanha_pipedrive`, `campanha_real`, `formulario_rd`, `empresa_rd`, `email_rd`, `source_rd`, `medium_rd`, `data_conversao_rd`, `mrr`, `ltv`, `data_entrada`, `data_fechamento`, `sct_dias` (ciclo de venda em dias).

Outras views (descubra as colunas antes de usar): `vw_funil`, `vw_funil_completo`, `vw_funil_pago`, `vw_funil_produto`, `vw_movimentacao_funil`, `vw_won_detalhado`, `vw_performance_vendas`, `vw_sal_vendedor`, `vw_mql_produto`, `vw_leads_porte`, `vw_leads_sdr_campanha`, `vw_criativos_convertidos`, `vw_roas_coorte`, `vw_trafego_campanha`, `vw_cpmql_diario`.

## Pipedrive no banco

**`pipedrive_deals`**:
`deal_id`, `title`, `add_time`, `update_time`, `value`, `status` ('open', 'won', 'lost'), `lost_reason`, `pipeline_id`, `stage_id`, `org_id`, `person_id`, `owner_id`, `pipeline_name`, `stage_name`, `owner_name`, `stage_change_time`, `won_time`, `lost_time`, `close_time`, `expected_close_date`, `archive_time`, `is_deleted`, `is_archived`, `acv`, `arr`, `mrr`.
Filtre `is_deleted = false`. A etapa "Análise Jurídico " tem um espaço no fim; use `trim(stage_name)`.

**`pipedrive_deals_cf_values`**: campos personalizados em formato longo. `deal_id`, `key`, `type`, `name`, `value`.
Nomes úteis em `name`: 'Produto', 'Perfil', 'Tipo de Venda', 'Vendedor Responsável', 'SDR responsável', 'Pré vendedor (técnico)', 'Unidade de negócio', 'Inbound - Campanha', 'Inbound - Source', 'Inbound - Medium', 'Inbound - Conversão', 'Inbound - ID RD', 'Inbound - Conteúdo', 'Inbound - Termo', 'utm_adsetname', 'Faturamento Anual', 'Gasto Mensal com Frete'.
Exemplo: `JOIN integrations.pipedrive_deals_cf_values s ON s.deal_id = d.deal_id AND s.name = 'Inbound - Source'`.
Valores de UTM costumam vir sujos (`google` e `Google`, `meta` e `facebook`, `.` e `(direct)`): normalize antes de agrupar.

**`pipedrive_deals_stages_change`**: `deal_id`, `stage_change_time`, `pipeline_id`, `stage_id`. Histórico de mudanças de etapa.

Também: `pipedrive_persons`, `pipedrive_organizations`, `pipedrive_users`, `pipedrive_stages`, `pipedrive_pipelines`.

## Meetime no banco

**`meetime_prospections`**: uma linha por prospecção.
`prospection_id`, `lead_id`, `cadence_id`, `cadence_name`, `lead_base`, `owner_id`, `owner_name` (SDR), `status` ('WON' = passou para vendas, 'LOST', 'SWITCHED_CADENCE', em andamento), `lost_reason_id`, `lost_reason`, `lead_origin_channel`, `lead_origin_source`, `lead_origin_campaign`, `conversion`, `rd_conversion_date`, `created_at`, `begin_at`, `scheduled_at`, `end_at`, `last_activity_at`, `first_activity_at`, `is_deleted`.

**`meetime_leads`**: `lead_id`, `current_prospection_id`, `name`, `email`, `company`, `title`, `website`, `city`, `state`, `fit_score`, `external_reference`, `created_at`, `updated_at`, `is_deleted`.

Também: `meetime_cadences`, `meetime_leads_cf_values`.

## RD Station
**`vw_leads_perdidos`**: `uuid`, `data_entrada`, `name`, `email`, `job_title`, `city`, `state`, `fit_score`, `lifecycle_stage`, `opportunity`, `interest`, `tags`, `origin`, `custom_origin_source`, `custom_origin_medium`, `custom_origin_campaign`, `last_conversion_date`, `last_marked_opportunity_date`.

## Exemplos de consulta

Perdas por motivo (90 dias, Inbound):
```sql
SELECT lost_reason, count(*) AS deals
FROM integrations.pipedrive_deals
WHERE status = 'lost' AND pipeline_id = 1 AND NOT is_deleted
  AND lost_time >= now() - interval '90 days'
GROUP BY 1 ORDER BY 2 DESC
```

Pipeline aberto por etapa, com deals parados:
```sql
SELECT trim(stage_name) AS etapa, count(*) AS deals, sum(value) AS valor,
       count(*) FILTER (WHERE stage_change_time < now() - interval '30 days') AS parados_30d
FROM integrations.pipedrive_deals
WHERE status = 'open' AND pipeline_id = 1 AND NOT is_deleted
GROUP BY 1 ORDER BY 2 DESC
```

## Pipedrive ao vivo: chaves dos campos personalizados

Em `pipedrive_deal`, os campos personalizados vêm com uma chave de 40 caracteres. Preencha a tabela com as chaves da sua conta (Pipedrive → Configurações → Campos de dados, ou a API `dealFields`):

| Campo | Chave |
|---|---|
| Produto | `<chave>` |
| Perfil | `<chave>` |
| Vendedor Responsável | `<chave>` |
| SDR responsável | `<chave>` |
| Inbound - Campanha | `<chave>` |
| Inbound - Source | `<chave>` |
| Inbound - Medium | `<chave>` |

Campos de opção vêm como ID numérico. Para o nome, use `pipedrive_deals_cf_values` no banco.
