# LLM Baselines

SRE-Zero Mini includes optional OpenAI-compatible LLM baselines. They are disabled unless selected through the evaluation CLI.

For the full baseline taxonomy, prompt-template notes, no-API runner, and
failure examples, see `docs/baseline_agents.md`.

## Configuration

Create a local `.env` from `.env.example`:

```bash
cp .env.example .env
```

Set:

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=...
```

For local or open-source servers, point `OPENAI_BASE_URL` or `SREZERO_OPEN_SOURCE_BASE_URL` at an OpenAI-compatible `/v1` endpoint. Some local servers accept an empty or dummy API key.

Optional per-baseline model variables:

- `SREZERO_PROMPTING_MODEL`
- `SREZERO_REACT_MODEL`
- `SREZERO_OPEN_SOURCE_MODEL`
- `SREZERO_FRONTIER_MODEL`

Provider-throttling controls:

- `SREZERO_LLM_MAX_RETRIES`: provider-call retries after an errored request. Default: `5`.
- `SREZERO_LLM_MIN_REQUEST_INTERVAL_SECONDS`: minimum wait after one LLM request
  finishes before sending the next request, including retries. Default: `15`.
- `SREZERO_LLM_RATE_LIMIT_REQUESTS`: maximum provider calls per window. Default: `5`.
- `SREZERO_LLM_RATE_LIMIT_WINDOW_SECONDS`: rate-limit window length. Default: `60`.
- `SREZERO_LLM_REJECTION_PAUSE_THRESHOLD`: consecutive failed provider calls before
  a cooldown pause. Default: `3`.
- `SREZERO_LLM_REJECTION_PAUSE_SECONDS`: cooldown length after the rejection
  threshold is hit. Default: `60`.

## Commands

- Random: `python eval/run_eval.py --agent random --episodes 5`
- Scripted expert: `python eval/run_eval.py --agent scripted --episodes 5`
- Prompting: `python eval/run_eval.py --agent prompting --episodes 1`
- ReAct-style: `python eval/run_eval.py --agent react --episodes 1`
- Open-source LLM: `python eval/run_eval.py --agent open_source --episodes 1`
- Frontier model: `python eval/run_eval.py --agent frontier --episodes 1`

For long sweeps, prefer `eval/run_all_eval.py --resume`. It writes per-run
JSON checkpoints and skips completed model runs on restart. To request a clean
pause, create the configured pause file, which defaults to
`notes/runs/pause.flag`; remove it before resuming.

LLM baseline results depend on the configured provider, model, decoding settings, and endpoint behavior. For benchmark reporting, record the `.env` model variables, provider type, seed, and episode count.
