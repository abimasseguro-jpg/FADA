# Gate G1 — testes determinísticos

- data: 2026-08-08
- política: `fada-hs/0.1`
- estado: concluído
- comando: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
- resultado: 21 testes, 21 aprovados

## Cobertura discriminante

- elegibilidade e slots desabilitados;
- cold start, confiança, cobertura parcial e fallback;
- empate determinístico e identificadores duplicados;
- tarefa longa em slot rápido e cauda adversarial;
- limites de janela, projeção, incerteza e epsilon;
- promoção, versão e rollback;
- adaptador shadow MVHSN sem mutação ou atribuição da fila;
- contrato determinístico da Sentinela-FADA.

## Limite

Os testes demonstram os contratos discretos cobertos. Não medem desempenho nem
substituem o backtest temporal G2.
