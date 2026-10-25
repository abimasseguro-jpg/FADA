# Referências

## Biblioteca web curada

A curadoria ampla de literatura primária sobre escalonamento heterogêneo,
predição sob incerteza, censura e drift, controle de capacidade, fairness,
stragglers, traces e validação segura está em
[`BIBLIOTECA_WEB_FADA.md`](BIBLIOTECA_WEB_FADA.md).

Ela contém identificadores estáveis, prioridade de leitura, links oficiais/DOIs,
relevância específica para FADA-HS e FADA RC e ressalvas sobre mecanismos fora
do contrato atual. A biblioteca registra metadados e links; não redistribui PDFs.

## Pacote bibliográfico local

O pacote bibliográfico recebido permanece no arquivo-fonte abaixo para evitar a
duplicação de 54 MB de PDFs e preservar sua proveniência:

```text
/home/atilapcorreia/Downloads/125940731.tar
```

Conteúdo catalogado:

- estudo de Min-Min, Max-Min e Sufferage;
- *A revisit of fast greedy heuristics for mapping a class of independent tasks
  onto heterogeneous computing systems*;
- SACSDA;
- artigos sobre atribuição de tarefas independentes, balanceamento e heurísticas
  de escalonamento heterogêneo.

Uso no FADA-HS:

- Sufferage: prioridade para tarefa cuja segunda alternativa é muito pior;
- Max-Min/LPT: antecipação controlada das tarefas longas;
- Min-Min: baseline de vazão, não política única;
- busca local: avaliação offline e refinamento, não caminho crítico do despacho;
- horizonte limitado: custo decisório previsível em produção.

Antes de citar, os metadados bibliográficos devem ser conferidos diretamente nos
PDFs. O arquivo não é incorporado ao repositório para não misturar distribuição de
terceiros com o código.
