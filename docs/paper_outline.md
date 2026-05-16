# Paper Outline

## Abstract

Introduce SRE-Zero as an environment-grounded benchmark for reliable tool-using
agents in simulated incident-response workflows. State that the current release
contains 40 deterministic tasks, train/dev/test splits, an unseen incident split,
structured actions, partial rewards, and reproducible evaluation scripts.

## Introduction

Motivate incident response as a setting where agents must gather evidence, use
tools safely, and avoid premature conclusions.

Key claims to develop:

- Reliable tool use requires process evaluation, not only final-answer scoring.
- Incident response is naturally sequential and evidence-grounded.
- Evidence gathering, remediation, and final resolution are separable skills.

## Related Work

Subsections:

- Tool-use and agent benchmarks.
- Software engineering and debugging benchmarks.
- Reinforcement learning environments and Gym-style APIs.
- Operations, incident response, and SRE automation.
- Reliability and safety evaluation for autonomous agents.

## SRE-Zero Environment

Describe services, observations, action space, simulator state, episode
termination, and safety boundaries.

Include:

- Service model: web server, database, cache, message queue, load balancer.
- Observation schema and hidden state boundaries.
- Structured action parser and invalid action handling.
- Gym-style API and final benchmark API.
- Simulation-only safety constraints.

## Task Suite

Define task design principles, the 40 deterministic v0.6 tasks, difficulty
labels, train/dev/test splits, unseen incident split, distractors, noisy metrics,
and config schema.

Include a task table with:

- task id
- difficulty
- split
- alert
- root-cause family
- correct remediation type
- distractor type

## Metrics

Paper-level metrics:

- success rate
- mean steps to resolution
- invalid action rate
- evidence coverage
- wrong remediation rate
- distractor robustness / distractor failure rate
- partial reward
- standardized 100-point marks score

## Baselines

Describe random, scripted expert, prompting-only, ReAct-style, open-source LLM,
and frontier-model baselines. Explain that scripted expert has task-policy access
and is an approximate upper bound, not a realistic autonomous model.

## Experiments

Specify:

- split used
- seed list
- episodes per task
- model/provider configuration
- timeout and parsing settings
- command-line invocation
- JSON artifact path

## Results

Report:

- aggregate marks table
- raw paper metrics table
- per-task success table
- difficulty-stratified table
- split-stratified table

## Failure Analysis

Analyze:

- high evidence coverage with failed resolution
- distractor-driven remediation
- malformed or invalid actions
- provider or parsing failures
- premature final resolution
- repeated useless actions

## Limitations

Discuss simulator simplicity, task scale, scripted policies, lack of real
infrastructure, provider instability, one-seed preliminary runs, lack of human
SRE baselines, and absence of statistical confidence intervals.

## Conclusion

Summarize the benchmark direction and planned extensions.

Planned extensions:

- more tasks and incident families
- more seeds and confidence intervals
- stronger open-source baselines
- human and semi-scripted baselines
- richer simulator state while preserving safety
