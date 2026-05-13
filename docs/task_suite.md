# Task Suite

SRE-Zero Mini v0.1 contains 15 deterministic incident-response tasks. Task configs live in `srezero/task_configs/*.json`, and the formal difficulty split manifest is `srezero/task_splits.json`.

## Splits

| Split | Count | Tasks |
| --- | ---: | --- |
| easy | 4 | `cache_crash`, `web_worker_crash`, `database_disk_full`, `cache_memory_pressure` |
| medium | 6 | `db_pool_exhaustion`, `cache_latency_degradation`, `db_slow_queries_missing_index`, `web_worker_saturation`, `cache_eviction_storm`, `db_query_timeout_low` |
| hard | 5 | `web_timeout_misconfig`, `misleading_web_500_db_rootcause`, `web_cache_host_misconfig`, `cascading_db_latency`, `cache_disabled_config_regression` |

## Tasks

| Task | Difficulty | Hidden root cause | Correct fix |
| --- | --- | --- | --- |
| `cache_crash` | easy | Cache service crashed | Restart `cache` |
| `web_worker_crash` | easy | Web worker process crashed | Restart `web_server` |
| `database_disk_full` | easy | Database disk is full | Increase `database.DISK_QUOTA_GB` |
| `cache_memory_pressure` | easy | Cache memory limit too low | Increase `cache.MAX_MEMORY_MB` |
| `db_pool_exhaustion` | medium | Database connection pool exhaustion | Increase `database.DB_POOL_SIZE` |
| `cache_latency_degradation` | medium | Cache TTL too low | Increase `cache.TTL_SECONDS` |
| `db_slow_queries_missing_index` | medium | Missing database index causing slow queries | Enable `database.INDEX_ORDERS_USER_ID` |
| `web_worker_saturation` | medium | Web worker pool too small | Increase `web_server.MAX_WORKERS` |
| `cache_eviction_storm` | medium | Cache eviction storm from low memory | Increase `cache.MAX_MEMORY_MB` |
| `db_query_timeout_low` | medium | Database query timeout too low | Increase `database.QUERY_TIMEOUT_MS` |
| `web_timeout_misconfig` | hard | Web timeout configuration too low | Increase `web_server.TIMEOUT_MS` |
| `misleading_web_500_db_rootcause` | hard | Database saturation causing web failures | Increase `database.DB_POOL_SIZE` |
| `web_cache_host_misconfig` | hard | Web cache host points to wrong endpoint | Set `web_server.CACHE_HOST` |
| `cascading_db_latency` | hard | Database read latency causing cascading latency | Enable `database.READ_REPLICA_ENABLED` |
| `cache_disabled_config_regression` | hard | Web cache usage disabled by config regression | Enable `web_server.USE_CACHE` |

## Design Notes

Each task config contains:

- Alert text visible to the agent.
- Hidden root cause and root-cause matching keywords.
- Relevant evidence keys and visible finding descriptions.
- Service state patches for logs, metrics, status, and config.
- Correct remediation validator.
- Expected action pattern for the scripted expert baseline.
- Distractors and metadata.

The agent never sees hidden root-cause fields, correct-fix fields, or reward internals in the observation.

