# Relatório de conclusões — escalonamento dinâmico de tarefas

**Data:** 06/08/2026  
**Projeto:** MVHSN  
**Base analisada:** `equacao_escalonamento_dinamico.md` e comportamento da fila ECM distribuída

## 1. Objetivo

Avaliar a equação proposta para decisão dinâmica de tarefas e definir uma versão operacional mais adequada à campanha MVHSN.

## 2. Conclusão principal

A formulação original é matematicamente consistente como modelo de minimização do *makespan*. Ela melhora a política baseada somente em médias históricas porque considera simultaneamente tarefas pendentes, tarefas em execução, velocidade dos recursos e a possibilidade de aguardar.

Entretanto, a formulação exata não deve ser aplicada diretamente a cada evento da fila. O problema de alocação heterogênea é computacionalmente caro e a previsão de custo não pode ser tratada como determinística.

A recomendação é utilizar um escalonador aproximado, orientado a eventos e com horizonte móvel.

## 3. Melhorias recomendadas

### 3.1 Unidade de escalonamento

Cada worker deve ser tratado como um slot independente. Modelar apenas a máquina inteira perde a informação de que local, WSL e bot possuem múltiplos workers concorrentes.

### 3.2 Custo por cenário

O custo deve ser estimado separadamente para `ecm_n50`, `ecm_n100`, `ecm_n200` e `ecm_n400`. O número da amostra, o número de iterações ECM, fallbacks do E-step e tempos parciais devem alimentar essa estimativa.

### 3.3 Aprendizagem online

Os tempos observados devem atualizar continuamente o custo previsto, preferencialmente usando mediana ou média aparada para evitar que tarefas anômalas distorçam o modelo.

### 3.4 Horizonte de candidatos

Em vez de otimizar as centenas de tarefas restantes em cada decisão, o escalonador deve avaliar uma janela limitada de candidatos, priorizando tarefas mais pesadas e cenários sub-representados.

### 3.5 Decisão de espera

A máquina livre poderá aguardar apenas quando a previsão indicar ganho superior a uma margem de segurança. Diferenças menores que o erro de previsão devem ser consideradas empate.

### 3.6 Fallback seguro

Quando não houver observações suficientes, o sistema deve retornar à política atual de retirada dinâmica, sem bloquear a fila por falta de estimativas.

## 4. Modelo operacional recomendado

Para cada worker `s` e tarefa `i`, usar:

\[
\widehat p_{is} = \frac{\widehat C_{k_i}m_i}{v_s}
\]

onde `k_i` é o cenário da tarefa, `m_i` é o fator de complexidade observado e `v_s` é a velocidade estimada do worker.

Para cada candidato, simular a distribuição das tarefas restantes por uma heurística de lista e calcular o término previsto:

\[
\widehat T_{i\rightarrow s}=\max_r L_r'
\]

A tarefa escolhida é a que produz o menor término previsto, desde que o ganho supere a margem de segurança.

## 5. O que foi deliberadamente excluído

Temperatura, clock e carga térmica não fazem parte desta versão do modelo, conforme decisão do projeto. A velocidade será inferida apenas pelo histórico de execução e pela capacidade observada de cada worker.

## 6. Riscos remanescentes

- erro elevado no início da campanha, antes de existirem medições suficientes;
- variação de custo entre tarefas do mesmo cenário;
- sobrecarga da simulação do escalonador;
- possibilidade de decisões instáveis sem margem de segurança;
- necessidade de distinguir tarefas em execução de tarefas apenas alugadas;
- dificuldade de comparar ganhos se houver reexecuções ou leases expirados.

## 7. Plano de validação

Antes de ativar o modelo na fila de produção, recomenda-se um backtest com o histórico da campanha atual, comparando:

- tempo total de conclusão (*makespan*);
- erro da ETA ao longo da execução;
- tempo ocioso dos workers;
- vazão por máquina e por cenário;
- equilíbrio entre os quatro tamanhos de amostra;
- número de reatribuições, falhas e leases expirados.

Não é possível afirmar um percentual de ganho sem esse backtest. A conclusão disponível neste momento é de adequação estrutural do modelo, não de superioridade experimental já demonstrada.

## 8. Parecer final

O estudo deve ser aprovado como base para evolução do escalonador, mas não como implementação exata de produção. A versão recomendada é uma heurística adaptativa por worker, cenário e custo aprendido, com janela de candidatos, margem de segurança e fallback para a fila atual.

Essa abordagem preserva a robustez operacional da campanha e permite medir o ganho real antes de alterar o comportamento do coordenador.
