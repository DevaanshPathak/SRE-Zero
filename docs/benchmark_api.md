# Final Benchmark API

SRE-Zero exposes a small public API for benchmark users. The goal is to keep the
environment stable while allowing the task suite, scoring, and reporting code to
grow.

## Python API

```python
from srezero import benchmark_catalog, benchmark_spec, benchmark_task_ids, make_env

spec = benchmark_spec()
task_ids = benchmark_task_ids(split="test")
catalog = benchmark_catalog(split="test")
env = make_env(task_id=task_ids[0])
observation, info = env.reset(seed=0)
```

Public functions:

| Function | Purpose |
| --- | --- |
| `benchmark_spec()` | Returns benchmark metadata, task counts, metric names, and scoring weights. |
| `benchmark_task_ids(split=None, difficulty=None)` | Returns canonical task ids, optionally filtered by split and difficulty. |
| `benchmark_catalog(split=None, difficulty=None)` | Returns public task metadata without hidden solutions. |
| `make_env(task_id=None)` | Creates the Gym-style `SREOpenEnv` wrapper. |
| `standard_score(overall_metrics, target_steps=8.0)` | Converts aggregate metrics into the standard 100-point marks score. |

## Splits

SRE-Zero v0.6 defines four benchmark splits:

| Split | Count | Purpose |
| --- | ---: | --- |
| `train` | 24 | Development and prompt/policy iteration. |
| `dev` | 8 | Model and prompt selection without touching final test. |
| `test` | 8 | Final held-out reporting split. |
| `unseen_incident` | 8 | Held-out incident-generalization subset of `test`. |

Difficulty labels are orthogonal and can be combined with benchmark splits:

```bash
python eval/run_eval.py --agent scripted --split test --difficulty hard --episodes 1
```

## Reproducible Evaluation Command

Canonical deterministic smoke run:

```bash
python eval/run_benchmark.py \
  --agent scripted \
  --split test \
  --episodes 1 \
  --seed 0 \
  --output notes/runs/benchmark_scripted_test.json
```

For a full marks table across baselines:

```bash
python eval/run_baseline_marks.py \
  --baselines random scripted \
  --split test \
  --episodes 5 \
  --seed 0 \
  --output notes/runs/baseline_marks_test.json
```

For paper-ready Markdown tables:

```bash
python eval/write_result_tables.py \
  --input notes/runs/baseline_blog_full/summary.json \
  --output-dir notes/tables/baseline_blog_full
```

## Standard Score

The public marks score is a 100-point composite:

| Component | Weight |
| --- | ---: |
| Success rate | 40 |
| Mean partial reward | 25 |
| Evidence coverage | 20 |
| Efficiency | 10 |
| Validity | 5 |

Efficiency is gated by success rate. Validity uses `1 - invalid_action_rate`.
The raw paper metrics should always be reported next to the composite score.
