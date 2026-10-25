# Sentinela-Mãe — memória estruturada e aprendizagem

## Finalidade

A memória do Sentinela-Mãe preserva somente sinais capazes de melhorar
decisões futuras. Ela não é transcrição de conversa, cópia de logs nem arquivo
indiscriminado de contexto.

Regra:

```text
conversa e artefatos produzem sinais;
sinais viram memória apenas quando há benefício em lembrar.
```

## Classes de memória

| Classe | Conteúdo | Autoridade |
|---|---|---|
| `normative` | norma ou decisão vigente | exige promoção explícita |
| `operational` | estado necessário à continuidade | vale no escopo e prazo declarados |
| `causal` | erro, causa, correção e prevenção | depende da força da evidência |
| `operator_intent` | preferência, limite e modo de direção | não é norma universal |
| `experimental` | hipótese, sugestão e resultado em avaliação | consultiva |

Norma não pode ser misturada com telemetria. Preferência não pode ser
generalizada sem confirmação. Hipótese não pode ser apresentada como fato.

## Fontes elegíveis

- notas triadas de sessão;
- sinais explícitos do operador;
- decisões e ADRs;
- relatórios epistemológicos;
- backlog da Sentinela-IA;
- contexto declarado pela Sentinela-filha;
- resultados de experimento com evidência consultável.

Chat bruto, cache, telemetria de alta frequência e repetição literal não são
fontes de memória durável.

## Ciclo de vida

```text
proposed → reviewed → accepted/rejected
accepted → implemented → validated
```

Estados também podem ser `superseded` ou `expired`. Toda revisão preserva o
registro anterior e acrescenta justificativa, responsável, data e evidência.

Uma hipótese deve declarar critério de expiração. Uma preferência deve
declarar escopo. Uma norma deve declarar fonte autorizadora e validação.

## Captura de sessão

Registrar quando houver:

- decisão emergente;
- correção relevante do operador;
- contradição detectada;
- risco novo;
- preferência estável;
- modo de direção;
- próxima ação que não deve ser esquecida.

Não registrar conversa casual, repetição de norma já consolidada ou dumping de
contexto.

## Instrumento

O comando portátil é:

```bash
python3 governanca/tools/sentinela_memory.py status --root .
python3 governanca/tools/sentinela_memory.py record --root . \
  --class operator_intent --kind preference --summary "..."
python3 governanca/tools/sentinela_memory.py review --root . \
  --fingerprint ID --decision accepted --reason "..."
```

`record` cria uma proposta; `review` registra decisão append-only. Nenhum dos
dois altera automaticamente código, configuração ou campanha.
