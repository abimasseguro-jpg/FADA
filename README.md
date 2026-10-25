# FADA — Framework Adaptativo de Distribuição de Atividades

FADA é o projeto transversal de escalonamento adaptativo para filas heterogêneas.
Ele nasceu no MVHSN, mas seu modelo, suas políticas e seus critérios de validação
não pertencem a uma campanha científica específica.

## Estado

**Experimental.** O núcleo formal e uma política de referência estão disponíveis
para testes e backtests. A promoção para produção depende dos gates descritos em
[`governanca/VALIDATION_GATES.md`](governanca/VALIDATION_GATES.md). Os scripts
históricos copiados do MVHSN não são, por si só, implementações de produção.

Em 08/08/2026, G0 e G1 foram concluídos. O backtest temporal G2 foi executado com
200 réplicas pareadas e não comprovou não inferioridade contra Sufferage; por isso,
G3 não foi iniciado.

Em 04/09/2026, a candidata independente `fada-hs/0.4` passou um novo backtest
offline pré-registrado contra Sufferage (400 seeds confirmatórias), inclusive os
limites de não inferioridade, cauda e custo decisório. Essa evidência é separada
do G2 histórico e não autoriza shadow, canário ou produção; consulte
[`NG2_HS04_RESULT_2026-09-04.md`](governanca/gates/NG2_HS04_RESULT_2026-09-04.md).

Em 04/09/2026, o núcleo foi homologado separadamente para execução CPU offline e
observacional no ambiente registrado, com 51 testes e um ensaio multiprocesso
pré-registrado. Essa aprovação não promove G2, campanha ou produção e não inclui
GPU; consulte
[`CPU_HOMOLOGATION_RESULT_2026-09-04.md`](governanca/gates/CPU_HOMOLOGATION_RESULT_2026-09-04.md).

Também em 04/09/2026, o FADA foi aprovado no nó CPU `aces` como plano de
controle shadow sobre um snapshot consistente da campanha GPU
`momeng_gpu_full_20260827`. O ensaio preservou a fila e a elegibilidade GPU, mas
não autoriza despacho ou produção; consulte
[`CPU_CAMPAIGN_SHADOW_RESULT_2026-09-04.md`](governanca/gates/CPU_CAMPAIGN_SHADOW_RESULT_2026-09-04.md).

Uma janela shadow ao vivo posterior também foi aprovada com seis capturas
somente leitura executadas no `aces`. O serviço foi encerrado ao fim da janela;
consulte
[`CPU_LIVE_SHADOW_RESULT_2026-09-04.md`](governanca/gates/CPU_LIVE_SHADOW_RESULT_2026-09-04.md).

A trilha CPU está operacionalmente homologada para executar o plano de controle
em shadow no `aces`, com start/status/stop, evidência por execução e falha fechada.
Ela não aplica decisões na campanha. Consulte
[`CPU_OPERATIONAL_HOMOLOGATION_RESULT_2026-09-04.md`](governanca/gates/CPU_OPERATIONAL_HOMOLOGATION_RESULT_2026-09-04.md).

## Organização

- `src/fada/`: domínio, estimador e política reutilizáveis;
- `adapters/mvhsn/`: leitura e análise da fila SQLite do MVHSN;
- `experiments/`: protótipos, simulações e resultados históricos;
- `docs/`: especificação, arquitetura, estudos e diagramas;
- `governanca/`: Sentinela-FADA, decisões, pareceres e gates de promoção;
- `references/`: catálogo das fontes usadas no desenho;
- `tools/`: geração de documentos e imagens;
- `tests/`: contratos mínimos do núcleo.

Para campanhas novas que desejem progresso simultâneo dos cenários, o núcleo
oferece a intercalação opcional da fila descrita em
[`docs/SCENARIO_INTERLEAVING.md`](docs/SCENARIO_INTERLEAVING.md).

O núcleo também inclui o Resource Controller experimental `fada-rc/0.1`. Ele
recomenda, por máquina, níveis previamente autorizados de threads e clock a
partir da vazão e de limites térmicos/operacionais. Nenhum atuador produtivo é
fornecido; consulte
[`docs/FADA_RESOURCE_CONTROLLER_01_SPECIFICATION.md`](docs/FADA_RESOURCE_CONTROLLER_01_SPECIFICATION.md).
Configurações estruturais de exemplo ficam em `configs/`, contratos JSON em
`schemas/v1/` e o replay observacional em `src/fada/resource_replay.py`.

## Uso local

```bash
cd /home/atilapcorreia/ARTIGOS/FADA
python3 -m unittest discover -s tests -v
python3 experiments/run_cpu_homologation.py
bash governanca/tools/start_cpu_shadow_acer.sh
bash governanca/tools/status_cpu_shadow_acer.sh
bash governanca/tools/stop_cpu_shadow_acer.sh
```

A mini campanha `momeng-cpu-mini-acer-20260904` foi criada no Acer em raiz
isolada, sem acesso à MVHSN distribuída. Consulte
[`CPU_MVHSN_MINI_ACER_RESULT_2026-09-04.md`](governanca/gates/CPU_MVHSN_MINI_ACER_RESULT_2026-09-04.md).

```bash
python3 governanca/tools/sentinela_fada.py audit --root .
python3 experiments/backtest_temporal.py \
  --replicates 200 --tasks-per-scenario 12 --bootstrap-samples 10000 \
  --output experiments/results/G2_TEMPORAL_BACKTEST_2026-08-08.json
```

O MVHSN permanece dono de seus dados, filas e evidências de campanha. FADA recebe
somente adaptadores e cópias identificadas de artefatos históricos; nenhum arquivo
usado pela campanha ativa foi removido.

### Política opt-in por custo e progresso

O dispatcher inclui `CostWeightedProgressPolicy`, uma política pura que equilibra o avanço dos cenários pelo custo estimado e pelo progresso interno das tarefas. Ela exige um mapa `progress={task_id: fraction}` com frações em `[0, 1]`, preserva afinidade e falha fechado em dados inválidos. O uso é opt-in e permanece sujeito aos gates de `governanca/VALIDATION_GATES.md`:

```python
from fada.dispatcher import FADADispatcher
from fada.policy_cost_progress import CostWeightedProgressPolicy

dispatcher = FADADispatcher(policy=CostWeightedProgressPolicy())
receipt = dispatcher.dispatch(tasks, workers, estimator, queue, progress=progress)
```

### Cenários em avanço conjunto

`ConcurrentScenarioPolicy` distribui os próximos despachos entre cenários a
partir dos contadores de tarefas concluídas, ativas e pendentes. Ela permite
que `n100`, `n200` e `n400` iniciem e avancem juntos quando há slots e tarefas
elegíveis. Consulte [a documentação de intercalação](docs/SCENARIO_INTERLEAVING.md)
para o contrato do snapshot e um exemplo de uso.

Para cenários heterogêneos, `CostBalancedScenarioPolicy` combina a fração de
trabalho concluída/ativa, `Task.complexity`, duração estimada e velocidade dos
workers. Ela prioriza o cenário realmente atrasado em trabalho e delega ao
plano protegido do FADA a associação tarefa-worker. O recurso é opt-in, exige
`ScenarioWorkStatus` consistente e falha fechado.

### Watchdog adaptativo da campanha MVSNC

`FADADispatcher.plan_adaptive` e `src/fada/adaptive.py` implementam a política
opt-in de recuperação de defasagem, manutenção de sincronização e finalização
para a grade MVSNC `d01`–`d03`. O módulo calcula trabalho residual, capacidade
por velocidade e metas móveis; o adaptador da campanha preserva claims
atômicos e usa a política anterior em caso de falha do watchdog. Consulte
[o contrato e a validação](docs/ADAPTIVE_WATCHDOG.md). Esta integração não
altera o comportamento padrão de outros dispatchers FADA.
