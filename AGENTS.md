# Agent Notes

This repository is SRE-Zero, a simulated incident-response benchmark for evaluating reliable tool-using agents.

## Working Principles

- Keep the environment simulation-only. Do not add real infrastructure control.
- Keep dependencies minimal and reproducible.
- Preserve deterministic task behavior unless a change explicitly introduces seeded variation.
- Prefer config-backed task definitions under `srezero/task_configs/`.
- Keep `SREEnv` stable for benchmark users.
- Keep `SREOpenEnv` compatible with the Gym-style reset/step shape.
- Do not commit secrets, `.env`, generated local notes, or experiment scratch files.

## Verification

Before pushing benchmark changes, run:

```bash
python -m pytest
python -m ruff check .
python -m mypy
python eval/run_eval.py --agent scripted --episodes 1
```

For frontend changes, also run:

```bash
cd frontend
npm run typecheck
npm run build
npm audit --audit-level=moderate
```

For baseline smoke checks, also run:

```bash
python eval/run_eval.py --agent random --episodes 1 --output eval/random_smoke.json
python eval/run_eval.py --agent scripted --difficulty hard --episodes 1 --output eval/hard_smoke.json
```

Remove temporary smoke result files before committing unless they are intentionally part of the change.

## Local Notes

The `notes/` directory is intentionally ignored. It is for local plots, paper drafts, and blog drafts. Do not force-add it unless the repository policy changes.
