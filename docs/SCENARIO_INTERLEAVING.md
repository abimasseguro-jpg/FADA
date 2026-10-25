# Intercalação de cenários na fila

A campanha Jet p3q3 do MVSNC mostrou avanço simultâneo dos três cenários em
quatro slots. O código dela percorre os cenários de forma intercalada ao formar
as partições. Isso ajuda a manter representantes de cada cenário nos lotes;
a ocupação de CPU e a reposição dos workers também contribuíram para o avanço
observado. A observação não demonstra que os cenários tenham o mesmo custo ou
resultado científico.

`fada.queue_order.interleave_scenarios()` torna a ordem intercalada disponível
como opção pura para projetos que criem uma **nova** fila. Ela conserva a ordem
interna de cada cenário, a identidade das tarefas e a cobertura integral. O
projeto hospedeiro ainda decide elegibilidade, capacidade, política de despacho,
persistência e recuperação. Um exemplo:

```python
from fada.queue_order import interleave_scenarios

pending = interleave_scenarios(task_catalog)
```

Não reordenar filas já persistidas ou campanhas em curso: isso mudaria a
prioridade de retries e poderia divergir do estado de posse dos workers. A
intercalação tampouco deve substituir estimativas de duração ou restrições de
elegibilidade. Antes de adotá-la em uma nova campanha, verificar cobertura e
ausência de duplicatas, depois medir a cada 30 minutos tarefas concluídas por
cenário, workers realmente ocupados, CPU efetiva, progresso científico,
checkpoints, retries e resultados aceitos. O equilíbrio da contagem de tarefas
é diferente do equilíbrio do trabalho computacional.

## Avanço conjunto durante o despacho

Para uma nova campanha que deve manter os cenários em andamento ao mesmo tempo,
use `ConcurrentScenarioPolicy` no `FADADispatcher`. Em cada chamada, o projeto
hospedeiro fornece uma fotografia consistente da fila pendente, dos slots livres
e dos contadores de tarefas concluídas e ativas por cenário. Tarefas ativas
entram na fração já alocada: assim, sucessivos slots livres tendem a receber
cenários diferentes. A política escolhe o cenário com menor fração
`(concluídas + ativas) / (concluídas + ativas + pendentes)`; depois, a política
FADA existente escolhe a tarefa e o slot elegíveis dentro do cenário.

```python
from fada.dispatcher import FADADispatcher
from fada.policy_scenario_cohort import ConcurrentScenarioPolicy, ScenarioStatus

dispatcher = FADADispatcher(policy=ConcurrentScenarioPolicy())
status = {
    "n100": ScenarioStatus(completed=0, active=0),
    "n200": ScenarioStatus(completed=0, active=0),
    "n400": ScenarioStatus(completed=0, active=0),
}
receipt = dispatcher.dispatch(pending, free_slots, estimator, queue,
                              scenario_status=status)
```

Após cada `claim` confirmado, o hospedeiro atualiza a fotografia antes do
próximo despacho. O status deve conter exatamente os cenários presentes em
`pending`; dados ausentes, duplicatas e contadores inválidos bloqueiam a
decisão. Cenários sem tarefa elegível para os slots livres são ignorados até
que haja capacidade compatível. A política é opt-in; sua adoção em uma
campanha exige medir avanço científico e resultados aceitos por cenário, além
da ocupação dos workers.

## Balanceamento por atraso, custo e velocidade

Quando cenários têm custos diferentes, `CostBalancedScenarioPolicy` mede o
avanço em unidades de trabalho, não apenas em número de tarefas. O hospedeiro
informa `completed_work` e `active_work` por cenário numa fotografia
consistente; o trabalho pendente vem de `Task.complexity`. A política escolhe a
menor fração de trabalho alocado e o plano protegido do FADA associa a tarefa
ao worker usando duração estimada, velocidade, elegibilidade e incerteza.

```python
from fada.dispatcher import FADADispatcher
from fada.policy_scenario_cohort import (
    CostBalancedScenarioPolicy, ScenarioWorkStatus,
)

dispatcher = FADADispatcher(policy=CostBalancedScenarioPolicy())
status = {
    "n100": ScenarioWorkStatus(completed_work=120, active_work=8),
    "n200": ScenarioWorkStatus(completed_work=80, active_work=16),
    "n400": ScenarioWorkStatus(completed_work=40, active_work=32),
}
receipt = dispatcher.dispatch(
    pending, free_slots, estimator, queue, scenario_status=status,
)
```

Após cada `claim`, o hospedeiro soma imediatamente a complexidade da tarefa a
`active_work` antes da próxima decisão. Snapshot ausente, cenário divergente,
identidade duplicada ou custo não estimável produz fallback sem claim. A
política é opt-in e não altera filas ou campanhas existentes.
