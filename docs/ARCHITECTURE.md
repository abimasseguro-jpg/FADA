# Arquitetura

```text
fila do projeto
     |
     v
adaptador ---------> estado normalizado (tarefas, slots, observações)
                          |
                          v
                   estimador robusto
                          |
                          v
                 política FADA-HS pura
                          |
             +------------+-------------+
             |                          |
          decisão                    telemetria
             |
             v
executor do projeto (dispatch, wait ou fallback)
```

O núcleo não abre bancos, não chama SSH e não altera filas. O adaptador traduz o
projeto hospedeiro para o domínio FADA; o executor conserva a autoridade sobre a
produção. Isso permite testar a mesma política com traces sintéticos, históricos
ou filas reais em *shadow mode*.

## Controle adaptativo de recursos

```text
telemetria por máquina + níveis (threads, clock) autorizados
                         |
                         v
              Resource Controller puro
                 /              \
        recomendação        evidência/motivo
                 |
                 v
      porta do executor hospedeiro
                 |
        NoOp no núcleo FADA
```

O Resource Controller 0.1 maximiza vazão sustentável sob limites separados de
temperatura, memória, swap, erros e estabilidade. Ele recomenda capacidade para
despachos futuros, mas não possui acesso a workers, filas ou controles de clock.
Configuração estrita e schemas versionados alimentam o controlador. O replay
temporal reutiliza a mesma política, expondo somente o prefixo de telemetria
disponível em cada instante e produzindo recomendações contrafactuais.
Os contratos e invariantes estão em
[`FADA_RESOURCE_CONTROLLER_01_SPECIFICATION.md`](FADA_RESOURCE_CONTROLLER_01_SPECIFICATION.md).
