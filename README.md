# SRE-Zero

SRE-Zero is an early-stage research benchmark for studying reliable tool-using LLM agents in simulated incident-response workflows.

The v0.1 repository contains **SRE-Zero Mini**, a deterministic environment where agents diagnose incidents across simulated `web_server`, `database`, and `cache` services. Agents inspect logs, metrics, status, and config, then apply minimal in-memory remediations under a step budget.

This is early research code. It is intentionally small, safe, and simulation-only. It does not control real infrastructure or execute arbitrary shell commands. External LLM APIs are optional and are only called when an LLM baseline is explicitly selected.

## Research Motivation

Many agent benchmarks measure final answer quality without grounding the agent in a stateful operational environment. SRE-Zero focuses on a narrower question: can a tool-using agent gather relevant evidence, distinguish symptoms from root causes, apply minimal fixes, and resolve incidents reliably?

The initial benchmark emphasizes:

- Deterministic incident tasks.
- Formal easy/medium/hard task splits.
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

Run the Next.js frontend:

```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

Run a difficulty split:

```bash
python eval/run_eval.py --agent scripted --difficulty hard --episodes 1
```

Configure optional OpenAI-compatible LLM baselines:

```bash
cp .env.example .env
```

Then edit `.env`:

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=...
```

Run LLM baselines:

```bash
python eval/run_eval.py --agent prompting --episodes 1
python eval/run_eval.py --agent react --episodes 1
python eval/run_eval.py --agent open_source --episodes 1
python eval/run_eval.py --agent frontier --episodes 1
```

Run tests and lint:

```bash
pytest
ruff check .
```

## Task Suite Summary

SRE-Zero Mini v0.1 includes 15 deterministic incident tasks backed by JSON configs in `srezero/task_configs/`.

| Task | Difficulty | Root Cause |
| --- | --- | --- |
| `cache_crash` | easy | Cache service crashed |
| `web_worker_crash` | easy | Web worker process crashed |
| `database_disk_full` | easy | Database disk is full |
| `cache_memory_pressure` | easy | Cache memory limit is too low |
| `db_pool_exhaustion` | medium | Database connection pool exhaustion |
| `cache_latency_degradation` | medium | Cache TTL configuration too low |
| `db_slow_queries_missing_index` | medium | Missing database index causing slow queries |
| `web_worker_saturation` | medium | Web worker pool too small |
| `cache_eviction_storm` | medium | Cache eviction storm due to low memory |
| `db_query_timeout_low` | medium | Database query timeout too low |
| `web_timeout_misconfig` | hard | Web timeout configuration too low |
| `misleading_web_500_db_rootcause` | hard | Database saturation causing web failures |
| `web_cache_host_misconfig` | hard | Web cache host configuration is wrong |
| `cascading_db_latency` | hard | Database read latency causing cascading latency |
| `cache_disabled_config_regression` | hard | Web cache usage disabled by config regression |

Formal split files:

- `easy`: 4 tasks
- `medium`: 6 tasks
- `hard`: 5 tasks

The split manifest is `srezero/task_splits.json`.

## APIs

The primary API is `SREEnv`:

```python
from srezero import SREEnv

env = SREEnv()
obs = env.reset(task_id="cache_crash", seed=0)
result = env.step("check_status(cache)")
```

The Gym-style API is `SREOpenEnv`:

```python
from srezero import SREOpenEnv

env = SREOpenEnv(task_id="cache_crash")
obs, info = env.reset(seed=0)
obs, reward, terminated, truncated, info = env.step("check_status(cache)")
```

## Frontend

The `frontend/` directory contains a Next.js console for using SRE-Zero interactively. It provides:

- Task browsing by easy/medium/hard split.
- Episode reset and session state.
- Structured action builder and raw action input.
- Observation details, known findings, reward components, metrics, and trajectory history.

The frontend uses local Next API routes and the deterministic JSON task configs. It does not control real infrastructure.

## Baseline Agents

- `RandomAgent`: samples action templates with deterministic randomness. It intentionally sometimes emits invalid service names to test environment robustness.
- `ScriptedExpertAgent`: uses a small task-specific policy table as an approximate upper bound. In v0.1 this policy is allowed to know task solutions, and this limitation is documented in the benchmark notes.
- `PromptingBaselineAgent`: calls an OpenAI-compatible chat completions endpoint with the current observation and asks for one action.
- `ReActBaselineAgent`: keeps a compact Thought/Action history across an episode and calls an OpenAI-compatible chat completions endpoint.
- `OpenSourceLLMBaselineAgent`: prompting profile intended for local or hosted open-source OpenAI-compatible servers.
- `FrontierLLMBaselineAgent`: ReAct profile intended for hosted frontier models.

## Baseline Checklist

- [ ] Run random baseline: `python eval/run_eval.py --agent random --episodes 5`
- [ ] Run scripted expert baseline: `python eval/run_eval.py --agent scripted --episodes 5`
- [ ] Run prompting baseline: `python eval/run_eval.py --agent prompting --episodes 1`
- [ ] Run ReAct-style baseline: `python eval/run_eval.py --agent react --episodes 1`
- [ ] Run open-source LLM baseline: `python eval/run_eval.py --agent open_source --episodes 1`
- [ ] Run frontier model baseline: `python eval/run_eval.py --agent frontier --episodes 1`

## Roadmap

- Add more task families and variants.
- Add hidden stochastic perturbations while preserving reproducibility.
- Add richer action costs and remediation side effects.
- Add trajectory export and comparison tools.
- Add optional Docker-backed scenarios after the simulator contract stabilizes.
- Add external LLM agent adapters without making them required.

## Phase 1 Status

- [x] Build SRE-Zero environment
- [x] Create 15-30 incident-response tasks
- [x] Add easy/medium/hard splits
- [x] Implement OpenEnv/Gym-style API
- [x] Add deterministic task configs
- [x] Add reward functions
- [x] Add evaluation metrics

## Citation

Citation metadata will be added when the benchmark paper draft is available.
