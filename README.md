# gitpulse

GitHub trending directory. Daily crawl → append-only snapshots → static site on GitHub Pages.
No server, no managed database, no paid infrastructure.

## Why the storage is text files

Star counts are only available as "right now" from the API — there is no way to ask what a
repo had last week. Velocity therefore has to be accumulated, one snapshot at a time, and
missing a day loses that day permanently.

Snapshots are immutable per-day gzipped JSONL rather than a committed SQLite file. Git
stores a fresh full blob every time a binary file changes, so a daily-committed database
would grow to multiple GB within a year with no way to reclaim it. One file per day, never
rewritten, stays one blob forever.

SQLite still does the querying — it is rebuilt in memory from these files when pages are
generated. Storage format and query engine are separate concerns.

## Layout

```
crawler/
  config.py           tuning constants, with the probe numbers behind them
  fetch_repos.py      GraphQL client + star-range sharding
  write_snapshot.py   first_seen merge, JSONL + gzip output
  test_crawler.py     self-checks, no network, no framework
data/
  repos.jsonl         current metadata, rewritten each run
  snapshots/          <date>.jsonl.gz, written once each
```

## The 1000-result trap

GitHub's `search` connection returns at most 1000 results however far the cursor is
followed. A plain `stars:>=2000` crawl returns exactly 1000 repos and looks successful.

Queries are therefore bounded to star ranges, and any range holding 1000 or more is
bisected until every shard fits. `fetch_all` refuses to return if a splittable shard came
back at the cap, and compares the sum of shard counts against the unsharded total.

## Running locally

```sh
export GITHUB_TOKEN=$(gh auth token)
python3 crawler/test_crawler.py     # self-checks
python3 crawler/fetch_repos.py      # sizing probe, writes nothing
python3 crawler/write_snapshot.py   # full crawl
```

## Current settings

| Setting | Value | Repos |
|---|---|---|
| Crawl floor | 2,000 stars | ~33,000 tracked |
| Publish gate | 12,000 stars, active | ~3,200 pages |

Probed live on 2026-08-29; see `crawler/config.py` for the full distribution.
Tracking far more repos than get pages is deliberate — the extra rows feed velocity for
repos that have not yet earned a page.

## Status

Phase 01 (crawler) implemented. Site generation, trending pages and SEO artifacts are
planned but not built.
