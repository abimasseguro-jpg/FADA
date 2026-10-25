# Protocolo epistemológico e de intercomunicabilidade do Sentinela

## Objetivo

Transformar todo erro, falha, incoerência ou diagnóstico corrigido em uma
investigação epistemologicamente auditável. O protocolo impede que correlação,
autoridade, intuição ou repetição sejam promovidas indevidamente a causa-raiz.

Aplica-se a detectores determinísticos, camada cognitiva, operadores humanos,
agentes de IA e Sentinelas-filhos. Não substitui os gates técnicos existentes;
acrescenta o contrato obrigatório de conhecimento e comunicação.

## Função de parceria criativa

A parceria criativa, seu ciclo de aprendizagem e os limites de autorização são
definidos uma única vez em `SENTINELA_MAE.md`. Este protocolo acrescenta a
exigência epistemológica: toda sugestão deve separar fato, inferência,
hipótese, preferência e evidência de validação.

## Regra universal

Todo incidente de severidade `error` ou `critical` deve gerar estudo
epistemológico. Incidentes `warning` também o exigem quando puderem afetar
resultado científico, campanha ativa, segurança, integridade ou governança.

Nenhuma causa pode ser declarada sem evidência discriminante. Na ausência
dela, o estado obrigatório é `provisional` ou `undetermined`.

## Estrutura mínima do estudo

1. Pergunta precisa que está sendo investigada.
2. Fatos observados e fontes primárias.
3. Inferências feitas a partir desses fatos.
4. Premissas explícitas que sustentam as inferências.
5. Desconhecidos e evidência ausente.
6. Explicações alternativas, inclusive as que contradizem a hipótese inicial.
7. Testes capazes de falsificar ou discriminar cada explicação.
8. Fronteira causal: o que a evidência permite e não permite concluir.
9. Estado da conclusão: `demonstrated`, `provisional` ou `undetermined`.
10. Justificativa da confiança atribuída.

O encerramento operacional de um sintoma não encerra automaticamente a
investigação epistemológica. Correção, causa-raiz e prevenção são alegações
distintas e devem possuir evidências próprias.

## Intercomunicabilidade com o Sentinela-mãe

Todo Sentinela-filho deve comunicar ao Sentinela-mãe:

- observação inicial do incidente;
- criação, alteração ou exclusão de arquivo monitorado;
- hashes SHA-256 anterior e novo;
- conclusão do estudo epistemológico;
- revisão ou retratação de diagnóstico anterior;
- alteração de protocolo, detector, gate ou regra;
- risco operacional e científico;
- resposta requerida e motivo de escalonamento.

Cada comunicação contém tradução semântica em linguagem operacional clara,
além da evidência técnica. Os eventos são escritos em
`governanca/evidencias/sentinela_mae/events.jsonl`, em ordem append-only,
numerados e encadeados pelo hash do evento anterior. O estado da ponte fica em
`governanca/evidencias/sentinela_mae/state.json`.

A ponte não promove código, reinicia campanha nem executa recomendações. Ela
preserva e traduz a comunicação para consumo determinístico do
Sentinela-mãe. Falha de transporte ou análise não autoriza silêncio: o evento
permanece no intake append-only e deve ser escalado.

## Critério de encerramento

Um erro somente pode ser classificado como epistemologicamente estudado quando:

- o relatório satisfaz integralmente o schema;
- fatos, inferências e premissas estão separados;
- alternativas e testes de falsificação foram registrados;
- o estado da conclusão e sua confiança estão justificados;
- a tradução ao Sentinela-mãe foi persistida com hash verificável;
- aprendizados continuam `proposed` até implementação e validação independentes.

## Proibições

- transformar ausência de evidência em evidência de ausência;
- confundir sequência temporal com causalidade;
- selecionar apenas evidência favorável;
- ocultar incerteza para produzir resposta conclusiva;
- alterar retrospectivamente o log append-only;
- considerar comunicação concluída sem tradução semântica;
- usar o Sentinela-mãe como autorização automática de mutação.
