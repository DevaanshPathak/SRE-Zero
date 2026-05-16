# Benchmark Status

Current status: implemented for the simulator benchmark baseline.

- [x] Build SRE-Zero environment
- [x] Create initial 15-30 incident-response tasks
- [x] Add 15 additional incident-response tasks
- [x] Add easy/medium/hard splits
- [x] Implement OpenEnv/Gym-style API
- [x] Add deterministic task configs
- [x] Add reward functions
- [x] Add evaluation metrics
- [x] Add basic result plotting
- [x] Expand services to include message queue and load balancer
- [x] Add train/dev/test and unseen-incident splits
- [x] Add standardized scoring
- [x] Add final benchmark API
- [x] Add paper-ready result table writer

Notes:

- The current suite has 40 deterministic tasks across `web_server`, `database`, `cache`, `message_queue`, and `load_balancer`.
- Task definitions are JSON configs under `srezero/task_configs/`.
- The split manifest is `srezero/task_splits.json` and includes both difficulty
  and benchmark splits.
- Distractor services are tracked for distractor failure rate in aggregate metrics.
- `SREEnv` remains the low-level environment API.
- `SREOpenEnv` provides a Gym-style wrapper without requiring Gymnasium as a dependency.
- `srezero.benchmark` exposes the public paper-facing API and standard scoring.
