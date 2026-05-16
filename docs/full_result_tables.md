# Full Result Tables

This document records the archived preliminary 25-task baseline sweep used for
the v1.5 draft. The current benchmark suite has since expanded to 40 tasks.
These numbers are not final model rankings. They use one seed and one episode
per LLM task; several API-backed runs include provider or agent-output errors.

For reproducible table generation from JSON:

```bash
python eval/write_result_tables.py \
  --input notes/runs/baseline_blog_full/summary.json \
  --output-dir notes/tables/baseline_blog_full
```

## Aggregate Marks

| Rank | Baseline | Model | Marks | Success | Reward | Evidence | Invalid | Errors |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | scripted | deterministic/scripted | 93.4 | 1.00 | 0.943 | 1.00 | 0.00 | 0 |
| 2 | frontier | openai/gpt-5.5 | 57.4 | 0.52 | 0.527 | 0.86 | 0.01 | 2 |
| 3 | frontier | anthropic/claude-opus-4.7 | 48.3 | 0.40 | 0.470 | 0.68 | 0.06 | 5 |
| 4 | react | anthropic/claude-sonnet-4.6 | 46.1 | 0.36 | 0.417 | 0.81 | 0.13 | 0 |
| 5 | open_source | mistralai/mistral-small-3.2-24b-instruct | 24.9 | 0.04 | 0.099 | 0.79 | 0.00 | 0 |
| 6 | react | openai/gpt-5-mini | 18.1 | 0.00 | 0.012 | 0.66 | 0.08 | 24 |
| 7 | open_source | nvidia/nemotron-3-super-120b-a12b:free | 17.3 | 0.00 | 0.039 | 0.61 | 0.19 | 5 |
| 8 | prompting | openai/gpt-5-mini | 16.2 | 0.00 | 0.014 | 0.55 | 0.01 | 20 |
| 9 | open_source | openai/gpt-oss-20b:free | 11.3 | 0.00 | 0.003 | 0.31 | 0.01 | 20 |
| 10 | random | deterministic/random | 5.4 | 0.00 | 0.004 | 0.04 | 0.11 | 0 |
| 11 | frontier | anthropic/claude-sonnet-4.6 | 5.3 | 0.00 | 0.000 | 0.01 | 0.00 | 25 |
| 12 | open_source | meta-llama/llama-3.3-70b-instruct:free | 5.0 | 0.00 | 0.000 | 0.00 | 0.00 | 25 |
| 13 | open_source | qwen/qwen3-next-80b-a3b-instruct:free | 5.0 | 0.00 | 0.000 | 0.00 | 0.00 | 25 |
| 14 | open_source | google/gemma-4-26b-a4b-it:free | 5.0 | 0.00 | 0.000 | 0.00 | 0.00 | 25 |

## Paper-Level Metrics

| Baseline | Model | Success | Mean Reward | Mean Steps | Invalid Action | Evidence | Wrong Fix | Distractor Failure | Premature Resolution |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| scripted | deterministic/scripted | 1.00 | 0.943 | 4.60 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| frontier | openai/gpt-5.5 | 0.52 | 0.527 | 6.28 | 0.01 | 0.86 | 0.26 | 0.00 | 0.36 |
| frontier | anthropic/claude-opus-4.7 | 0.40 | 0.470 | 4.04 | 0.06 | 0.68 | 0.18 | 0.00 | 0.40 |
| react | anthropic/claude-sonnet-4.6 | 0.36 | 0.417 | 6.68 | 0.13 | 0.81 | 0.32 | 0.00 | 0.64 |
| open_source | mistralai/mistral-small-3.2-24b-instruct | 0.04 | 0.099 | 8.04 | 0.00 | 0.79 | 0.42 | 0.00 | 0.44 |
| react | openai/gpt-5-mini | 0.00 | 0.012 | 3.36 | 0.08 | 0.66 | 0.00 | 0.00 | 0.00 |
| open_source | nvidia/nemotron-3-super-120b-a12b:free | 0.00 | 0.039 | 6.52 | 0.19 | 0.61 | 0.64 | 0.00 | 0.00 |
| prompting | openai/gpt-5-mini | 0.00 | 0.014 | 4.12 | 0.01 | 0.55 | 0.00 | 0.00 | 0.00 |
| open_source | openai/gpt-oss-20b:free | 0.00 | 0.003 | 2.76 | 0.01 | 0.31 | 0.00 | 0.00 | 0.00 |
| random | deterministic/random | 0.00 | 0.004 | 3.38 | 0.11 | 0.04 | 0.94 | 0.05 | 0.48 |
| frontier | anthropic/claude-sonnet-4.6 | 0.00 | 0.000 | 0.04 | 0.00 | 0.01 | 0.00 | 0.00 | 0.00 |
| open_source | meta-llama/llama-3.3-70b-instruct:free | 0.00 | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| open_source | qwen/qwen3-next-80b-a3b-instruct:free | 0.00 | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| open_source | google/gemma-4-26b-a4b-it:free | 0.00 | 0.000 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

The full per-task success table should be generated from the run JSON because it
is wide and easier to inspect as a separate artifact.
