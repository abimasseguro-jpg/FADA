# Manifesto de extração do MVHSN

Extração realizada em 06/08/2026. A operação foi por cópia para preservar a
campanha ativa e a proveniência histórica.

| Classe | Origem no MVHSN | Destino FADA | Situação |
|---|---|---|---|
| núcleo | conceito e fórmula nos relatórios | `src/fada/`, `docs/SPECIFICATION.md` | formalizado em 0.1 |
| adaptador | `scripts/fada_shadow_report.py` | `adapters/mvhsn/` | cópia histórica |
| adaptador | `scripts/simulate_adaptive_scheduler.py` | `adapters/mvhsn/` | cópia histórica |
| protótipo | `scripts/simulate_fada_*.py` | `experiments/prototypes/` | não produtivo |
| resultado | Monte Carlo de 06/08/2026 | `experiments/results/` | evidência histórica |
| documentação | relatório e fluxogramas | `docs/research/`, `docs/diagrams/` | cópia histórica |
| parecer | pacote e análise mAI/Sentinela | `governanca/reviews/` | `needs_evidence` |
| campanha | banco, leases, logs e relatório shadow | permanece no MVHSN | deliberado |

Os arquivos mantidos no MVHSN são interfaces de compatibilidade e evidências da
origem. Novas evoluções genéricas devem ocorrer neste projeto; alterações no
adaptador MVHSN devem ser sincronizadas conscientemente nos dois lados até que o
MVHSN passe a importar uma versão instalada da FADA.
