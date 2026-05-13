# Environment Design

SRE-Zero Mini is a deterministic, simulation-only environment for incident-response agents. It models a small service graph with three services:

- `web_server`
- `database`
- `cache`

Each service has simulated status, logs, metrics, configuration, and dependency metadata. Actions mutate only in-memory simulator state.

## Episode Flow

1. `SREEnv.reset(task_id, seed)` loads an incident task.
2. The agent receives an alert, available tools, and an initial observation.
3. The agent submits one structured action.
4. The environment returns a new observation, shaping reward, terminal flag, and inspectable info.
5. The episode ends when the incident is resolved, the step budget is exhausted, escalation occurs, or an incorrect final resolution terminates the task.

## Observation Space

Observations include:

- Incident id.
- Current step and remaining steps.
- Alert text.
- Last action and result.
- Known findings gathered so far.
- Available action templates.
- Done flag.

Observations intentionally exclude hidden root causes, correct fixes, reward internals, and full task solutions.

## Action Space

Actions are represented by Pydantic `Action` objects and can also be submitted as strings:

```text
inspect_logs(web_server)
inspect_metrics(database)
check_status(cache)
inspect_config(web_server, TIMEOUT_MS)
restart_service(cache)
update_config(database, DB_POOL_SIZE, 100)
resolve_incident(database connection pool exhaustion, increase database pool size)
escalate(need human operator)
```

Invalid actions return controlled error observations and penalties. They never crash the environment.

