# SRE-Zero

SRE-Zero is an early-stage research benchmark for studying reliable tool-using LLM agents in simulated incident-response workflows.

The v0.6 repository contains **SRE-Zero Mini**, a deterministic environment where agents diagnose incidents across simulated `web_server`, `database`, `cache`, `message_queue`, and `load_balancer` services. Agents inspect logs, metrics, status, and config, then apply minimal in-memory remediations under a step budget.

This is early research code. It is intentionally small, safe, and simulation-only. It does not control real infrastructure or execute arbitrary shell commands. External LLM APIs are optional and are only called when an LLM baseline is explicitly selected.

## Research Motivation

Many agent benchmarks measure final answer quality without grounding the agent in a stateful operational environment. SRE-Zero focuses on a narrower question: can a tool-using agent gather relevant evidence, distinguish symptoms from root causes, apply minimal fixes, and resolve incidents reliably?

The initial benchmark emphasizes:

- Deterministic incident tasks.
- Formal easy/medium/hard task splits.
- Train/dev/test and unseen-incident benchmark splits.
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
./start-frontend.sh
```

Then open `http://localhost:3000`.

Run the optional Python HTTP backend:

```bash
./start-backend.sh
```

The backend listens on `http://127.0.0.1:8000` by default and exposes `/health`, `/tasks`, `/episode/reset`, and `/episode/step`.

Run a difficulty split:

```bash
python eval/run_eval.py --agent scripted --difficulty hard --episodes 1
```

Run a benchmark split with standardized scoring:

```bash
python eval/run_benchmark.py --agent scripted --split test --episodes 1 --seed 0
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

Generate a JSON report with raw records and model-wise marks:

```bash
python eval/run_baseline_marks.py --baselines all --episodes 1 --output notes/runs/baseline_marks.json
python eval/run_baseline_marks.py --baselines prompting react --models openai/gpt-5-mini openai/gpt-5.4-mini
```

Run only non-API baselines:

```bash
python eval/run_baseline_marks.py --baselines all --no-api --episodes 3
```

Run one baseline episode and save its trajectory:

```bash
python eval/run_agent.py --agent scripted --task misleading_web_500_db_rootcause
```

Run the full default sweep:

```bash
python eval/run_all_eval.py --preset paper --timeout-seconds 60
```

For budgeted daily collection, see `evals.md`. It splits the paper preset into
day-wise commands that write JSONs under `notes/runs/`.

The full sweep prints a run plan, timestamped start/end logs for each baseline/model
run, and live progress bars for task/episode progress. It also writes a log file to
`notes/runs/run_all_eval.log` by default.

The `paper` preset compares 4-5 models inside each LLM baseline bucket:

- `prompting`: `openai/gpt-5-mini`, `openai/gpt-5.4-mini`, `google/gemini-3.1-flash-lite`, `qwen/qwen3.6-flash`, `mistralai/mistral-medium-3-5`
- `react`: `openai/gpt-5-mini`, `openai/gpt-5.4`, `anthropic/claude-sonnet-4.6`, `google/gemini-3.1-pro-preview`, `x-ai/grok-4.3`
- `open_source`: `ibm-granite/granite-4.1-8b`, `inclusionai/ring-2.6-1t:free`, `qwen/qwen3.6-35b-a3b`, `nvidia/nemotron-3-super-120b-a12b:free`, `google/gemma-4-26b-a4b-it:free`
- `frontier`: `openai/gpt-5.5`, `anthropic/claude-opus-4.7-fast`, `google/gemini-3.1-pro-preview`, `x-ai/grok-4.3`, `mistralai/mistral-medium-3-5`

Use a smaller smoke preset:

```bash
python eval/run_all_eval.py --preset quick --timeout-seconds 60
```

Create basic SVG plots from a combined results JSON:

```bash
python eval/plot_results.py --input notes/runs/all_eval_summary.json --output-dir notes/plots/latest
```

Create paper-ready Markdown result tables:

```bash
python eval/write_result_tables.py --input notes/runs/all_eval_summary.json --output-dir notes/tables/latest
```

Disable the log file or choose a custom path:

```bash
python eval/run_all_eval.py --preset quick --no-log-file
python eval/run_all_eval.py --preset paper --log-file notes/runs/paper_sweep.log
```

Override any model bucket:

```bash
python eval/run_all_eval.py \
  --prompting-models openai/gpt-5-mini \
  --react-models openai/gpt-5-mini \
  --open-source-models ibm-granite/granite-4.1-8b inclusionai/ring-2.6-1t:free \
  --frontier-models openai/gpt-5.5 anthropic/claude-opus-4.7-fast \
  --summary-output notes/runs/all_eval_summary.json
```

Run tests and lint:

```bash
pytest
ruff check .
```

## Task Suite Summary

SRE-Zero v0.6 includes 40 deterministic incident tasks backed by JSON configs in `srezero/task_configs/`.

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
| `message_queue_crash` | easy | Message queue service crashed |
| `load_balancer_health_check_misconfig` | easy | Load balancer health check path misconfigured |
| `message_queue_backlog_consumers_low` | easy | Message queue consumer concurrency too low |
| `web_server_memory_leak_restart` | easy | Web server memory leak caused worker crashes |
| `database_maintenance_mode_left_on` | easy | Database maintenance mode left enabled |
| `cache_auth_token_expired` | easy | Cache authentication token expired |
| `load_balancer_tls_cert_expired` | easy | Load balancer TLS certificate expired |
| `load_balancer_connection_limit_low` | medium | Load balancer maximum connections too low |
| `message_queue_retry_limit_low` | medium | Message queue retry limit too low |
| `load_balancer_sticky_session_hotspot` | medium | Sticky sessions causing backend hotspot |
| `message_queue_visibility_timeout_low` | medium | Message queue visibility timeout too low |
| `web_rate_limit_too_low` | medium | Web server rate limit too low |
| `database_autovacuum_disabled` | medium | Database autovacuum disabled |
| `cache_compression_disabled` | medium | Cache compression disabled |
| `message_queue_max_in_flight_low` | medium | Message queue max in-flight limit too low |
| `load_balancer_idle_timeout_low` | medium | Load balancer idle timeout too low |
| `web_queue_publish_timeout_low` | medium | Web server queue publish timeout too low |
| `misleading_queue_backlog_db_rootcause` | hard | Database latency causing queue backlog |
| `misleading_lb_502_cache_rootcause` | hard | Cache crash causing load-balancer 502s |
| `load_balancer_bad_backend_weight` | hard | Load balancer backend weight misconfigured |
| `misleading_cache_miss_db_index_rootcause` | hard | Database missing index causing slow cache refills |
| `misleading_lb_503_web_worker_rootcause` | hard | Web worker saturation causing load-balancer 503s |
| `message_queue_poison_message_retry_storm` | hard | Poison messages causing queue retry storm |
| `database_read_replica_disabled_misleading_cache` | hard | Disabled read replica causing cache refill latency |
| `misleading_web_timeouts_lb_idle_timeout` | hard | Load-balancer idle timeout causing web timeout symptoms |

Formal split files:

- `easy`: 11 tasks
- `medium`: 16 tasks
- `hard`: 13 tasks
- `train`: 24 tasks
- `dev`: 8 tasks
- `test`: 8 tasks
- `unseen_incident`: 8 held-out test tasks

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

The final benchmark API exposes stable catalog, split, environment, and scoring helpers:

```python
from srezero import benchmark_spec, benchmark_task_ids, make_env

spec = benchmark_spec()
task_ids = benchmark_task_ids(split="test")
env = make_env(task_id=task_ids[0])
```

See `docs/benchmark_api.md` for the public API, reproducible commands, and
standardized scoring formula.

## Frontend

The `frontend/` directory contains a Next.js console for using SRE-Zero interactively. It provides:

- Task browsing by easy/medium/hard split.
- Episode reset and session state.
- Structured action builder and raw action input.
- Observation details, known findings, reward components, metrics, and trajectory history.
- Model selection from `OPENAI_MODEL` plus local `notes/available_models.md`.
- Side-by-side prompting baseline comparison for two selected OpenAI-compatible models.

The frontend uses local Next API routes and the deterministic JSON task configs. It does not control real infrastructure.

Model comparison requires `.env` with `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. The API key is read server-side only and is not returned to the browser.

The root `start-frontend.sh` script starts the Next dev server. The root `start-backend.sh` script starts a lightweight Python stdlib backend for API experimentation.

## Baseline Agents

- `RandomAgent`: samples action templates with deterministic randomness. It intentionally sometimes emits invalid service names to test environment robustness.
- `ScriptedExpertAgent`: uses a small task-specific policy table as an approximate upper bound. In v0.6 this policy is allowed to know task solutions, and this limitation is documented in the benchmark notes.
- `PromptingBaselineAgent`: calls an OpenAI-compatible chat completions endpoint with the current observation and asks for one action.
- `ReActBaselineAgent`: keeps a compact Thought/Action history across an episode and calls an OpenAI-compatible chat completions endpoint.
- `OpenSourceLLMBaselineAgent`: prompting profile intended for local or hosted open-source OpenAI-compatible servers.
- `FrontierLLMBaselineAgent`: ReAct profile intended for hosted frontier models.

Prompt templates, agent-runner notes, baseline result table guidance, and failure
examples are documented in `docs/baseline_agents.md`.

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

## Benchmark Status

- [x] Build SRE-Zero environment
- [x] Create initial 15-30 incident-response tasks
- [x] Add 15 additional incident-response tasks
- [x] Add train/dev/test and unseen-incident splits
- [x] Add easy/medium/hard splits
- [x] Implement OpenEnv/Gym-style API
- [x] Add deterministic task configs
- [x] Add reward functions
- [x] Add evaluation metrics
- [x] Add standardized scoring
- [x] Add final benchmark API
- [x] Add basic result plotting

## Citation

Citation metadata will be added when the benchmark paper draft is available.
