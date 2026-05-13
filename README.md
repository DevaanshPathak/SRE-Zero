# SRE-Zero

SRE-Zero is an early-stage research benchmark for studying reliable tool-using LLM agents in simulated incident-response workflows.

The v0.1 repository contains **SRE-Zero Mini**, a small deterministic environment where agents diagnose incidents across simulated `web_server`, `database`, and `cache` services. Agents inspect logs, metrics, status, and config, then apply minimal in-memory remediations under a step budget.

This is early research code. It is intentionally small, safe, and simulation-only. It does not call external LLM APIs, control real infrastructure, or execute arbitrary shell commands.

## Research Motivation

Many agent benchmarks measure final answer quality without grounding the agent in a stateful operational environment. SRE-Zero focuses on a narrower question: can a tool-using agent gather relevant evidence, distinguish symptoms from root causes, apply minimal fixes, and resolve incidents reliably?

The initial benchmark emphasizes:

- Deterministic incident tasks.
- Structured tool actions.
- Text and structured observations.
- Partial-credit rewards.
- Simple reproducible baselines.
- Metrics beyond success rate.

## Installation

Requires Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
```

## Quick Start

Run a scripted expert episode:

```bash
python examples/run_single_episode.py --task cache_crash --agent scripted
```

Run random baseline evaluation:

```bash
python eval/run_eval.py --agent random --episodes 5
```

Run scripted baseline evaluation:

```bash
python eval/run_eval.py --agent scripted --episodes 5
```

Run tests and lint:

```bash
pytest
ruff check .
```

## Task Suite Summary

SRE-Zero Mini v0.1 includes five incident tasks:

| Task | Difficulty | Root Cause |
| --- | --- | --- |
| `cache_crash` | easy | Cache service crashed |
| `db_pool_exhaustion` | medium | Database connection pool exhaustion |
| `web_timeout_misconfig` | hard | Web timeout configuration too low |
| `cache_latency_degradation` | medium | Cache TTL configuration too low |
| `misleading_web_500_db_rootcause` | hard | Database saturation causing web failures |

## Baseline Agents

- `RandomAgent`: samples action templates with deterministic randomness. It intentionally sometimes emits invalid service names to test environment robustness.
- `ScriptedExpertAgent`: uses a small task-specific policy table as an approximate upper bound. In v0.1 this policy is allowed to know task solutions, and this limitation is documented in the benchmark notes.

## Roadmap

- Add more task families and variants.
- Add hidden stochastic perturbations while preserving reproducibility.
- Add richer action costs and remediation side effects.
- Add trajectory export and comparison tools.
- Add optional Docker-backed scenarios after the simulator contract stabilizes.
- Add external LLM agent adapters without making them required.

## Citation

Citation metadata will be added when the benchmark paper draft is available.

