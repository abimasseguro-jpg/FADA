# Gate G0 — especificação

- data: 2026-08-08
- política: `fada-hs/0.1`
- estado: concluído

## Evidência

- objetivo robusto aplicado uniformemente a todo o contrafactual;
- unidades, desempates e decisão de espera definidos em `docs/SPECIFICATION.md`;
- fallback explícito para entradas inseguras;
- promoção e rollback reversíveis implementados em `src/fada/control.py`;
- testes de fallback, versionamento e rollback em `tests/test_policy.py`.

## Limite

G0 fecha o contrato formal. Não demonstra desempenho, não autoriza shadow mode e
não promove a política para produção.
