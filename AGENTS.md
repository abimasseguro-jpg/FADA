# Global project governance

- Every software or scientific project owned by this user must include an
  operational Sentinela and mAI governance layer.
- A new project is not considered fully initialized until Sentinela and mAI
  have project-specific identity, isolated state/log paths, start, stop and
  status commands, and a successful validation run.
- When performing authorized change or build work in an existing project,
  verify this requirement. Treat a missing or shared-state installation as a
  governance defect and remediate it within the authorized project scope.
- Git worktrees may share versioned Sentinela/mAI code, but each worktree must
  keep independent runtime state, PID files, logs, evidence and project ID.
- Sentinela and mAI must remain observational and fail closed: they must not
  alter scientific results, active campaigns or production defaults without
  explicit authorization.

## Project-local observational authorization

Authorized by the project owner on 2026-09-02 for the canonical root
`/home/atilapcorreia/ARTIGOS/FADA`, Sentinela project ID `fada`, and effective
Xander project ID `fada-9637841022e6`.

The following governance checks are authorized until explicitly revoked:

- `python3 governanca/tools/sentinela_fada.py status --root .`
- `python3 governanca/tools/sentinela_fada.py audit --root . --skip-tests`
- `python3 governanca/tools/sentinela_memory.py status --root .`

This authorization does not include `pytest`, `unittest`, simulations,
campaigns, production services, external queues, worker or lease changes,
scientific-result changes, or production-default changes. A root, project-ID,
scope, or observational-mode mismatch must fail closed without mutation.
