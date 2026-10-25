# FADA Resource Controller 0.1

## Escopo

O Resource Controller é um recomendador puro, separado da política FADA-HS e do
executor hospedeiro. Ele recebe níveis de capacidade previamente autorizados e
telemetria por máquina e devolve uma recomendação. Não cria ou interrompe
workers, não muda frequência de CPU, não concede leases e não toca em tarefas
em execução.

Cada nível autorizado identifica explicitamente:

- número de workers/threads de campanha;
- clock máximo solicitado ao executor hospedeiro, em hertz.

Não existem limites operacionais globais codificados no controlador. Cada
máquina fornece seus próprios níveis, limites térmicos, reserva de memória,
swap permitido, taxa de erro, janela, cooldown e ganho mínimo.

## Objetivo e comparação entre threads e clock

A variável otimizada é a mediana da vazão agregada observada, em tarefas por
segundo. Temperatura, memória, swap, erros e estabilidade são restrições; suas
unidades não são somadas à vazão.

Quando a temperatura alcança o nível de atenção, o controlador compara duas
reduções adjacentes, quando ambas foram autorizadas:

1. menos workers com o mesmo clock;
2. clock menor com o mesmo número de workers.

Se ambas possuem observações suficientes e seguras, vence a de maior vazão. Em
empate, vence o maior clock e depois o menor número de workers. Sem evidência
comparável, o fallback conservador reduz primeiro os workers e conserva o clock.
Isso implementa a preferência pelo clock mais alto sem transformá-la em regra
absoluta contra evidência de desempenho.

Para evitar que ruído pareça ganho, cada nível recebe uma faixa robusta:

```text
centro = mediana(vazão)
erro_robusto = 1,4826 * MAD(vazão) / sqrt(n)
faixa = centro +/- multiplicador * erro_robusto
```

Uma troca por desempenho exige que o limite inferior do candidato supere o
limite superior do nível atual pela margem configurada. Essa faixa é uma
proteção heurística contra dispersão, não um intervalo estatístico calibrado;
calibração temporal permanece necessária antes de qualquer promoção.

Temperatura crítica ignora cooldown e seleciona o nível autorizado de menor
proxy `workers * clock`. Esse produto serve somente para ordenar reduções de
emergência; não é estimativa de potência nem entra no objetivo de desempenho.
Reduções por temperatura de atenção, memória, swap, erro ou instabilidade também
têm precedência sobre o cooldown; o cooldown bloqueia apenas ajustes de
otimização depois que as restrições voltaram ao estado seguro.

Quando configurado, o limite de aquecimento usa a diferença entre as duas
observações mais recentes do mesmo nível, em graus Celsius por segundo. A
indicação explícita de thermal throttling também força somente redução. Não se
calcula taxa atravessando uma mudança de nível, pois isso confundiria regimes.
Quando esse limite foi habilitado, a ausência de duas observações comparáveis
bloqueia adaptações de desempenho, embora reduções por outros sinais continuem
permitidas.

## Segurança e adaptação gradual

- aumento por desempenho exige amostras suficientes do nível atual e do nível
  candidato;
- nível não observado nunca é promovido por extrapolação;
- cada recomendação normal avança no máximo um nível ordenado de capacidade;
- cooldown e histerese térmica impedem oscilações rápidas;
- pressão de memória, swap, erros ou instabilidade permite somente redução;
- telemetria ausente, obsoleta, inconsistente ou de outra máquina gera fallback;
- redução altera apenas a capacidade oferecida para despachos futuros; tarefas
  já iniciadas não pertencem à interface do controlador.

## Modos

- `disabled`: mantém a configuração e não requer telemetria;
- `shadow`: calcula contrafactuais, mas `apply_allowed` é sempre falso;
- `advisory`: publica recomendação humana, mas não autoriza aplicação;
- `active`: marca uma mudança segura como aplicável pelo hospedeiro, sem executá-la.

O núcleo nunca chama `CapacityActuator`. A interface existe para integração do
hospedeiro e sua única implementação no FADA é `NoOpCapacityActuator`, que rejeita
toda solicitação. Um atuador real, inclusive para clock, exige autorização e
implementação no projeto hospedeiro.

## Evidência e confirmação

Toda recomendação contém a observação causal, versão `fada-rc/0.1`, confiança,
motivo e chave de idempotência determinística. O estado efetivo continua sendo o
informado pelo hospedeiro; recomendação sem recibo aceito não altera o nível
assumido.

## Configuração, schemas e replay

O carregador estrito está em `src/fada/config.py`; exemplos permanecem em
`configs/` e nunca constituem defaults de produção. Os contratos JSON versionados
estão em `schemas/v1/` para configuração, amostra de telemetria e recomendação.
Campos desconhecidos, versões incompatíveis e unidades ambíguas falham fechados.

`replay_resource_telemetry` processa amostras em ordem de evento e entrega a cada
decisão somente o prefixo já observado, impedindo vazamento do futuro. O replay
é puramente local: não possui porta de dispatch nem chama `CapacityActuator`.

## Limites desta versão

O controlador não descobre níveis seguros, não faz overclock, não controla BIOS,
governador do sistema ou afinidade NUMA e não alega causalidade a partir de
telemetria observacional. Exploração controlada, sensores específicos e atuador
real ficam para integração e validação posteriores.
