# Solicitação de evolução da FADA

> Esta solicitação foi operacionalizada em
> `docs/PROTOCOLO_EVOLUCAO_FADA_HS_RC_V1.md`, que preserva este documento como
> fonte e organiza a execução em tickets, dependências e gates.

Trabalhe no projeto `/home/atilapcorreia/ARTIGOS/FADA`.

Antes de qualquer alteração, leia o `AGENTS.md` aplicável, verifique o estado do
Sentinela/mAI e preserve integralmente a governança do projeto. Não altere
campanhas ativas, filas externas, resultados científicos ou projetos
hospedeiros sem autorização explícita.

## Objetivo geral

Quero evoluir a FADA de um coordenador/despachador de tarefas para um sistema
que também possa recomendar e, futuramente, controlar a capacidade
computacional de cada máquina. Essa nova capacidade deve permanecer
arquiteturalmente separada do núcleo de despacho.

A divisão desejada é:

1. **FADA-HS:** escolhe qual tarefa pendente deve ser enviada para qual slot
   elegível.
2. **FADA Resource Controller:** determina quantos slots/workers devem ficar
   ativos em cada máquina.
3. **Adaptador do projeto hospedeiro:** traduz fila, tarefas, telemetria e
   capacidades.
4. **Executor hospedeiro:** conserva a autoridade para iniciar workers,
   conceder leases e executar tarefas.
5. **Sentinela/mAI:** permanecem observacionais e não comandam campanhas.

## Estado que deve ser preservado

A versão `fada-hs/0.1` permanece experimental. O G2 existente foi executado e
não aprovado:

- makespan médio da FADA: 647,711;
- makespan médio do Sufferage: 637,728;
- makespan p95 da FADA: 844,571;
- makespan p95 do Sufferage: 761,973;
- razão p95: 1,1084;
- custo decisório p95: 4,704 ms.

Não apague, substitua ou reinterprete esse resultado. Qualquer evolução deverá
receber uma nova versão e um novo protocolo pré-registrado.

## Recomendações prioritárias

### 1. Criar uma nova versão candidata

Criar uma versão candidata, como `fada-hs/0.2`, sem modificar retroativamente
o contrato ou as evidências da versão 0.1.

### 2. Melhorar o estimador de duração

O estimador deve passar a considerar:

- cenário;
- máquina;
- backend;
- configuração de hardware;
- quantidade de workers ativos;
- observações recentes;
- mudança temporal de desempenho;
- incerteza calibrada;
- execuções interrompidas, com falha ou censuradas por limite de iterações.

O estimador atual, baseado principalmente em medianas históricas, deve
continuar disponível como baseline.

### 3. Tornar o Sufferage parte efetiva da decisão

Atualmente, o Sufferage funciona apenas como desempate. Como empates exatos de
makespan são raros, sua influência prática pode ser pequena.

Implemente e teste uma política em que:

1. seja encontrada a melhor decisão por makespan previsto;
2. sejam mantidas as alternativas dentro de uma margem configurável;
3. entre essas alternativas, seja priorizada a tarefa com maior Sufferage.

Não misture grandezas com unidades diferentes sem normalização ou uma regra
lexicográfica explícita.

### 4. Criar uma proteção pelo baseline

A cada decisão, calcular:

- alternativa proposta pela FADA;
- alternativa proposta pelo Sufferage;
- diferença prevista;
- incerteza dessa diferença.

Se a vantagem estimada da FADA não superar uma margem de segurança
configurável, usar o Sufferage. Essa proteção deve ser testável e totalmente
registrada na telemetria.

### 5. Criar o FADA Resource Controller como componente separado

Esse controlador deverá ajustar lentamente a quantidade de workers/slots
ativos. Para cargas como MomEng CPU, o parâmetro principal é a quantidade de
processos R simultâneos, mantendo inicialmente uma thread BLAS por processo.

O controlador deverá:

- trabalhar somente com níveis de capacidade previamente autorizados;
- observar vazão, memória, swap, temperatura, frequência, erros e estabilidade;
- usar janelas mínimas de observação;
- possuir histerese para evitar oscilações;
- nunca interromper tarefas em execução;
- alterar apenas a disponibilidade para despachos futuros;
- voltar à última configuração estável quando necessário;
- funcionar nos modos `disabled`, `shadow`, `advisory` e `active`;
- falhar de maneira segura quando faltar telemetria.

O número de workers não deve ser fixado no código. Limites, margem mínima de
ganho, reserva de memória e intervalo entre ajustes devem ser configuráveis por
máquina.

### 6. Incorporar concorrência ao modelo de desempenho

A duração prevista de uma tarefa deve depender também do número de workers
ativos, pois aumentar a concorrência pode provocar disputa por cache, memória,
NUMA e largura de banda.

O controlador deve buscar a maior vazão agregada, e não simplesmente o maior
número de processos.

### 7. Criar um modelo de capacidades e requisitos

As máquinas devem poder declarar:

- CPU ou GPU;
- arquitetura;
- backend;
- memória;
- precisão suportada;
- topologia NUMA;
- quantidade de slots;
- versões relevantes do runtime;
- estado de saúde.

As tarefas devem declarar:

- backends permitidos;
- memória mínima;
- precisão necessária;
- dimensão ou classe de complexidade;
- requisitos científicos;
- política de fallback.

A FADA deve respeitar a elegibilidade recebida. Ela não pode concluir sozinha
que dois backends são cientificamente equivalentes.

### 8. Melhorar o tratamento da cauda

Adicionar e avaliar:

- estimativas por quantis;
- risco de tarefa longa;
- objetivo sensível ao p95;
- detecção de stragglers;
- estratégia específica para o final da campanha;
- ETA com intervalo de confiança.

Não implementar migração ou cancelamento automático de trajetórias já
iniciadas.

### 9. Ampliar a telemetria por decisão

Registrar:

- tarefas e slots considerados;
- estimativas e incertezas;
- decisão FADA;
- decisão Sufferage;
- motivo da escolha;
- configuração de workers;
- duração posteriormente observada;
- erro da previsão;
- versão da política;
- versão do estimador;
- fallback ou rollback ocorrido.

### 10. Fortalecer o shadow mode

A FADA deve conseguir observar uma campanha sem alterá-la, produzir decisões
contrafactuais e comparar posteriormente:

- previsão contra duração observada;
- decisão FADA contra decisão real;
- resultado por cenário e máquina;
- makespan, p95, ociosidade e ETA;
- comportamento sob falhas e drift.

## Validação obrigatória

Organize a evolução em etapas:

1. especificação formal e invariantes;
2. testes determinísticos;
3. novo backtest temporal pré-registrado;
4. shadow mode;
5. canário reversível em uma única máquina;
6. produção somente após aprovação explícita.

O novo backtest deve comparar pelo menos:

- FIFO;
- interleaved;
- Min-Min;
- Max-Min;
- Sufferage;
- `fada-hs/0.1`;
- nova política candidata.

Preserve o G2 anterior como evidência histórica. Não ajuste critérios depois de
observar os novos resultados.

## Primeira entrega solicitada

Antes de implementar toda a expansão:

1. inspecione o código e a governança atuais;
2. identifique quais capacidades já existem;
3. apresente uma arquitetura proposta;
4. divida o trabalho em incrementos pequenos e reversíveis;
5. indique os arquivos que seriam criados ou modificados;
6. defina testes e critérios de aceitação;
7. aponte riscos, incompatibilidades e decisões que exigem autorização humana.

Não toque na campanha MVHSN ativa. Comece pelo núcleo genérico da FADA, por
testes isolados e pelo shadow mode.
