# LLM Baselines

SRE-Zero Mini includes optional OpenAI-compatible LLM baselines. They are disabled unless selected through the evaluation CLI.

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

## Commands

- Random: `python eval/run_eval.py --agent random --episodes 5`
- Scripted expert: `python eval/run_eval.py --agent scripted --episodes 5`
- Prompting: `python eval/run_eval.py --agent prompting --episodes 1`
- ReAct-style: `python eval/run_eval.py --agent react --episodes 1`
- Open-source LLM: `python eval/run_eval.py --agent open_source --episodes 1`
- Frontier model: `python eval/run_eval.py --agent frontier --episodes 1`

LLM baseline results depend on the configured provider, model, decoding settings, and endpoint behavior. For benchmark reporting, record the `.env` model variables, provider type, seed, and episode count.

