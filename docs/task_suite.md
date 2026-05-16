# Task Suite

SRE-Zero v0.6 contains 40 deterministic incident-response tasks. Task configs
live in `srezero/task_configs/*.json`, and the formal split manifest is
`srezero/task_splits.json`.

## Splits

### Difficulty Splits

| Split | Count |
| --- | ---: |
| easy | 11 |
| medium | 16 |
| hard | 13 |

### Benchmark Splits

| Split | Count | Purpose |
| --- | ---: | --- |
| train | 24 | Development and prompt/policy iteration. |
| dev | 8 | Model and prompt selection without touching final test. |
| test | 8 | Final held-out reporting split. |
| unseen_incident | 8 | Held-out incident-generalization subset of `test`. |

The `unseen_incident` split is a held-out incident-generalization subset of
`test`. It is intentionally not used for prompt or policy development.

## Tasks

| Task | Difficulty | Hidden root cause | Correct fix |
| --- | --- | --- | --- |
| `cache_crash` | easy | cache service crashed | Restart `cache` |
| `web_worker_crash` | easy | web server worker process crashed | Restart `web_server` |
| `database_disk_full` | easy | database disk is full | Increase `database.DISK_QUOTA_GB` |
| `cache_memory_pressure` | easy | cache memory limit is too low | Increase `cache.MAX_MEMORY_MB` |
| `message_queue_crash` | easy | message queue service crashed | Restart `message_queue` |
| `load_balancer_health_check_misconfig` | easy | load balancer health check path misconfigured | Set `load_balancer.HEALTH_CHECK_PATH` to `/healthz` |
| `message_queue_backlog_consumers_low` | easy | message queue consumer concurrency too low | Increase `message_queue.CONSUMER_CONCURRENCY` |
| `web_server_memory_leak_restart` | easy | web server memory leak caused worker crashes | Restart `web_server` |
| `database_maintenance_mode_left_on` | easy | database maintenance mode was left enabled | Set `database.MAINTENANCE_MODE` to `false` |
| `cache_auth_token_expired` | easy | cache authentication token expired | Set `cache.AUTH_TOKEN_VALID` to `true` |
| `load_balancer_tls_cert_expired` | easy | load balancer TLS certificate expired | Set `load_balancer.TLS_CERT_VALID` to `true` |
| `db_pool_exhaustion` | medium | database connection pool exhaustion | Increase `database.DB_POOL_SIZE` |
| `cache_latency_degradation` | medium | cache hit rate degraded due to wrong cache TTL config | Increase `cache.TTL_SECONDS` |
| `db_slow_queries_missing_index` | medium | database missing index causing slow queries | Set `database.INDEX_ORDERS_USER_ID` to `true` |
| `web_worker_saturation` | medium | web server worker pool too small | Increase `web_server.MAX_WORKERS` |
| `cache_eviction_storm` | medium | cache eviction storm due to low memory | Increase `cache.MAX_MEMORY_MB` |
| `db_query_timeout_low` | medium | database query timeout configuration too low | Increase `database.QUERY_TIMEOUT_MS` |
| `load_balancer_connection_limit_low` | medium | load balancer maximum connections too low | Increase `load_balancer.MAX_CONNECTIONS` |
| `message_queue_retry_limit_low` | medium | message queue retry limit too low | Increase `message_queue.RETRY_LIMIT` |
| `load_balancer_sticky_session_hotspot` | medium | load balancer sticky sessions causing backend hotspot | Set `load_balancer.STICKY_SESSIONS` to `false` |
| `message_queue_visibility_timeout_low` | medium | message queue visibility timeout too low | Increase `message_queue.VISIBILITY_TIMEOUT_MS` |
| `web_rate_limit_too_low` | medium | web server rate limit configured too low | Increase `web_server.RATE_LIMIT_RPS` |
| `database_autovacuum_disabled` | medium | database autovacuum disabled | Set `database.AUTOVACUUM_ENABLED` to `true` |
| `cache_compression_disabled` | medium | cache compression disabled | Set `cache.COMPRESSION_ENABLED` to `true` |
| `message_queue_max_in_flight_low` | medium | message queue max in-flight limit too low | Increase `message_queue.MAX_IN_FLIGHT` |
| `load_balancer_idle_timeout_low` | medium | load balancer idle timeout too low | Increase `load_balancer.IDLE_TIMEOUT_MS` |
| `web_queue_publish_timeout_low` | medium | web server queue publish timeout too low | Increase `web_server.QUEUE_PUBLISH_TIMEOUT_MS` |
| `web_timeout_misconfig` | hard | web server timeout configuration too low | Increase `web_server.TIMEOUT_MS` |
| `misleading_web_500_db_rootcause` | hard | database saturation causing web failures | Increase `database.DB_POOL_SIZE` |
| `web_cache_host_misconfig` | hard | web server cache host configuration is wrong | Set `web_server.CACHE_HOST` to `cache.internal` |
| `cascading_db_latency` | hard | database read latency causing cascading service latency | Set `database.READ_REPLICA_ENABLED` to `true` |
| `cache_disabled_config_regression` | hard | web server cache usage disabled by configuration regression | Set `web_server.USE_CACHE` to `true` |
| `misleading_queue_backlog_db_rootcause` | hard | database read latency causing queue consumer backlog | Set `database.READ_REPLICA_ENABLED` to `true` |
| `misleading_lb_502_cache_rootcause` | hard | cache service crashed causing web upstream failures | Restart `cache` |
| `load_balancer_bad_backend_weight` | hard | load balancer backend weight misconfigured | Set `load_balancer.WEB_WEIGHT_PRIMARY` to `50` |
| `misleading_cache_miss_db_index_rootcause` | hard | database missing product search index causing slow cache refill | Set `database.INDEX_PRODUCTS_SKU` to `true` |
| `misleading_lb_503_web_worker_rootcause` | hard | web worker saturation causing load balancer 503s | Increase `web_server.MAX_WORKERS` |
| `message_queue_poison_message_retry_storm` | hard | message queue retry limit too high for poison messages | Set `message_queue.RETRY_LIMIT` to `3` |
| `database_read_replica_disabled_misleading_cache` | hard | database read replica disabled causing cache refill latency | Set `database.READ_REPLICA_ENABLED` to `true` |
| `misleading_web_timeouts_lb_idle_timeout` | hard | load balancer idle timeout lower than web response time | Increase `load_balancer.IDLE_TIMEOUT_MS` |

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

The agent never sees hidden root-cause fields, correct-fix fields, or reward
internals in the observation.
