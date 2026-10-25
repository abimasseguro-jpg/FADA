# Protocolo de evolução integrada FADA-HS 0.2 e FADA Resource Controller 0.1

- **Identificador:** `FADA-EVO-HS02-RC01-V1`
- **Data:** 2026-09-02
- **Estado:** planejado; nenhuma implementação ou campanha iniciada
- **Origem:** `docs/SOLICITACAO_EVOLUCAO_FADA_RESOURCE_CONTROLLER.md`
- **Candidatos:** `fada-hs/0.2` e `fada-rc/0.1`
- **Baseline preservada:** `fada-hs/0.1`
- **Resultado histórico preservado:** G2 de 2026-08-08, não aprovado

Este documento transforma a solicitação de evolução em tickets executáveis e
interdependentes. Ele governa a sequência do trabalho, mas não autoriza testes,
backtests confirmatórios, acesso a filas, shadow em campanha real, canário ou
produção. Cada ação continua sujeita ao `AGENTS.md` e às autorizações indicadas
em cada ticket.

## 1. Resultado esperado

A evolução produzirá dois componentes independentes e coordenados:

1. **FADA-HS 0.2** seleciona a próxima associação entre tarefa e slot elegível,
   comparando sua proposta com Sufferage e usando incerteza para falhar de forma
   segura.
2. **FADA Resource Controller 0.1** recomenda, inicialmente sem aplicar, quantos
   slots autorizados devem ficar disponíveis em cada máquina.

O adaptador apenas traduz o estado do hospedeiro. O executor hospedeiro continua
sendo o único componente autorizado a iniciar workers, conceder leases e executar
tarefas. Sentinela e mAI observam, validam e registram evidências; nunca comandam
campanhas.

## 2. Estado de partida demonstrado

| Área | Existe | Evidência atual | Lacuna para a evolução |
|---|---|---|---|
| Domínio | `Task`, `WorkerSlot`, `Decision` | `src/fada/domain.py` | requisitos, capacidades, backend, hardware e saúde |
| Estimador | mediana por cenário/máquina, fallback por cenário e prior | `src/fada/estimation.py` | concorrência, recência, drift, censura, quantis e calibração |
| FADA-HS | makespan robusto; Sufferage apenas no desempate | `src/fada/policy.py` | faixa Sufferage e proteção explícita pelo baseline |
| Controle de versão | promoção e rollback em memória | `src/fada/control.py` | configuração persistível e estados separados do RC |
| Backtest | FIFO, interleaved, Min-Min, Max-Min, Sufferage e FADA | `experiments/backtest_temporal.py` | incluir 0.1, 0.2, concorrência, censura, cauda e RC |
| Shadow | leitor MVHSN direto e somente leitura | `adapters/mvhsn/fada_shadow_report.py` | contrato genérico, snapshots, replay e telemetria versionada |
| Governança | G0/G1 concluídos; G2 não aprovado | `governanca/VALIDATION_GATES.md` | novos gates e evidências exclusivos para 0.2/0.1 |
| Resource Controller | não existe | ausência em `src/fada/` | domínio, política, modos, histerese e interface de recomendação |

O G2 histórico não pode ser apagado, substituído ou reinterpretado. Em
particular, `fada-hs/0.1` apresentou makespan médio 647,711 contra 637,728 do
Sufferage e razão p95 1,1084; seu estado continua experimental e não promovido.

## 3. Arquitetura-alvo e fronteiras de autoridade

```text
                       projeto hospedeiro
                 fila + executor + autoridade
                            |
                     snapshot somente leitura
                            v
                    adaptador do hospedeiro
                            |
                  domínio normalizado e versionado
                 /             |                 \
                v              v                  v
      estimador de duração  capacidades       telemetria
          e incerteza       e requisitos      de máquina
            /    \              |                  |
           v      v             v                  v
    FADA-HS 0.2  modelo de concorrência --> FADA-RC 0.1
           |                                  |
     decisão proposta                 recomendação de capacidade
           \                                  /
            +-------- ledger shadow ---------+
                            |
                 Sentinela/mAI observacional

Somente após gates e autorização explícita:

decisão/recomendação -> adaptador de comando -> executor hospedeiro
```

Regras de fronteira:

- o núcleo não abre banco, não chama SSH, não inicia processos e não altera fila;
- elegibilidade e equivalência científica são entradas, nunca inferências da FADA;
- o RC escolhe apenas entre níveis de capacidade autorizados pelo hospedeiro;
- redução de capacidade nunca interrompe tarefa em execução;
- falta, atraso ou incoerência de telemetria mantém a última configuração estável
  ou devolve autoridade ao hospedeiro;
- `active` descreve a emissão de uma intenção aplicável, não a posse do atuador;
- todo efeito externo requer confirmação do executor e registro correlacionado.

## 4. Estratégia de execução holística

Os tickets são entregues em **fatias verticais**. Um ticket de algoritmo não é
considerado concluído isoladamente: deve possuir contrato, telemetria, testes e
evidência compatíveis. As ondas abaixo evitam criar primeiro todos os modelos e
somente depois descobrir que não podem ser observados ou comparados.

| Onda | Entrega integrada | Tickets de saída | Gate |
|---|---|---|---|
| 0 | baseline congelada, contratos e schemas | `EVO-001`–`EVO-004` | `NG0` |
| 1 | estimativa 0.2 observável e reproduzível | `EST-101`–`EST-105` | `NG1A` |
| 2 | FADA-HS 0.2 protegida pelo Sufferage | `HS-201`–`HS-204` | `NG1B` |
| 3 | Resource Controller recomendador | `RC-301`–`RC-305` | `NG1C` |
| 4 | replay e backtest pré-registrado | `VAL-401`–`VAL-403` | `NG2` |
| 5 | shadow real sem atuação | `SHD-501`–`SHD-503` | `NG3` |
| 6 | canário e produção, ambos condicionais | `OPS-601`–`OPS-603` | `NG4`/`NG5` |

`NG1A`, `NG1B` e `NG1C` formam juntos o gate determinístico `NG1`; a aprovação
de um ramo não promove os demais.

### Registro mestre dos tickets

| Ticket | Entrega | Dependências diretas | Estado inicial |
|---|---|---|---|
| `EVO-001` | baseline e rastreabilidade | — | `ready` |
| `EVO-002` | fronteiras e invariantes | `EVO-001` | `planned` |
| `EVO-003` | schemas versionados | `EVO-002` | `planned` |
| `EVO-004` | configuração e compatibilidade | `EVO-002`, `EVO-003` | `planned` |
| `EST-101` | observações e censura | `EVO-003` | `planned` |
| `EST-102` | estimador estratificado | `EST-101`, `EVO-004` | `planned` |
| `EST-103` | recência e drift | `EST-102` | `planned` |
| `EST-104` | incerteza e cauda | `EST-102`, `EST-103` | `planned` |
| `EST-105` | concorrência e vazão | `EST-101`, `EST-102`, `EVO-004` | `planned` |
| `HS-201` | candidata HS 0.2 | `EVO-002`, `EVO-004`, `EST-102` | `planned` |
| `HS-202` | faixa Sufferage | `HS-201`, `EST-104` | `planned` |
| `HS-203` | proteção pelo baseline | `HS-202`, `EST-104`, `EST-105` | `planned` |
| `HS-204` | cauda e encerramento | `HS-203`, `EST-104` | `planned` |
| `RC-301` | domínio de capacidade | `EVO-003`, `EVO-004` | `planned` |
| `RC-302` | objetivo de vazão | `RC-301`, `EST-104`, `EST-105` | `planned` |
| `RC-303` | histerese e cooldown | `RC-302` | `planned` |
| `RC-304` | modos fail-closed | `RC-303` | `planned` |
| `RC-305` | porta do executor | `RC-304` | `planned` |
| `VAL-401` | ledger de decisões | `EVO-003`, `HS-203`, `RC-304` | `planned` |
| `VAL-402` | replay adversarial | `EST-105`, `HS-204`, `RC-305`, `VAL-401` | `planned` |
| `VAL-403` | protocolo e backtest | `VAL-402`, `NG1` | `planned` |
| `SHD-501` | shadow genérico | `VAL-401`, `VAL-402` | `planned` |
| `SHD-502` | adaptador MVHSN endurecido | `SHD-501`, `RC-301` | `planned` |
| `SHD-503` | janela shadow real | `SHD-502`, `NG2` | `blocked` |
| `OPS-601` | contrato de canário | `NG3` | `blocked` |
| `OPS-602` | execução do canário | `OPS-601` | `blocked` |
| `OPS-603` | decisão de promoção | `OPS-602` | `blocked` |

O estado deste quadro somente muda junto com evidência e atualização do ticket
correspondente. Tickets bloqueados por autorização humana não podem ser marcados
`ready` por inferência técnica.

## 5. Contratos transversais obrigatórios

Todos os tickets devem respeitar simultaneamente:

- **Versionamento:** eventos registram versão de schema, política, estimador e RC.
- **Unidades:** duração em segundos, memória em bytes, temperatura em graus Celsius,
  frequência em hertz e capacidade como identificador de nível autorizado.
- **Tempo:** instante de observação, validade, origem e monotonicidade são explícitos.
- **Identidade:** máquina, slot, tarefa, decisão e execução usam IDs estáveis.
- **Correlação:** proposta FADA, proposta Sufferage, recomendação RC e resultado
  observado compartilham um `decision_id` ou `observation_id`.
- **Censura:** sucesso, falha, interrupção e limite de iterações não são misturados.
- **Incerteza:** ponto, intervalo/quantil, cobertura e método de calibração são
  registrados juntos.
- **Fail-closed:** dado obrigatório ausente, inválido, obsoleto ou incompatível
  gera fallback/advisory; nunca uma ação otimista implícita.
- **Reprodutibilidade:** configuração, seed, corpus, commit e hashes acompanham a
  evidência de validação.
- **Imutabilidade histórica:** resultados de 0.1 permanecem separados dos de 0.2.

## 6. Tickets

### Onda 0 — baseline, contratos e desenho integrado

#### EVO-001 — Congelar baseline e matriz de rastreabilidade

- **Objetivo:** registrar o que pertence a `fada-hs/0.1`, seus resultados e quais
  requisitos originam cada ticket novo.
- **Entregas:** `governanca/evolucao/FADA_EVO_TRACEABILITY_V1.md` e manifesto com
  hashes do G0, G1, G2, código 0.1 e resultado bruto.
- **Aceite:** todo requisito da solicitação aponta para pelo menos um ticket e um
  gate; nenhuma evidência histórica é modificada.
- **Dependências:** nenhuma.
- **Autoridade:** documentação e leitura local; não executa testes.
- **Rollback:** remover apenas os novos artefatos de rastreabilidade.

#### EVO-002 — Especificar fronteiras e invariantes 0.2/0.1

- **Objetivo:** separar formalmente FADA-HS, RC, adaptador, executor e governança.
- **Entregas:** `docs/FADA_HS_02_SPECIFICATION.md`,
  `docs/FADA_RESOURCE_CONTROLLER_01_SPECIFICATION.md` e atualização arquitetural.
- **Aceite:** modos, falhas, autoridade, não objetivos e invariantes são verificáveis;
  nenhuma equivalência científica é inferida pela FADA.
- **Dependências:** `EVO-001`.
- **Decisão humana:** semântica exata de `active` e autoridade do atuador.

#### EVO-003 — Versionar schemas de entrada e saída

- **Objetivo:** definir contratos estáveis antes dos algoritmos.
- **Entregas propostas:** `schemas/v1/task.json`, `machine_capability.json`,
  `telemetry_sample.json`, `duration_observation.json`, `hs_decision.json`,
  `capacity_recommendation.json` e `execution_feedback.json`.
- **Aceite:** schemas rejeitam IDs duplicados, unidades ambíguas, capacidades não
  autorizadas, telemetria obsoleta e backends não elegíveis.
- **Dependências:** `EVO-002`.
- **Integração:** todos os tickets seguintes consomem estes schemas.

#### EVO-004 — Definir configuração e compatibilidade

- **Objetivo:** retirar limites operacionais do código e preservar leitores 0.1.
- **Entregas propostas:** `src/fada/config.py`, exemplos em `configs/` e estratégia
  de migração de schema sem reescrever telemetria antiga.
- **Aceite:** limites por máquina, capacidades autorizadas, reserva de memória,
  histerese, intervalo mínimo e margens possuem validação e defaults conservadores.
- **Dependências:** `EVO-002`, `EVO-003`.
- **Decisão humana:** níveis de capacidade inicialmente permitidos por máquina.

### Onda 1 — estimador 0.2 completo e observável

#### EST-101 — Modelar observações válidas, falhas e censura

- **Objetivo:** preservar o significado de execuções concluídas, interrompidas,
  falhas e censuradas por limite.
- **Entregas propostas:** `src/fada/observations.py` e testes de contrato.
- **Aceite:** observações inválidas são rejeitadas; censura nunca entra como duração
  completa; motivo e limite de censura permanecem consultáveis.
- **Dependências:** `EVO-003`.

#### EST-102 — Estratificar cenário, máquina, backend e hardware

- **Objetivo:** substituir a chave mínima `(cenário, máquina)` por contexto
  versionado, preservando `ScenarioEstimator` como baseline.
- **Entregas:** novo estimador em módulo separado, sem alterar resultados de 0.1.
- **Aceite:** hierarquia de fallback explícita, cobertura mensurável e ausência de
  mistura entre backends ou precisões incompatíveis.
- **Dependências:** `EST-101`, `EVO-004`.

#### EST-103 — Incorporar recência, drift e atualização temporal

- **Objetivo:** responder a mudanças de desempenho sem oscilar por ruído.
- **Entregas:** política de janela/decaimento, detector de drift e eventos de troca
  de regime.
- **Aceite:** traces estacionários não geram falso drift acima do limite congelado;
  drift sintético conhecido é detectado dentro da janela pré-definida.
- **Dependências:** `EST-102`.

#### EST-104 — Calibrar incerteza, quantis e risco de cauda

- **Objetivo:** produzir ponto, intervalo e quantis úteis a HS e RC.
- **Entregas:** interface `DurationEstimate`, calibração temporal e métricas de
  cobertura, erro de ETA e pinball loss.
- **Aceite:** intervalos inválidos falham; calibração é avaliada fora da janela de
  ajuste; p50/p95 permanecem ordenados.
- **Dependências:** `EST-102`, `EST-103`.

#### EST-105 — Modelar interferência por concorrência

- **Objetivo:** estimar duração e vazão em função de workers ativos, topologia e
  pressão observada.
- **Entregas:** `src/fada/concurrency.py` e curva por máquina/backend/configuração.
- **Aceite:** extrapolação fora de níveis observados é marcada e não promove aumento;
  o máximo de workers nunca é tratado automaticamente como máxima vazão.
- **Dependências:** `EST-101`, `EST-102`, `EVO-004`.
- **Consumidores:** `HS-203`, `RC-302`, `VAL-402`.

### Onda 2 — FADA-HS 0.2 com proteção do baseline

#### HS-201 — Criar candidata isolada `fada-hs/0.2`

- **Objetivo:** introduzir uma implementação nova sem alterar a classe ou o
  comportamento de 0.1.
- **Entregas propostas:** `src/fada/policy_v02.py` e factory versionada.
- **Aceite:** 0.1 continua reproduzindo suas decisões e permanece disponível como
  comparador e rollback.
- **Dependências:** `EVO-002`, `EVO-004`, `EST-102`.

#### HS-202 — Aplicar Sufferage dentro de faixa de makespan

- **Objetivo:** tornar Sufferage efetivo sem somar grandezas incompatíveis.
- **Regra:** selecionar o melhor makespan; formar conjunto de alternativas dentro
  de uma margem configurada; ordenar esse conjunto por Sufferage e desempates
  determinísticos.
- **Aceite:** margem zero reproduz seleção estrita; unidades não são misturadas;
  casos discriminantes demonstram influência real do Sufferage.
- **Dependências:** `HS-201`, `EST-104`.

#### HS-203 — Implementar proteção comparativa pelo Sufferage

- **Objetivo:** calcular propostas FADA e Sufferage em toda decisão.
- **Regra:** usar a proposta FADA somente quando a vantagem estimada superar a
  margem de segurança considerando incerteza; caso contrário emitir Sufferage.
- **Aceite:** ausência de cobertura, intervalo inconclusivo ou inconsistência gera
  baseline/fallback; ambas as propostas permanecem na telemetria.
- **Dependências:** `HS-202`, `EST-104`, `EST-105`.

#### HS-204 — Tratar cauda e encerramento de campanha

- **Objetivo:** tornar o objetivo sensível ao p95, risco de tarefa longa e
  stragglers sem migrar ou cancelar trabalho iniciado.
- **Aceite:** estratégia de final de fila é explícita; nenhuma trajetória ativa é
  alterada; ganhos médios não ocultam regressão de cauda.
- **Dependências:** `HS-203`, `EST-104`.

### Onda 3 — Resource Controller consultivo e separado

#### RC-301 — Criar domínio de capacidade e máquina

- **Objetivo:** representar níveis autorizados, saúde, CPU/GPU, arquitetura,
  backend, memória, precisão, NUMA, runtime e slots.
- **Entregas propostas:** `src/fada/resource_domain.py` e validadores.
- **Aceite:** estado ausente/obsoleto impede aumento; nível recomendado pertence à
  lista autorizada; identidade de slot não é confundida com processo físico.
- **Dependências:** `EVO-003`, `EVO-004`.

#### RC-302 — Definir objetivo de vazão e segurança

- **Objetivo:** escolher capacidade por vazão agregada prevista, memória, swap,
  temperatura, frequência, erros e estabilidade.
- **Aceite:** objetivo, restrições e unidades são separados; nenhum score mistura
  unidades sem normalização documentada; reserva de memória é obrigatória.
- **Dependências:** `RC-301`, `EST-104`, `EST-105`.

#### RC-303 — Implementar janelas, histerese e cooldown

- **Objetivo:** ajustar lentamente e evitar oscilações.
- **Aceite:** janelas mínimas, ganho mínimo, histerese e intervalo entre mudanças
  são configuráveis; queda de capacidade afeta somente despachos futuros.
- **Dependências:** `RC-302`.

#### RC-304 — Implementar modos fail-closed

- **Objetivo:** criar máquina de estados `disabled`, `shadow`, `advisory`, `active`.
- **Aceite:** transições ilegais falham; reinício não promove modo; telemetria
  insuficiente mantém configuração estável; `active` não chama executor diretamente.
- **Dependências:** `RC-303`.

#### RC-305 — Definir porta do executor e confirmação

- **Objetivo:** separar recomendação de atuação por uma interface estreita.
- **Entregas propostas:** protocolo `CapacityActuator`, implementação `NoOp` e
  recibo de confirmação/rejeição do hospedeiro.
- **Aceite:** núcleo e Sentinela não possuem implementação produtiva; toda intenção
  tem idempotency key; timeout ou rejeição não altera estado assumido.
- **Dependências:** `RC-304`.
- **Autoridade:** apenas interfaces e `NoOp`; atuador real exige ticket hospedeiro.

### Onda 4 — telemetria, replay e validação offline

#### VAL-401 — Implementar ledger unificado por decisão

- **Objetivo:** registrar entradas, alternativas, decisão, capacidade, versões,
  fallback/rollback e feedback posterior.
- **Entregas propostas:** `src/fada/telemetry.py` e formato JSONL append-only.
- **Aceite:** escrita interrompida não produz evento válido parcial; segredos e
  payload científico não são copiados; correlação posterior é determinística.
- **Dependências:** `EVO-003`, `HS-203`, `RC-304`.

#### VAL-402 — Criar replay temporal e cenários adversariais

- **Objetivo:** reproduzir HS e RC sobre o mesmo snapshot sem efeito externo.
- **Cobertura:** drift, falha, censura, memória, swap, temperatura, telemetria
  obsoleta, interferência de concorrência, cauda e final de fila.
- **Aceite:** mesma entrada/configuração/seed produz decisões idênticas; políticas
  recebem exatamente os mesmos dados disponíveis no mesmo instante.
- **Dependências:** `EST-105`, `HS-204`, `RC-305`, `VAL-401`.

#### VAL-403 — Pré-registrar e executar novo backtest em fases separadas

- **Objetivo:** comparar FIFO, interleaved, Min-Min, Max-Min, Sufferage,
  `fada-hs/0.1` e `fada-hs/0.2`; avaliar RC separadamente por curva de vazão.
- **Fase A:** congelar corpus, seeds, métricas, tolerâncias, critérios, hashes e
  protocolo antes de observar o resultado confirmatório.
- **Fase B:** executar somente após autorização específica e registrar resultado
  imutável, inclusive quando não aprovado.
- **Métricas HS:** makespan médio/p95, ociosidade, ETA, cobertura, cauda, fallback e
  custo decisório.
- **Métricas RC:** throughput, tempo estável, oscilações, memória/swap, violações,
  tempo até rollback e ganho por nível de capacidade.
- **Dependências:** `VAL-402` e todos os subgates `NG1` aprovados.
- **Decisão humana:** critérios quantitativos finais antes da Fase B.

### Onda 5 — shadow genérico e integração hospedeira

#### SHD-501 — Criar adaptador shadow genérico

- **Objetivo:** consumir snapshots versionados sem conhecer banco ou fila concreta.
- **Aceite:** entrada somente leitura; saída é contrafactual; nenhum método de
  dispatch, lease, worker start/stop ou alteração de capacidade fica disponível.
- **Dependências:** `VAL-401`, `VAL-402`.

#### SHD-502 — Endurecer adaptador MVHSN sem tocar a campanha

- **Objetivo:** substituir constantes e leitura ad hoc por tradução validada para o
  contrato genérico.
- **Aceite:** teste com banco temporário prova igualdade byte/lógica da fila antes e
  depois; identidade da raiz é conferida; falha de schema encerra sem saída ativa.
- **Dependências:** `SHD-501`, `RC-301`.
- **Autoridade:** modificar o adaptador local é permitido em ticket próprio; acessar
  banco ou campanha MVHSN real exige autorização explícita separada.

#### SHD-503 — Executar janela shadow e adjudicar

- **Objetivo:** observar campanha autorizada sem influenciá-la e correlacionar
  decisões contrafactuais com resultados reais.
- **Aceite:** integridade da fila demonstrada; cobertura mínima e duração da janela
  pré-registradas; relatório separa previsão, contrafactual e fato observado.
- **Dependências:** `SHD-502`, `NG2` aprovado.
- **Autoridade:** bloqueado até autorização do responsável pelo hospedeiro.

### Onda 6 — canário reversível e produção

#### OPS-601 — Preparar contrato e runbook de canário

- **Objetivo:** delimitar uma máquina, níveis de capacidade, exposição, abortos,
  rollback e observabilidade.
- **Aceite:** nenhuma tarefa ativa é interrompida; executor hospedeiro conserva a
  decisão final; rollback e perda de telemetria são ensaiados fora da campanha.
- **Dependências:** `NG3` aprovado.
- **Decisão humana:** máquina, janela, limites e responsável pelo abort.

#### OPS-602 — Executar e adjudicar canário

- **Objetivo:** medir efeito causal limitado sem extrapolar para produção.
- **Aceite:** critérios congelados antes da execução; exposição respeitada; qualquer
  violação encerra o canário; resultado negativo também é preservado.
- **Dependências:** `OPS-601`.
- **Autoridade:** execução somente mediante autorização explícita contemporânea.

#### OPS-603 — Decidir promoção ou encerramento

- **Objetivo:** promover, manter experimental, revisar ou rejeitar cada componente
  independentemente.
- **Aceite:** decisão cita evidências `NG0`–`NG4`; HS e RC podem receber estados
  diferentes; produção possui rollback, monitoramento e responsável nomeado.
- **Dependências:** `OPS-602` aprovado.
- **Autoridade:** promoção produtiva exige autorização explícita do responsável.

## 7. Grafo de dependências resumido

```text
EVO-001 -> EVO-002 -> EVO-003 -> EVO-004
                         |          |
                         v          v
                      EST-101 -> EST-102 -> EST-103 -> EST-104
                                      \                  |
                                       +----> EST-105 <--+

EVO-004 + EST-102 -> HS-201 -> HS-202 -> HS-203 -> HS-204
EVO-003 + EVO-004 -> RC-301 -> RC-302 -> RC-303 -> RC-304 -> RC-305

HS-203 + RC-304 + EVO-003 -> VAL-401
EST-105 + HS-204 + RC-305 + VAL-401 -> VAL-402 -> VAL-403
VAL-401 + VAL-402 -> SHD-501 -> SHD-502 -> SHD-503
SHD-503 -> OPS-601 -> OPS-602 -> OPS-603
```

Nenhum atalho vertical é permitido: por exemplo, `RC-304` sem `EST-105` pode ser
testado deterministicamente, mas não pode alegar otimização de vazão; `HS-203`
sem `EST-104` pode existir como protótipo, mas não pode decidir vantagem com
incerteza; `SHD-503` sem `VAL-403` não inicia.

## 8. Gates de promoção da nova linha

| Gate | Escopo | Condição mínima | Não autoriza |
|---|---|---|---|
| `NG0` | contratos | rastreabilidade, invariantes e schemas revisados | implementação completa |
| `NG1A` | estimador | testes determinísticos e calibração temporal documentada | backtest confirmatório |
| `NG1B` | HS 0.2 | Sufferage, baseline guard, cauda e fallback cobertos | shadow real |
| `NG1C` | RC 0.1 | modos, histerese, níveis e `NoOp` cobertos | atuação em workers |
| `NG2` | offline | protocolo congelado e backtest aprovado | acesso a campanha |
| `NG3` | shadow | janela real somente leitura aprovada | canário |
| `NG4` | canário | exposição limitada aprovada e rollback demonstrado | produção geral |
| `NG5` | produção | decisão humana e runbook operacional | mutação científica |

Cada gate terá protocolo e resultado separados em `governanca/gates/`. Um gate
falho bloqueia seus descendentes, mas não apaga entregas úteis de outros ramos.

## 9. Estratégia de testes por ticket

Cada implementação deve acrescentar testes nas quatro camadas aplicáveis:

1. **Contrato:** schema, unidades, versões, IDs e rejeições.
2. **Determinismo:** invariantes, empates, fallback, estados e rollback.
3. **Integração isolada:** adaptadores e ledger usando apenas temporários/fixtures.
4. **Avaliação:** replay temporal, calibração e comparação pareada pré-registrada.

Casos negativos mínimos:

- telemetria ausente, atrasada, fora de unidade ou de outra máquina;
- backend/precisão não elegível;
- memória insuficiente, swap crescente ou saúde desconhecida;
- censura misturada indevidamente com conclusão;
- mudança de regime e quantis não calibrados;
- aumento de workers que reduz vazão;
- oscilação de capacidade e reinício durante cooldown;
- decisão FADA inconclusiva contra Sufferage;
- escrita parcial de telemetria e feedback duplicado;
- perda de confirmação do executor.

Comandos de testes permanecem bloqueados até autorização explícita. A criação do
teste não autoriza sua execução.

## 10. Evidência e definição global de pronto

Um ticket só está **concluído** quando:

- código, contrato, testes e documentação do mesmo incremento concordam;
- dependências estão concluídas ou a limitação está marcada como bloqueadora;
- arquivos e APIs afetados estão listados;
- há prova de que nenhum caminho produtivo foi ativado;
- evidência bruta fica em caminho exclusivo do projeto/worktree;
- resultado negativo é preservado com a mesma prioridade do positivo;
- Sentinela/mAI continuam operacionais, isolados e observacionais;
- revisão registra fatos, inferências, desconhecidos e fronteira causal;
- rollback remove somente o incremento, sem reescrever histórico.

Estados permitidos para tickets:

`planned -> ready -> in_progress -> implemented -> validated -> accepted`

Também são válidos `blocked`, `rejected` e `superseded`. `implemented` não
significa `validated`; `validated` não significa `promoted`.

## 11. Riscos e decisões humanas

| Tema | Risco | Mitigação | Decisão exigida |
|---|---|---|---|
| Critérios 0.2 | ajustar gate depois dos dados | pré-registro e hashes | limites quantitativos do `VAL-403` |
| Censura | viés de duração | estados separados e método documentado | modelo estatístico aceito |
| Concorrência | confundir correlação com causalidade | níveis controlados e replay pareado | níveis autorizados por máquina |
| Sensores | leituras ausentes ou não comparáveis | unidade/origem/validade e fail-closed | sensores obrigatórios por modo |
| Sufferage guard | baseline dominar sempre | medir taxa e motivo de guarda | margem de segurança |
| Active RC | recomendação virar comando implícito | porta estreita e confirmação hospedeira | autoridade e atuador concreto |
| MVHSN | interferência na campanha | fixtures antes de qualquer leitura real | acesso e janela shadow |
| Canário | regressão operacional | uma máquina, limites e abort automático | exposição e responsável |
| Licença | redistribuição ambígua | Apache-2.0 registrada no projeto | já decidida pelo responsável |

## 12. Ordem imediata recomendada

Sem executar testes nem tocar no MVHSN, a próxima sessão de implementação deve:

1. executar `EVO-001` e preservar os hashes da baseline;
2. elaborar conjuntamente `EVO-002` e `EVO-003`;
3. submeter as decisões humanas de schema, modos e níveis de capacidade;
4. somente então abrir `EVO-004`, `EST-101`, `HS-201` e `RC-301`;
5. manter cada incremento em `disabled`/`shadow` até seus gates próprios.

Esta ordem cria primeiro uma linguagem comum entre HS, RC, adaptadores,
telemetria e validação. Assim, os tickets podem avançar em paralelo quando suas
dependências estiverem satisfeitas, sem perder coerência sistêmica.
