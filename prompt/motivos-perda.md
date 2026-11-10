# Motivos de perda: lista padrão e normalização

## Pipedrive (venda): os 31 motivos padrão

Use o texto exato ao sugerir correção. Família = parte antes do travessão.

| Família | Motivo padrão |
|---|---|
| Contato | Contato - Desistiu após agendamento — somente quando houver evidência clara de desistência. |
| Contato | Contato - No Show recorrente / Sem retorno após reagendamento |
| Contato | Contato - No Show / Não compareceu à reunião |
| Engajamento | Engajamento — No-show sem reagendamento |
| Engajamento | Engajamento — Cliente perdeu interesse |
| Engajamento | Engajamento — Sem retorno do cliente |
| Qualificação | Qualificação — Busca por parceria |
| Qualificação | Qualificação — Busca apenas por orçamento / benchmark |
| Prioridade | Prioridade — Orçamento indisponível no período |
| Prioridade | Prioridade — Projeto postergado com previsão |
| Prioridade | Prioridade — Projeto suspenso sem previsão |
| Prioridade | Prioridade — Projeto sem prioridade |
| Concorrência | Concorrência — Concorrente selecionado |
| Concorrência | Concorrência — Manutenção do fornecedor atual |
| Contrato | Contrato — Processo não formalizado após aprovação |
| Contrato | Contrato — Divergência contratual |
| Comercial | Comercial — Relação custo-benefício não percebida |
| Comercial | Comercial — Investimento acima do orçamento |
| POC | POC — Critérios de sucesso não atingidos |
| POC | POC — Falha técnica durante validação |
| Desenvolvimento | Desenvolvimento — Esforço técnico inviável |
| Desenvolvimento | Desenvolvimento — Prazo incompatível |
| Integração | Integração — Integração não suportada |
| Produto | Produto — Produto não aderente ao processo |
| Produto | Produto — Funcionalidade ainda em roadmap |
| Aderência / ICP | Aderência / ICP — Requisito funcional não atendido |
| Aderência / ICP | Aderência / ICP — Porte ou complexidade insuficiente |
| Aderência / ICP | Aderência / ICP — Perfil do cliente fora do ICP |
| Administrativo | Administrativo — Empresa encerrou atividades |
| Administrativo | Administrativo — Negócio duplicado |
| Outros | Outros — Outro motivo |

## Normalização de textos antigos ou livres

Visto em 10/11/2026 nos últimos 90 dias do funil Inbound. Quando aparecer um texto novo, classifique pelo sentido e, se houver dúvida, leia as notas do deal.

| Texto encontrado | Família / motivo padrão |
|---|---|
| Sem qualificação comercial registrada (saneamento) | **Saneamento** (fora da análise) |
| Registro antigo de prospecção sem oportunidade qualificada… | **Saneamento** (fora da análise) |
| Saneamento - sem avanço comercial validado | **Saneamento** (fora da análise) |
| Duplicidade; Duplicidade - projeto consolidado no deal … | Administrativo — Negócio duplicado (fora da análise) |
| Sem retorno; Lead sem retorno após tentativas de contato; Não responde e-mails ou ligações, deixou de ser prioridade | Engajamento — Sem retorno do cliente |
| No Show | Contato - No Show / Não compareceu à reunião |
| Contato - Impossível contato | Engajamento — Sem retorno do cliente |
| Prioridade - Não é prioridade ou não tem interesse; Sem prioridade | Prioridade — Projeto sem prioridade |
| Prioridade - Reestruturação Interna | Prioridade — Projeto suspenso sem previsão |
| Preço - Achou caro; Preço / Investimento não aprovado | Comercial — Investimento acima do orçamento |
| Aderência - Perfil do cliente não é ideal | Aderência / ICP — Perfil do cliente fora do ICP |
| Aderência - Quer uma funcionalidade que não fornecemos ou foge do roadmap | Aderência / ICP — Requisito funcional não atendido |
| Concorrência — Contratou outra solução; "Optou pela <concorrente>…" | Concorrência — Concorrente selecionado (registre o nome do concorrente) |
| Cancelamento - Projeto cancelado | Prioridade — Projeto suspenso sem previsão |
| Cancelamento - Não fez uso do software; Cancelamento - Mudança de gestão | **Cancelamento pós-venda** (não é perda de negociação; mostre à parte) |
| Motivo padrão com texto extra depois (ex.: "Prioridade — Projeto suspenso sem previsão. Em 06/11…") | O motivo padrão do início; o texto extra é contexto |
| Vazio (nulo) | **Sem motivo registrado** |

Diferença útil entre parecidos:
- **Contato** = o lead não apareceu ou sumiu antes ou logo depois da primeira reunião.
- **Engajamento** = houve conversa real e o cliente parou de responder ou perdeu interesse depois.
- **Prioridade** = o cliente quer, mas não agora.
- **Comercial** = preço ou valor percebido. **Concorrência** = escolheu outra solução ou ficou com a atual.

## Meetime (pré-venda): motivos dos SDRs

Lista vista nos últimos 90 dias. Agrupamento sugerido para análise:

| Motivo no Meetime | Grupo |
|---|---|
| Prioridade - Não tem interesse ou não é prioridade | Interesse / prioridade |
| Cadência encerrada automaticamente; Tentativas de contato esgotadas - Inbound / Inbound Passivo / Outbound; Tentativas de e-mails automáticos esgotados | Sem contato |
| Contato - Dados de contato inválidos; Cadastro errado - Estudante ou procurava outra coisa; Cadastro errado - Motorista | Lead inválido |
| No-Show - Não compareceu ou reagendou diversas vezes; Reagendamento | No-show |
| Aderência - Quer uma funcionalidade que não fornecemos…; Aderência - Não tem logística; Aderência - Empresa pequena | Fora do ICP |
| Fechou com concorrente; Outros - Concorrente / Software | Concorrência |
| Preço - Achou caro | Preço |
| Outros - Lead duplicado; Outros - Já é cliente; Suporte - Usuário Plataforma; Parceria - Contato transferido…; Outros - Empresa falida; Outros - Decisão no exterior; Outros - Empresa não tem site… | Administrativo / outros |

`status = 'WON'` na prospecção significa que o lead foi passado para vendas, não que virou cliente. `SWITCHED_CADENCE` é troca de cadência, não perda.
