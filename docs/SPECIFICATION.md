# Especificação FADA-HS 0.1

## Objetivo

Minimizar o término previsto da fila (*makespan*) em recursos heterogêneos, com
decisões reversíveis, incerteza explícita e fallback seguro.

Para uma tarefa `i`, cenário `k_i` e slot `s`:

```text
p_hat(i,s) = C_hat(k_i,s) * m_i
```

Quando o custo disponível é independente da máquina:

```text
p_hat(i,s) = C_hat(k_i) * m_i / v_s
```

Cada estimativa é transformada de maneira uniforme para incorporar incerteza:

```text
p_robusto(i,s) = p_hat(i,s) * [1 + lambda * (1 - confianca(i,s))]
```

Para cada atribuição elegível, a FADA adiciona `p_robusto(i,s)` à carga do slot
escolhido e simula uma lista gulosa das tarefas restantes, também usando
`p_robusto`. O objetivo robusto de referência é:

```text
J(i,s) = max_r L'_r
```

A aplicação uniforme é obrigatória: penalizar apenas a atribuição focal cria
contrafactuais assimétricos. A decisão minimiza `J`. Sufferage — diferença entre
os dois melhores términos de uma tarefa — desempata a favor de tarefas com poucas
alternativas boas; confiança, identificador da tarefa e identificador do slot
completam o desempate determinístico, nessa ordem.

## Decisão de esperar

`J_espera` deve ser calculado pelo adaptador sobre o mesmo conjunto de tarefas,
slots, estimativas, transformação de incerteza e horizonte de `J`, alterando
somente a disponibilidade futura que motiva a espera. Esperar é permitido apenas
quando `J - J_espera > epsilon`; igualdade e ganhos dentro da margem despacham
imediatamente. Na ausência de um contrafactual mensurável, a política não espera.

## Invariantes

1. tarefa já alugada não é migrada;
2. tarefa só pode ir para slot elegível e habilitado;
3. ausência de estimativa aciona fallback, nunca bloqueio indefinido;
4. toda decisão registra versão, entradas, previsão, confiança, motivo e resultado;
5. política não altera dados científicos nem o conteúdo da tarefa;
6. rollback retorna à política anterior sem reescrever tarefas concluídas;
7. janela de candidatos e horizonte de projeção são limitados.
8. identificadores duplicados de tarefa ou slot acionam fallback;
9. uma versão promovida preserva a versão imediatamente anterior para rollback.

## Fallback, promoção e rollback

`fallback` é uma decisão explícita que devolve autoridade ao escalonador seguro do
projeto hospedeiro. Ele é acionado para fila/pool vazio, ausência ou cobertura
parcial de estimativas, ausência de atribuição elegível e identificadores
duplicados. FADA não implementa implicitamente o algoritmo hospedeiro.

Promoção troca somente a versão ativa para decisões futuras. Rollback restaura a
versão imediatamente anterior e não migra, cancela nem reescreve tarefas já
alugadas ou concluídas. Sem versão anterior, rollback falha explicitamente.

## Limites e justiça

`candidate_window` limita as tarefas candidatas e `projection_limit` limita o
horizonte simulado. Prioridade é ordenada primeiro; duração prevista decrescente
e identificador completam a seleção determinística. O adaptador hospedeiro deve
converter envelhecimento de fila em prioridade monotônica quando houver risco de
starvation e registrar essa entrada na telemetria.

## Cold start e aprendizagem

- preferir mediana por `(cenário, máquina)`;
- usar mediana do cenário ajustada pela velocidade apenas como segundo nível;
- usar prior explícito apenas quando configurado;
- reduzir a confiança em cada fallback;
- atualizar o estimador somente com execuções válidas e identificadas.

## Fora do escopo da versão 0.1

Temperatura, migração/preempção, alteração automática do número de threads e
otimização exata global.
