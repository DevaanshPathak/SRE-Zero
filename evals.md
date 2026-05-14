# SRE-Zero Evaluation Rotation

This file is the local run plan for collecting benchmark JSONs without spending
the whole API budget in one day. The target budget is roughly 4 USD/day, but the
actual cost depends on the provider, model pricing, latency, and how many actions
each model takes. Treat each command as a budgeted run unit, not as a guaranteed
price cap.

All commands write outputs under `notes/runs/`, which is intentionally ignored by
git. Run commands from the repository root.

## Before Running

```powershell
New-Item -ItemType Directory -Force notes\runs | Out-Null
$env:SREZERO_LLM_TIMEOUT_SECONDS="60"
```

Use `--dry-run` before spending API calls:

```powershell
python eval/run_all_eval.py --preset paper --only-baselines prompting --difficulty easy --dry-run
```

## Model Buckets

The `paper` preset compares 4-5 models inside each LLM baseline bucket.

Prompting:

- `openai/gpt-5-mini`
- `openai/gpt-5.4-mini`
- `google/gemini-3.1-flash-lite`
- `qwen/qwen3.6-flash`
- `mistralai/mistral-medium-3-5`

ReAct:

- `openai/gpt-5-mini`
- `openai/gpt-5.4`
- `anthropic/claude-sonnet-4.6`
- `google/gemini-3.1-pro-preview`
- `x-ai/grok-4.3`

Open-source:

- `ibm-granite/granite-4.1-8b`
- `inclusionai/ring-2.6-1t:free`
- `qwen/qwen3.6-35b-a3b`
- `nvidia/nemotron-3-super-120b-a12b:free`
- `google/gemma-4-26b-a4b-it:free`

Frontier:

- `openai/gpt-5.5`
- `anthropic/claude-opus-4.7-fast`
- `google/gemini-3.1-pro-preview`
- `x-ai/grok-4.3`
- `mistralai/mistral-medium-3-5`

## Day 0: No-API Anchors

Run the deterministic lower and upper bounds. This does not call an LLM API.

```powershell
python eval/run_all_eval.py `
  --only-baselines random scripted `
  --deterministic-episodes 5 `
  --output-dir notes/runs/day00_deterministic `
  --summary-output notes/runs/day00_deterministic/summary.json `
  --log-file notes/runs/day00_deterministic/run.log
```

## Day 1: Prompting, Easy Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines prompting `
  --difficulty easy `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day01_prompting_easy `
  --summary-output notes/runs/day01_prompting_easy/summary.json `
  --log-file notes/runs/day01_prompting_easy/run.log
```

## Day 2: Prompting, Medium Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines prompting `
  --difficulty medium `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day02_prompting_medium `
  --summary-output notes/runs/day02_prompting_medium/summary.json `
  --log-file notes/runs/day02_prompting_medium/run.log
```

## Day 3: Prompting, Hard Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines prompting `
  --difficulty hard `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day03_prompting_hard `
  --summary-output notes/runs/day03_prompting_hard/summary.json `
  --log-file notes/runs/day03_prompting_hard/run.log
```

## Day 4: ReAct, Easy Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines react `
  --difficulty easy `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day04_react_easy `
  --summary-output notes/runs/day04_react_easy/summary.json `
  --log-file notes/runs/day04_react_easy/run.log
```

## Day 5: ReAct, Medium Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines react `
  --difficulty medium `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day05_react_medium `
  --summary-output notes/runs/day05_react_medium/summary.json `
  --log-file notes/runs/day05_react_medium/run.log
```

## Day 6: ReAct, Hard Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines react `
  --difficulty hard `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day06_react_hard `
  --summary-output notes/runs/day06_react_hard/summary.json `
  --log-file notes/runs/day06_react_hard/run.log
```

## Day 7: Open-Source, Easy Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines open_source `
  --difficulty easy `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day07_open_source_easy `
  --summary-output notes/runs/day07_open_source_easy/summary.json `
  --log-file notes/runs/day07_open_source_easy/run.log
```

## Day 8: Open-Source, Medium Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines open_source `
  --difficulty medium `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day08_open_source_medium `
  --summary-output notes/runs/day08_open_source_medium/summary.json `
  --log-file notes/runs/day08_open_source_medium/run.log
```

## Day 9: Open-Source, Hard Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines open_source `
  --difficulty hard `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day09_open_source_hard `
  --summary-output notes/runs/day09_open_source_hard/summary.json `
  --log-file notes/runs/day09_open_source_hard/run.log
```

## Day 10: Frontier, Easy Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines frontier `
  --difficulty easy `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day10_frontier_easy `
  --summary-output notes/runs/day10_frontier_easy/summary.json `
  --log-file notes/runs/day10_frontier_easy/run.log
```

## Day 11: Frontier, Medium Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines frontier `
  --difficulty medium `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day11_frontier_medium `
  --summary-output notes/runs/day11_frontier_medium/summary.json `
  --log-file notes/runs/day11_frontier_medium/run.log
```

## Day 12: Frontier, Hard Split

```powershell
python eval/run_all_eval.py `
  --preset paper `
  --only-baselines frontier `
  --difficulty hard `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/day12_frontier_hard `
  --summary-output notes/runs/day12_frontier_hard/summary.json `
  --log-file notes/runs/day12_frontier_hard/run.log
```

## Cheap Daily Smoke

Use this when you only want to verify the pipeline and spend little or no API
budget. The first command uses no LLM API. The second command calls only the
quick preset LLM set on easy tasks.

```powershell
python eval/run_all_eval.py `
  --preset quick `
  --skip-llm `
  --deterministic-episodes 1 `
  --output-dir notes/runs/smoke_deterministic `
  --summary-output notes/runs/smoke_deterministic/summary.json `
  --log-file notes/runs/smoke_deterministic/run.log
```

```powershell
python eval/run_all_eval.py `
  --preset quick `
  --skip-deterministic `
  --difficulty easy `
  --llm-episodes 1 `
  --timeout-seconds 60 `
  --output-dir notes/runs/smoke_llm_easy `
  --summary-output notes/runs/smoke_llm_easy/summary.json `
  --log-file notes/runs/smoke_llm_easy/run.log
```

## Notes for Paper Runs

- Use the same `seed` across all days unless intentionally running a new replicate.
- Keep `llm_episodes=1` until the cost profile is known.
- Compare models within the same day/split using `summary.json -> marks.by_baseline`.
- Compare difficulty splits by merging `summary.json` files later.
- If a provider returns malformed content or rate limits, the run is recorded in JSON
  with error counts instead of being silently dropped.
