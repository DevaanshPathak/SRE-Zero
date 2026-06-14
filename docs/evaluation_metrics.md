# Evaluation Metrics

Success rate is necessary but not enough. An agent that guesses final answers or applies risky remediations can succeed occasionally while behaving unreliably.

SRE-Zero reports:

- `success_rate`: fraction of episodes resolved correctly.
- `mean_reward`: mean normalized final reward.
- `mean_steps`: mean steps used.
- `invalid_action_rate`: invalid actions divided by total actions.
- `evidence_coverage`: mean fraction of task-relevant evidence gathered.
- `wrong_remediation_rate`: wrong remediation actions divided by remediation actions.
- `distractor_failure_rate`: wrong remediations against configured distractor services divided by remediation actions.
- `premature_resolution_rate`: fraction of episodes with premature or incorrect resolution submissions.
- `root_cause_identification_rate`: fraction of episodes where a submitted resolution matched the hidden root cause, even if the incident was not fully resolved.
- `fix_identification_rate`: fraction of episodes where the submitted resolution described an acceptable fix.
- `correct_service_remediation_rate`: fraction of episodes where the agent attempted remediation on the correct service.
- `correct_remediation_rate`: fraction of episodes where the simulator accepted a remediation as the correct fix.
- `remediation_precision`: correct remediation actions divided by all remediation actions.

These metrics separate diagnosis quality, tool reliability, remediation quality, and efficiency.
They are intentionally reported alongside success rate because early agents often gather
evidence or identify the right subsystem without completing the full incident workflow.

## Difficulty Splits

Evaluation JSON includes `by_difficulty` aggregates for `easy`, `medium`, and `hard`
tasks. Combined summaries also include `difficulty_marks.rows`, which can be used
directly for paper and blog tables. This lets reports show easy-only smoke behavior
without hiding the all-task benchmark result.

## Failure Modes

Each run includes a compact `failure_modes` object with counts for:

- successful episodes
- agent/provider errors
- wrong remediation
- premature resolution
- step-budget exhaustion
- invalid-action failures
- other unresolved failures

These counts are meant for failure-analysis tables, not for ranking models directly.

## Standardized Scoring

The standard paper-facing marks score is defined in `srezero/scoring.py`.

| Component | Weight |
| --- | ---: |
| Success rate | 40 |
| Mean partial reward | 25 |
| Evidence coverage | 20 |
| Efficiency | 10 |
| Validity | 5 |

The score is reported out of 100. It is a compact summary only; paper tables
should also report the raw paper-level metrics above.

## Reproducible Commands

Evaluation can run the full suite, a difficulty split, or a benchmark split:

```bash
python eval/run_eval.py --agent scripted --episodes 1
python eval/run_eval.py --agent scripted --difficulty hard --episodes 1
python eval/run_benchmark.py --agent scripted --split test --episodes 1 --seed 0
```

Combined evaluation summaries can be plotted without extra dependencies:

```bash
python eval/plot_results.py --input notes/runs/all_eval_summary.json --output-dir notes/plots/latest
python eval/write_result_tables.py --input notes/runs/all_eval_summary.json --output-dir notes/tables/latest
```
