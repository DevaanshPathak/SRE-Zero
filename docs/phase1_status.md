# Phase 1 Status

Current status: implemented for the Phase 1 simulator baseline.

- [x] Build SRE-Zero environment
- [x] Create 15-30 incident-response tasks
- [x] Add easy/medium/hard splits
- [x] Implement OpenEnv/Gym-style API
- [x] Add deterministic task configs
- [x] Add reward functions
- [x] Add evaluation metrics

Notes:

- The current suite has 15 deterministic tasks, which is the lower bound of the Phase 1 target range.
- Task definitions are JSON configs under `srezero/task_configs/`.
- The split manifest is `srezero/task_splits.json`.
- `SREEnv` remains the primary benchmark API.
- `SREOpenEnv` provides a Gym-style wrapper without requiring Gymnasium as a dependency.

