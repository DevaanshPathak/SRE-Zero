# Reward Design

SRE-Zero Mini uses partial-credit rewards to distinguish lucky final answers from reliable incident-response behavior.

Episode-level reward is normalized to `[0.0, 1.0]`. Each step also returns a shaping reward equal to the change in raw reward state, clipped to `[-1.0, 1.0]`.

## Positive Components

| Component | Maximum |
| --- | ---: |
| Relevant evidence gathered | 0.20 |
| Correct root cause identified | 0.25 |
| Correct remediation applied | 0.25 |
| Correct resolution submitted | 0.20 |
| Efficiency bonus | 0.10 |

Evidence credit is proportional to relevant evidence coverage. Efficiency is awarded only on successful resolution and decreases as more of the step budget is used.

## Penalties

| Penalty | Value |
| --- | ---: |
| Invalid action | -0.05 |
| Repeated invalid action | -0.10 |
| Wrong remediation | -0.15 |
| Premature resolution | -0.20 |
| Restarting unrelated service | -0.10 |
| Repeated useless action | -0.05 |

Reward internals are returned in `StepResult.info["reward_components"]` for benchmark analysis, but they are not part of the agent-visible observation.

