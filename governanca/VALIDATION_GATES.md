# Gates de validação e promoção

Cada gate só pode ser marcado como concluído por um artefato reproduzível em
`governanca/gates/`. A aprovação de um gate não implica aprovação dos seguintes.

Estado em 2026-08-08: G0 e G1 concluídos; G2 executado e não aprovado; G3–G5
não iniciados.

Estado adicional em 2026-09-04: a trilha independente de execução CPU offline
foi homologada. Ela não altera nem contorna a reprovação histórica de G2.

## CPU-H1 — execução CPU offline

**Estado:** concluído —
`governanca/gates/CPU_HOMOLOGATION_RESULT_2026-09-04.md`.

- protocolo congelado antes da execução;
- 51 testes determinísticos aprovados;
- 15 rodadas multiprocesso concluídas com digests reproduzíveis;
- aceleração observada de 3,54×, acima do limiar de 1,20×;
- nenhum acesso a GPU, fila, atuador ou configuração produtiva.

O gate homologa somente o núcleo CPU offline/observacional no ambiente registrado.
GPU, carga científica, segurança térmica, shadow real, canário e produção não são
herdados desta aprovação.

## CPU-SH1 — shadow CPU sobre snapshot de campanha GPU

**Estado:** concluído —
`governanca/gates/CPU_CAMPAIGN_SHADOW_RESULT_2026-09-04.md`.

- execução isolada no nó CPU `aces`;
- 52 testes determinísticos aprovados;
- snapshot real preservado byte a byte durante a análise;
- elegibilidade GPU obrigatória e inventário CUDA/HIP validados;
- recomendação contrafactual produzida sem fila, worker, lease ou GPU;
- Sentinela/mAI próprias validadas e encerradas corretamente.

Este gate autoriza somente shadow sobre snapshot. Ele não promove `NG3`, não
autoriza observação contínua da fila ativa e não permite aplicação de decisões.

## CPU-SH2 — janela shadow ao vivo

**Estado:** concluído —
`governanca/gates/CPU_LIVE_SHADOW_RESULT_2026-09-04.md`.

- seis snapshots ao vivo analisados no `aces`;
- integridade, somente leitura e elegibilidade aprovadas em 6/6 capturas;
- recomendação contrafactual estável;
- nenhum efeito em fila, leases, workers ou GPUs;
- serviço encerrado ao fim da janela.

A arquitetura fica aprovada para shadow contínuo, mas este gate não autoriza
canário nem aplicação de decisões na campanha.

## CPU-OP1 — homologação operacional CPU

**Estado:** concluído —
`governanca/gates/CPU_OPERATIONAL_HOMOLOGATION_RESULT_2026-09-04.md`.

- start, status e stop operacionais e idempotentes;
- estado, PID e log isolados no checkout; ledger e relatórios isolados por execução;
- validação V2 com 10/10 amostras e zero erros;
- lifecycle corretivo V3 com 2/2 amostras e dois stops limpos;
- falha V1 preservada e comprovadamente fail-closed;
- nenhum processo ou PID residual.

**Decisão:** trilha CPU homologada para plano de controle shadow. Canário e
produção decisória permanecem não autorizados.

## CPU-MINI-ACER — campanha MomEng CPU isolada

**Estado:** concluído —
`governanca/gates/CPU_MVHSN_MINI_ACER_RESULT_2026-09-04.md`.

- workload `momeng`/`cpu_reference` executado somente no `codex-acer`;
- 10 tarefas em raiz independente;
- nenhum worker científico ou GPU iniciado;
- MVHSN distribuída não acessada;
- análise FADA em SQLite `mode=ro`, sem aplicação de recomendação.

Variante vigente: `momeng-cpu-mini-acer-n50-n100-20260904`, usando somente
`n=50` e `n=100`; resultado em
`governanca/gates/CPU_MVHSN_MINI_ACER_N50_N100_RESULT_2026-09-04.md`.

Homologação científica MomEng CPU: `CPU_MOMENG_MINI_ACER_RESULT_2026-09-04.md`,
com protocolo congelado em `CPU_MOMENG_MINI_ACER_PROTOCOL_2026-09-04.md`.

Homologação da campanha CPU ampliada: `CPU_MOMENG_CAMPAIGN_ACER_RESULT_2026-09-04.md`,
com 12/12 execuções aprovadas (`n=50,100,200,400`).

## G0 — especificação

**Estado:** concluído — `governanca/gates/G0_SPECIFICATION_2026-08-08.md`.

- invariantes, unidades e desempates versionados;
- decisão de espera possui contrafactual definido;
- fallback e rollback testados.

## G1 — testes determinísticos

**Estado:** concluído — `governanca/gates/G1_DETERMINISTIC_TESTS_2026-08-08.md`.

- elegibilidade, cold start, indisponibilidade e empate;
- tarefas longas, máquinas lentas e cauda adversarial;
- nenhuma perda ou dupla atribuição provocada pelo adaptador.

## G2 — backtest temporal

**Estado:** não aprovado — `governanca/gates/G2_RESULT_2026-08-08.md`.

- comparação com FIFO, interleaved, Min-Min, Max-Min e Sufferage;
- traces separados em treino e avaliação pela ordem temporal;
- makespan, p95, ociosidade, erro de ETA e custo do escalonador.

## NG2 — backtest da candidata FADA-HS 0.2

**Estado:** não aprovado —
`governanca/gates/NG2_HS02_RESULT_2026-09-04.md`.

- protocolo e hashes congelados antes da execução;
- 400 réplicas pareadas executadas offline com 32 processos locais;
- quatro dos cinco critérios passaram;
- limite superior bootstrap da regressão média foi 3,164%, acima do máximo de
  2%.

Este resultado preserva o bloqueio de shadow científico novo e de promoção.

## NG2 — backtest da candidata FADA-HS 0.3

**Estado:** não aprovado —
`governanca/gates/NG2_HS03_RESULT_2026-09-04.md`.

- não inferioridade estatística e critérios de cauda aprovados em 400 réplicas
  inéditas;
- p95 do custo decisório de 143,439 ms excedeu o limite congelado de 100 ms.

O bloqueio persiste até que uma candidata posterior satisfaça todos os critérios.

## NG2-HS04 — backtest da candidata FADA-HS 0.4

**Estado:** concluído para a política offline —
`governanca/gates/NG2_HS04_RESULT_2026-09-04.md`.

- protocolo congelado antes da coleta e 400 seeds confirmatórias inéditas;
- não inferioridade bootstrap aprovada (0,533% <= 2%);
- p95 de makespan aprovado (0,9866 <= 1,05);
- custo decisório p95 aprovado (75,870 ms <= 100 ms).

**Decisão:** a FADA-HS 0.4 está aprovada como política offline neste corpus. O
gate integrado NG2 do protocolo FADA-HS/RC, bem como NG3–NG5, não são promovidos
por esta evidência isolada.

## CPU-H2 / NG2-HS04-R — reprodução externa no servidor

**Estado:** concluído —
`governanca/gates/NG2_HS04_SERVER_REPRODUCTION_RESULT_2026-09-04.md`.

- checkout, identidade Xander e estado Sentinela/mAI exclusivos do servidor;
- hashes do núcleo e do runner conferidos antes da execução;
- NG2-HS04 reproduzido com 5/5 critérios aprovados;
- kernel CPU conservador aprovado, com 72 CPUs lógicas observadas e aceleração
  de 3,584× até quatro processos;
- nenhuma fila, worker, GPU ou serviço de campanha acessado.

Esta é uma certificação de portabilidade offline, não uma promoção para shadow
ou produção.

## VAL-402-HS04 — ledger e replay adversarial

**Estado:** concluído para replay sintético —
`governanca/gates/VAL402_HS04_ADVERSARIAL_RESULT_2026-09-04.md`.

- ledger JSONL append-only e somente leitura por decisão;
- traces nominal, com drift/ruído, cauda e encerramento reproduzidos;
- 156 IDs de decisão únicos e replays byte-a-byte determinísticos;
- p95 decisório máximo de 17,356 ms;
- sem adaptador de comando ou acesso a campanha.

Esta evidência cobre a fatia FADA-HS de VAL-401/VAL-402. A integração completa
com os contratos de estimador e RC ainda é necessária antes de NG3.

## EST-101/EST-102 — contratos de observação e estratificação

**Estado:** implementação offline verificada —
`governanca/gates/EST101_EST102_CONTRACT_RESULT_2026-09-04.md`.

- resultados concluídos, falhos, interrompidos e censurados são distintos;
- só conclusões fornecem duração para treino;
- o estimador 0.2 permanece paralelo ao baseline 0.1;
- fallback não mistura backend ou perfil de hardware.

Este avanço ainda não compõe NG1A: recência/drift, calibração de incerteza e
interferência de concorrência permanecem pendentes.

## EST-101–EST-105 — estimador 0.2 completo em contrato

**Estado:** implementação offline verificada —
`governanca/gates/EST101_EST105_CONTRACT_RESULT_2026-09-04.md`.

- recência e regime temporal são determinísticos;
- cobertura, ETA e perdas de quantil exigem avaliação pós-corte;
- capacidade só é inferida em níveis efetivamente observados.

Ainda não é NG1A: falta executar a evidência integrada com corpus, sementes e
limiares pré-registrados. Nenhuma política ou controller em modo ativo foi
alterado.

## VAL-402 integrado — HS 0.4, estimador 0.2 e RC shadow

**Estado:** concluído para replay sintético integrado —
`governanca/gates/VAL402_INTEGRATED_RESULT_V2_2026-09-04.md`.

- os quatro cenários adversariais passaram com ledger correlacionado e
  versionado;
- a maior latência p95 foi 9,843 ms;
- RC permaneceu em shadow e nenhuma recomendação foi aplicada;
- tentativa anterior por latência permanece preservada como não aprovada.

O próximo gate é VAL-403/NG2: backtest temporal confirmatório da integração,
pré-registrado antes de nova coleta. Shadow real integrado, canário e produção
seguem bloqueados.

## NG2 integrado — homologação offline completa

**Estado:** concluído —
`governanca/gates/NG2_INTEGRATED_RESULT_2026-09-04.md`.

- 400 réplicas temporais inéditas aprovaram os cinco critérios;
- política HS 0.4, estimador 0.2 e RC shadow possuem evidências correlacionadas;
- backtest, ledger e replay permanecem somente leitura.

**Decisão:** FADA homologada para operação offline integrada. NG3 continua
necessário exclusivamente para uma futura janela de shadow real integrada;
canário e produção seguem não autorizados.

## G3 — shadow mode

**Estado:** não iniciado; bloqueado pela não aprovação de G2.

- decisões registradas sem alterar a fila;
- contrafactual elegível e erro posterior por decisão;
- estabilidade por cenário e por máquina.

## G4 — canário reversível

- somente tarefas ainda pendentes;
- limite de exposição e interrupção automática;
- rollback imediato se makespan/ociosidade piorarem além do limite acordado.

## G5 — produção

- ganho reproduzível ou não inferioridade com benefício operacional comprovado;
- observabilidade e runbook ativos;
- aprovação explícita do responsável pela campanha hospedeira.
