"""Crawler tuning constants.

Values were chosen from live repositoryCount probes on 2026-08-29:

    stars:>=500                                 122,279
    stars:>=1000                                 64,422
    stars:>=2000                                 32,970   <- crawl floor
    stars:>=5000                                 12,450
    stars:>=2000  active                         18,393
    stars:>=12000 active                          3,248   <- publish gate
    stars:>=15000 active                          2,472

"active" = pushed within 180 days and not archived.
"""

# Crawl floor. Every repo at or above this is tracked in the dataset, whether or
# not it ever gets a page. Lowering it grows the daily snapshot linearly:
# 33k repos is ~250KB gzipped per day (~90MB/year of immutable blobs), while a
# 500-star floor would be ~330MB/year.
MIN_STARS = 2000

# Upper bound for the sharding search space. No repository is close to this, so
# it just gives the recursive bisection a finite top end.
MAX_STARS = 1_000_000

# GitHub's search connection silently stops at 1000 results no matter how far
# pagination is followed. Any range holding this many repos must be split.
SEARCH_RESULT_CAP = 1000

# Max nodes per request. GraphQL search costs 1 rate-limit point per request
# regardless of page size, so the largest allowed page is also the cheapest.
PAGE_SIZE = 100

# Abort rather than degrade: if the hourly budget drops below this mid-run,
# something is wrong and a partial dataset is worse than no run at all.
MIN_RATE_LIMIT_REMAINING = 200

# Shard counts are sampled at slightly different moments than the total, and
# real repos cross thresholds during a run. Allow drift before failing the
# sharding self-check.
SHARD_SUM_TOLERANCE = 0.02

# Refuse to overwrite repos.jsonl if a run returns dramatically fewer repos than
# the last one. Guards first_seen (which is not recoverable) against a partial
# fetch caused by an API outage.
MIN_FETCH_RATIO = 0.80

# Network retry policy for transient 5xx and secondary rate limits.
MAX_RETRIES = 5
RETRY_BASE_DELAY = 2.0
