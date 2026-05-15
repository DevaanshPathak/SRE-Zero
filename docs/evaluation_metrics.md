# Evaluation Metrics

Success rate is necessary but not enough. An agent that guesses final answers or applies risky remediations can succeed occasionally while behaving unreliably.

SRE-Zero Mini reports:

- `success_rate`: fraction of episodes resolved correctly.
- `mean_reward`: mean normalized final reward.
- `mean_steps`: mean steps used.
- `invalid_action_rate`: invalid actions divided by total actions.
- `evidence_coverage`: mean fraction of task-relevant evidence gathered.
- `wrong_remediation_rate`: wrong remediation actions divided by remediation actions.
- `distractor_failure_rate`: wrong remediations against configured distractor services divided by remediation actions.
- `premature_resolution_rate`: fraction of episodes with premature or incorrect resolution submissions.

These metrics separate diagnosis quality, tool reliability, remediation quality, and efficiency.

Evaluation can run the full suite or a difficulty split:

```bash
python eval/run_eval.py --agent scripted --episodes 1
python eval/run_eval.py --agent scripted --difficulty hard --episodes 1
```

Combined evaluation summaries can be plotted without extra dependencies:

```bash
python eval/plot_results.py --input notes/runs/all_eval_summary.json --output-dir notes/plots/latest
```
