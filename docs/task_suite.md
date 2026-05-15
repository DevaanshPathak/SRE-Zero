# Task Suite

SRE-Zero Mini v0.1 contains 25 deterministic incident-response tasks. Task configs live in `srezero/task_configs/*.json`, and the formal difficulty split manifest is `srezero/task_splits.json`.

## Splits

| Split | Count | Tasks |
| --- | ---: | --- |
| easy | 7 | `cache_crash`, `web_worker_crash`, `database_disk_full`, `cache_memory_pressure`, `message_queue_crash`, `load_balancer_health_check_misconfig`, `message_queue_backlog_consumers_low` |
| medium | 10 | `db_pool_exhaustion`, `cache_latency_degradation`, `db_slow_queries_missing_index`, `web_worker_saturation`, `cache_eviction_storm`, `db_query_timeout_low`, `load_balancer_connection_limit_low`, `message_queue_retry_limit_low`, `load_balancer_sticky_session_hotspot`, `message_queue_visibility_timeout_low` |
| hard | 8 | `web_timeout_misconfig`, `misleading_web_500_db_rootcause`, `web_cache_host_misconfig`, `cascading_db_latency`, `cache_disabled_config_regression`, `misleading_queue_backlog_db_rootcause`, `misleading_lb_502_cache_rootcause`, `load_balancer_bad_backend_weight` |

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
| `message_queue_crash` | easy | Message queue service crashed | Restart `message_queue` |
| `load_balancer_health_check_misconfig` | easy | Load balancer health check path misconfigured | Set `load_balancer.HEALTH_CHECK_PATH` |
| `message_queue_backlog_consumers_low` | easy | Message queue consumer concurrency too low | Increase `message_queue.CONSUMER_CONCURRENCY` |
| `load_balancer_connection_limit_low` | medium | Load balancer maximum connections too low | Increase `load_balancer.MAX_CONNECTIONS` |
| `message_queue_retry_limit_low` | medium | Message queue retry limit too low | Increase `message_queue.RETRY_LIMIT` |
| `load_balancer_sticky_session_hotspot` | medium | Sticky sessions causing backend hotspot | Disable `load_balancer.STICKY_SESSIONS` |
| `message_queue_visibility_timeout_low` | medium | Message queue visibility timeout too low | Increase `message_queue.VISIBILITY_TIMEOUT_MS` |
| `misleading_queue_backlog_db_rootcause` | hard | Database read latency causing queue backlog | Enable `database.READ_REPLICA_ENABLED` |
| `misleading_lb_502_cache_rootcause` | hard | Cache crash causing web and edge 502s | Restart `cache` |
| `load_balancer_bad_backend_weight` | hard | Load balancer backend weight misconfigured | Set `load_balancer.WEB_WEIGHT_PRIMARY` |

## Design Notes

Each task config contains:

- Alert text visible to the agent.
- Hidden root cause and root-cause matching keywords.
- Relevant evidence keys and visible finding descriptions.
- Service state patches for logs, metrics, status, and config.
- Correct remediation validator.
- Expected action pattern for the scripted expert baseline.
- Distractors and metadata.
- Optional distractor services for measuring distractor-driven wrong fixes.

The agent never sees hidden root-cause fields, correct-fix fields, or reward internals in the observation.
