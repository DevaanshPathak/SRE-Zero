# Paper Outline

## Abstract

Introduce SRE-Zero as an environment-grounded benchmark for reliable tool-using agents in simulated incident-response workflows.

## Introduction

Motivate incident response as a high-stakes setting where agents must gather evidence, use tools safely, and avoid premature conclusions.

## Related Work

Discuss agent benchmarks, tool-use evaluation, software engineering benchmarks, operations research, and reliability evaluation.

## SRE-Zero Environment

Describe services, observations, action space, simulator state, episode termination, and safety boundaries.

## Task Suite

Define task design principles, the 15 deterministic v0.1 tasks, difficulty splits, distractors, and config schema.

## Metrics

Explain success, reward, evidence coverage, invalid action rate, wrong remediation rate, premature resolution rate, and efficiency.

## Baselines

Describe random and scripted expert baselines, including the limitations of the scripted upper bound.

## Experiments

Specify evaluation protocol, seeds, episodes per task, and reporting format.

## Results

Report baseline performance and task-level breakdowns.

## Failure Analysis

Analyze invalid actions, symptom chasing, repeated useless actions, premature resolution, and wrong remediations.

## Limitations

Discuss simulator simplicity, small task count, scripted policies, lack of real infrastructure, and missing LLM adapters in v0.1.

## Conclusion

Summarize the benchmark direction and planned extensions.
