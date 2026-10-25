# Protocolo de integração autônoma — FADA + MomEng CPU Linux v1

- **Identificador:** `FADA-MOMENG-CPU-ACTIVE-V1`
- **Estado:** planejado; não autoriza execução, alteração de campanha ou acesso
  ao projeto hospedeiro.
- **Objetivo:** permitir que o FADA proponha e, somente depois dos gates e da
  autorização do responsável, faça o MomEng CPU Linux aplicar decisões de
  despacho e de capacidade de forma reversível e auditável.
- **Relação com o protocolo de evolução:** este documento detalha a integração
  hospedeira prevista por `FADA-EVO-HS02-RC01-V1`; não reclassifica o G2
  histórico, nem amplia a homologação CPU em shadow já obtida.

## 1. Resultado que buscamos

O sistema final terá duas decisões separadas:

1. **Despacho (FADA-HS):** qual tarefa pendente, elegível e ainda não iniciada
   será atribuída ao próximo slot livre do MomEng.
2. **Capacidade (FADA-RC):** quantos workers/threads autorizados o executor
   MomEng deve manter para novas tarefas em cada máquina CPU.

O FADA não executará tarefas científicas, não editará resultados e não matará
tarefas em andamento. O MomEng CPU Linux continuará dono da fila, dos processos,
dos recibos de aplicação e do rollback. Sentinela e mAI apenas observam,
validam e registram evidências.

## 2. Arquitetura e contrato de autoridade

```text
snapshot/telemetria MomEng (leitura) --> adaptador MomEng --> FADA-HS + FADA-RC
                                                         |              |
                                             intenção de despacho   intenção de capacidade
                                                         \              /
                                                     outbox assinada/versionada
                                                               |
                                                         executor MomEng
                                                               |
                                               recibo idempotente + estado observado
                                                               |
                                                    ledger FADA / Sentinela
```

Regras invariáveis:

- O adaptador de leitura não pode iniciar processo, gravar fila ou conceder
  lease.
- A única fronteira mutante é um atuador implementado **no MomEng CPU Linux**;
  o núcleo FADA mantém `NoOpCapacityActuator` como default.
- Toda intenção possui `run_id`, versão de política/configuração, versão do
  schema, chave de idempotência, validade curta e motivo verificável.
- O executor só aceita uma intenção se a tarefa ainda estiver pendente, o slot
  continuar elegível e a configuração da máquina corresponder ao snapshot.
- Um recibo aceito, rejeitado ou expirado é obrigatório. Sem recibo, o FADA
  conserva o estado observado anterior e falha fechado.
- Reduzir threads só impede novos inícios; nunca interrompe uma tarefa científica
  já iniciada. Aumentos respeitam o teto autorizado pelo hospedeiro.
- A configuração segura por máquina — afinidade, memória reservada, máximos de
  threads, temperaturas e cooldown — pertence ao MomEng, é versionada e não tem
  default implícito no FADA.

## 3. Escopo e exclusões v1

Inclui uma instalação CPU Linux indicada pelo responsável, uma fila/manifesto
local do MomEng, workers CPU explicitamente declarados e aplicação reversível de
despacho e de contagem de threads.

Ficam fora desta versão: GPU, alteração de clock/governor/BIOS, afinidade NUMA
automática, preempção, migração de tarefas, alteração de dados científicos,
várias máquinas sem inventário homologado e qualquer fila/campanha não declarada
no protocolo específico de execução.

## 4. Fases e gates

| Fase | Entrega verificável | Critério de passagem | Não autoriza |
|---|---|---|---|
| `MC0` — descoberta | raiz canônica do MomEng, formato de fila, ciclo de vida de worker, inventário CPU e dono operacional documentados | contrato de integração e matriz de autoridade aprovados pelo responsável | acesso mutante |
| `MC1` — contratos | schemas de snapshot, intenção de despacho, intenção de capacidade e recibo; outbox local e idempotência | rejeições determinísticas para versões/unidades/estado inválidos | iniciar workers |
| `MC2` — adaptador isolado | leitor MomEng e atuador de fixture em diretório temporário | provas de nenhuma escrita pelo leitor; duplicata, expiração e conflito rejeitados | campanha real |
| `MC3` — replay offline | traces congelados e comparação FADA versus baseline do MomEng | protocolo pré-registrado; sem regressão além do limite humano definido | shadow ao vivo |
| `MC4` — shadow | FADA emite intenções, executor apenas simula e devolve recibos `would_apply` | consistência de snapshots, recibos e rollback em janela pré-registrada | aplicação |
| `MC5` — canário reversível | uma máquina CPU, teto baixo de exposição e kill switch do MomEng | aprovação explícita para essa máquina e evidência de rollback | ampliação |
| `MC6` — operação controlada | runbook, alarmes, métricas e revisão pós-canário | decisão humana documentada para ampliar escopo | produção irrestrita |

Cada fase requer protocolo e resultado próprios em `governanca/gates/`. Uma falha
bloqueia descendentes e preserva suas evidências; não pode ser contornada por
homologação CPU anterior ou por resultado sintético.

## 5. Critérios técnicos obrigatórios

### Despacho

- somente tarefas pendentes e slots explicitamente elegíveis;
- comparação com baseline do MomEng registrada para cada intenção;
- decisão inconclusiva, telemetria ausente ou estimativa insuficiente devolve a
  decisão ao baseline do hospedeiro;
- a atribuição é atômica no MomEng: uma tarefa não pode receber dois leases;
- a confirmação inclui IDs de tarefa, slot, lease e versão do snapshot.

### Threads/workers

- níveis discretos e previamente autorizados por máquina, incluindo `0` apenas
  se o MomEng suportar pausa segura de novos inícios;
- aumentos um degrau por vez e somente após cooldown, telemetria válida e margem
  de vazão configurada;
- temperatura, memória, swap, taxa de erro, perda de heartbeat ou telemetria
  obsoleta permitem apenas manter/reduzir a capacidade;
- cada alteração recebe confirmação do número de processos/threads observado;
- discrepância entre pedido e estado observado suspende novas alterações até
  reconciliação humana ou rollback confirmado.

## 6. Segurança operacional e rollback

O MomEng oferece um `kill switch` local, independente do FADA, que desabilita a
leitura da outbox e retoma sua política/configuração estável. O rollback é:

1. bloquear novas intenções FADA;
2. preservar tarefas em execução e seus resultados;
3. retornar o limite de novos workers ao último nível confirmado;
4. processar somente a política nativa do MomEng para novas tarefas;
5. registrar causa, snapshots, intenções pendentes e recibos finais.

Condições de parada automática no canário: falha de integridade da fila, recibo
ausente/ambíguo, duplicidade de lease, regressão além do limite pré-registrado,
telemetria sem origem confiável ou qualquer erro do atuador. A parada não apaga
evidência nem tenta reexecutar uma tarefa.

## 7. Métricas e evidências

Cada gate mede, contra baseline e por janela temporal: vazão, tempo de espera,
makespan, p95, ociosidade, taxa de erro, uso de memória/swap, temperatura,
tempo de decisão, intenções emitidas/aceitas/rejeitadas/expiradas e tempo de
rollback. Métricas científicas do MomEng são observadas separadamente e não são
prova de ganho do escalonador.

Evidência bruta deve incluir hashes de configuração, snapshots imutáveis, ledger
de intenções e recibos, logs do executor e versões de código. Ela fica isolada
por `project_id`, `run_id` e worktree. Resultados negativos têm o mesmo status
de preservação que resultados positivos.

## 8. Decisões humanas necessárias antes de começar a implementação

1. Informar a raiz canônica e o `AGENTS.md` do `momeng_cpu_linux`.
2. Nomear o responsável pela fila/executor e a máquina CPU inicial do canário.
3. Aprovar os níveis de threads permitidos, limites de memória/temperatura e
   política de rollback dessa máquina.
4. Definir baseline MomEng, limites quantitativos de regressão e duração do
   shadow/canário.
5. Autorizar separadamente: implementação no projeto MomEng, execução dos
   testes, janela shadow e, por último, aplicação no canário.

## 9. Próximo incremento autorizado por este protocolo

Antes de qualquer acesso ao MomEng, abrir `MC0`: produzir uma matriz de
interface e autoridade baseada somente na inspeção do checkout indicado. Nenhum
comando de campanha, worker, fila, serviço ou teste é parte deste incremento.
