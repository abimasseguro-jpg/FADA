# Análise exclusiva da FADA-MVHSN — pacote compacto

Não analisar a campanha atual. Avaliar somente o modelo geral.

## Fórmula

Para tarefa $i$ e worker $s$:

```text
p_hat(i,s) = C_hat(k_i) * m_i / v_s
```

`C_hat(k_i)` é o custo aprendido da classe/cenário; `m_i` é a complexidade observada; `v_s` é a velocidade histórica do worker.

Para cada possível atribuição:

```text
T_hat(i -> s) = max_r L'_r
```

`L'_r` é a carga prevista de cada worker após a atribuição e uma redistribuição gulosa das tarefas restantes.

Escolher a atribuição que minimiza `T_hat`. Aguardar somente quando esperar for melhor que a melhor atribuição por margem `epsilon`.

## Desenho

O fluxo é: atualizar estado; estimar custos por cenário; estimar velocidade por worker; selecionar janela de candidatos; simular atribuições; calcular makespan; comparar com epsilon; despachar ou aguardar; registrar o tempo observado.

## Melhorias propostas

- tratar cada worker como slot independente;
- diferenciar n50, n100, n200 e n400;
- atualizar custos por mediana ou média aparada;
- usar fallback quando faltarem amostras;
- limitar a busca a uma janela de candidatos;
- registrar previsão, resultado, erro, decisão e motivo;
- manter shadow mode antes da promoção;
- comparar contra FIFO, round-robin e menor carga;
- exigir rollback e gates quantitativos.

## Pergunta à mAI

A FADA é matematicamente consistente, estável, escalável e justificável como política geral de escalonamento heterogêneo? Identificar hipóteses, contraexemplos, riscos, alternativas e testes de falsificação. Emitir conclusão e sugestões exclusivamente sobre a FADA, sem analisar ou recomendar alterações na campanha atual.
