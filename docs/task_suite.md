# Task Suite

SRE-Zero Mini v0.1 contains five deterministic incidents.

## `cache_crash`

- Difficulty: easy
- Alert: "Users are seeing elevated latency. Cache hit rate has dropped suddenly."
- Hidden root cause: cache service crashed
- Relevant evidence: cache status, cache logs, cache metrics
- Distractors: none
- Correct fix: restart cache
- Expected behavior: inspect cache health, restart cache, submit the cache crash resolution.

## `db_pool_exhaustion`

- Difficulty: medium
- Alert: "Checkout is returning intermittent 500 errors."
- Hidden root cause: database connection pool exhaustion
- Relevant evidence: web logs show checkout 500s; database metrics show connections near max
- Distractors: web errors are symptoms rather than the root cause
- Correct fix: increase `database.DB_POOL_SIZE`
- Expected behavior: inspect web logs, inspect database metrics, update database pool size, resolve.

## `web_timeout_misconfig`

- Difficulty: hard
- Alert: "Users report intermittent timeouts on the API."
- Hidden root cause: web server timeout configuration too low
- Relevant evidence: web logs show upstream timeout; web config has `TIMEOUT_MS` too low
- Distractors: upstream services appear in timeout logs but are not saturated
- Correct fix: increase `web_server.TIMEOUT_MS`
- Expected behavior: inspect web logs, inspect web timeout config, update timeout, resolve.

## `cache_latency_degradation`

- Difficulty: medium
- Alert: "Application latency has increased across product pages."
- Hidden root cause: cache hit rate degraded due to wrong cache TTL config
- Relevant evidence: cache metrics show low hit rate; cache config has `TTL_SECONDS` too low
- Distractors: web latency is a symptom of cache misses
- Correct fix: increase `cache.TTL_SECONDS`
- Expected behavior: inspect cache metrics, inspect cache TTL config, update TTL, resolve.

## `misleading_web_500_db_rootcause`

- Difficulty: hard
- Alert: "Web server is producing frequent 500 errors."
- Hidden root cause: database saturation causing web failures
- Relevant evidence: web logs point to downstream database waits; database metrics show saturation
- Distractors: web logs look severe, but restarting `web_server` does not solve the incident
- Correct fix: increase `database.DB_POOL_SIZE`
- Expected behavior: inspect web logs, inspect database metrics, avoid the web restart distractor, update database pool size, resolve.

