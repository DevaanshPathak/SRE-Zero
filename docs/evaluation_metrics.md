# Evaluation Metrics

Success rate is necessary but not enough. An agent that guesses final answers or applies risky remediations can succeed occasionally while behaving unreliably.

SRE-Zero Mini reports:

- `success_rate`: fraction of episodes resolved correctly.
- `mean_reward`: mean normalized final reward.
- `mean_steps`: mean steps used.
- `invalid_action_rate`: invalid actions divided by total actions.
- `evidence_coverage`: mean fraction of task-relevant evidence gathered.
- `wrong_remediation_rate`: wrong remediation actions divided by remediation actions.
- `premature_resolution_rate`: fraction of episodes with premature or incorrect resolution submissions.

These metrics separate diagnosis quality, tool reliability, remediation quality, and efficiency.

