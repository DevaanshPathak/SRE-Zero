# Baseline Agents

SRE-Zero includes deterministic and optional API-backed baseline agents. The
baseline layer is intentionally simple: it is meant to expose environment
behavior and failure modes, not to be a tuned agent stack.

## Implemented Agents

| Agent | API required | Description |
| --- | --- | --- |
| `random` | no | Samples structured actions with seeded randomness and occasional invalid services. |
| `scripted` | no | Follows each task config's expected action pattern as an approximate upper bound. |
| `prompting` | yes | Sends the current observation to an OpenAI-compatible chat endpoint and asks for one action. |
| `react` | yes | Maintains a compact Thought/Action history and asks for one action per step. |
| `open_source` | yes | Prompting profile for local or hosted OpenAI-compatible open-source models. |
| `frontier` | yes | ReAct profile for stronger hosted models. |

## Prompt Templates

Prompt templates live in `baselines/prompts.py`. They are shared by the LLM
agents so paper experiments can cite one stable prompt source.

The prompting-only system prompt instructs the model to:

- use only simulator actions,
- gather evidence before remediation,
- apply minimal fixes,
- return exactly one action call,
- include required arguments such as `inspect_metrics(cache)`,
- use only valid services: `web_server`, `database`, `cache`, `message_queue`,
  and `load_balancer`.

The ReAct template requires:

```text
Thought: <brief reasoning>
Action: <one valid action call>
```

Only the `Action:` line is executed by the environment. The reasoning text is
kept in the model context but is not treated as a simulator action.

## Agent Runner

Use `eval/run_agent.py` to run one episode and save a trajectory JSON:

```bash
python eval/run_agent.py --agent scripted --task misleading_web_500_db_rootcause \
  --output notes/runs/agent_episode.json
```

The runner blocks API-backed agents unless `--allow-api` is explicit:

```bash
python eval/run_agent.py --agent react --task cache_crash --allow-api
```

This makes no-API smoke checks safer.

## Evaluation Harness

Use `eval/run_eval.py` for one agent over the task suite:

```bash
python eval/run_eval.py --agent random --episodes 5
python eval/run_eval.py --agent scripted --episodes 5
```

Use `eval/run_baseline_marks.py` for model-wise marks tables. To avoid API calls,
use `--no-api`:

```bash
python eval/run_baseline_marks.py --baselines all --no-api --episodes 3 \
  --output notes/runs/baseline_agents_no_api/summary.json
```

Use `eval/run_all_eval.py` for full sweeps when API-backed LLM runs are intended.

## No-API Baseline Table

The latest no-API smoke table was generated with deterministic baselines only:

| Baseline | Model | Marks | Success | Reward | Evidence | Invalid | Steps | Errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `scripted` | `deterministic/scripted` | 93.4 | 1.00 | 0.943 | 1.00 | 0.00 | 4.60 | 0 |
| `random` | `deterministic/random` | 5.5 | 0.00 | 0.006 | 0.04 | 0.08 | 3.20 | 0 |

The API-backed baselines were intentionally skipped for this table:

- `prompting`
- `react`
- `open_source`
- `frontier`

## Failure Examples

Random baseline failure on `misleading_web_500_db_rootcause`:

```text
inspect_config(load_balancer, CONSUMER_CONCURRENCY)
check_status(cache)
escalate(random baseline escalation)
```

The alert concerns severe web errors caused by database saturation. The random
agent inspected unrelated load-balancer config, checked a healthy cache, and
escalated without gathering database evidence.

Scripted expert success on the same task:

```text
inspect_logs(web_server)
inspect_metrics(database)
inspect_config(database, DB_POOL_SIZE)
update_config(database, DB_POOL_SIZE, 150)
resolve_incident(database saturation causing web failures, increase database pool size)
```

This contrast is the intended role of the deterministic baselines: random gives
a floor, and scripted expert verifies that the task is solvable through the
environment's action space.

## Reporting Notes

LLM baseline results should report:

- provider and base URL family,
- model name,
- prompt template version,
- seed,
- episodes per task,
- task split,
- timeout,
- provider or parsing errors.

Do not compare LLM results against deterministic results without noting that the
scripted expert has task-specific policy access and is an upper-bound baseline.
