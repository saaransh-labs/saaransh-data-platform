## Bug Fixes & Their Validity

You identified 5 concerns, all of which were valid:

1. **Semaphore held during retries/sleeps** — blocks other tasks from running while sleeping inside the retry loop.
2. **Race condition in `ResultAggregator`** — technically not a real bug in asyncio (no await between stat increments), but worth knowing why.
3. **Cookie refresh stampede** — all tasks refresh cookies simultaneously on startup and on 403s.
4. **403 refresh race** — same root cause as #3 but triggered mid-run, potentially worsening the block.
5. **Wrong exception type** — `aiohttp.ContentTypeError` is never caught by `except ValueError`; it silently falls into the broader `ClientError` block.

Plus additional issues: shared session Referer inconsistency, blunt timeout with no per-stage limits, `gather` swallowing exceptions, and no retry on empty responses.

---

## Deeper Concepts You Worked Through

**Semaphore vs Rate Limiter** — these are two separate concerns. Semaphore limits concurrency, rate limiter limits request frequency. You need both, and they serve different purposes.

**Concurrent vs Sequential with delay** — at a fixed rate like 1 req/s with consistent response times, they're equivalent in throughput. Concurrency earns its complexity only when response latency is variable — slow outliers don't stall the pipeline.

**Cookie stampede fix** — a shared `asyncio.Lock` with a "already refreshed" flag ensures only one task does the refresh; others wait and reuse the result. The cookie jar is already shared — the problem was redundant concurrent writes to it.

**Timeout granularity** — `ClientTimeout(total=5)` is one blunt cutoff. Splitting into `connect`, `sock_read`, and `total` gives you meaningful failure detection at each stage of the request lifecycle.

**Rate limiter `min_interval`** — start at 1s, tune empirically. Add jitter on top so requests don't look mechanically periodic. With a rate limiter as the binding constraint, `MAX_CONCURRENT` only helps absorb latency variance, not increase throughput.