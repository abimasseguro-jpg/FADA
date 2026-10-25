# Governança e Sentinela-FADA

A Sentinela-FADA é a guardiã epistemológica deste projeto. Ela observa e valida
o modelo de escalonamento, preserva incidentes e memória, e comunica eventos ao
intake append-only do Sentinela-mãe. Não despacha tarefas nem altera campanhas.

## Hierarquia

1. instrução explícita atual do responsável;
2. `SENTINELA_FADA.md`;
3. `PROTOCOLO_EPISTEMOLOGICO_SENTINELA.md`;
4. `PROJECT_CONTEXT.md`;
5. `../docs/SPECIFICATION.md`;
6. `VALIDATION_GATES.md`;
7. incidentes, pareceres e evidências históricas.

## Comandos

```bash
python3 governanca/tools/sentinela_fada.py status --root .
python3 governanca/tools/sentinela_fada.py audit --root .
python3 governanca/tools/sentinela_memory.py status --root .
```

Todo erro ou falha deve ser registrado com fato, inferência, alternativas,
fronteira causal e estado da conclusão. Registro não autoriza correção automática.

