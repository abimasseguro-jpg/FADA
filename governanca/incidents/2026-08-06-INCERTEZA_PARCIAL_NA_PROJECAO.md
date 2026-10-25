# Incidente epistemológico — incerteza parcial na projeção

## Falha observada

O primeiro teste do núcleo FADA-HS escolheu despachar uma tarefa curta para o slot
lento, embora a regra de cauda esperada exigisse priorizar a tarefa longa no slot
rápido. A projeção determinística tinha o mesmo makespan nas duas ordens.

## Causa

A penalização de incerteza era somada somente ao tempo da atribuição candidata. As
demais tarefas projetadas permaneciam determinísticas. Isso comparava objetivos
assimétricos e penalizava mais a decisão que antecipava a tarefa longa.

## Generalização

Uma função robusta de avaliação deve aplicar a mesma transformação de risco a
todos os elementos do contrafactual. Penalizar apenas a ação focal produz viés de
horizonte e pode inverter a decisão mesmo quando os planos são equivalentes.

## Solução

Aplicar `p_robusto = p_hat * (1 + lambda * (1 - confiança))` à tarefa candidata e
a todas as tarefas da projeção. Usar Sufferage somente como desempate em unidades
separadas. O teste de regressão permanece em `tests/test_policy.py`.

## Estado

Corrigido antes de qualquer integração produtiva; sem impacto na campanha MVHSN.

