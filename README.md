# gitpulse

GitHub trending directory. Daily crawl → append-only snapshots → static site on GitHub Pages.
No server, no managed database, no paid infrastructure.

**Live:** https://thaitrn.github.io/gitpulse/

## Why the storage is text files

Star counts are only available as "right now" from the API — there is no way to ask what a
repo had last week. Velocity therefore has to be accumulated one snapshot at a time, and a
missed day is lost permanently.

Snapshots are immutable per-day gzipped JSONL rather than a committed SQLite file. Git
stores a fresh full blob every time a binary file changes, so a daily-committed database
would reach multiple GB within a year with no way to reclaim it. One file per day, never
rewritten, stays one blob forever.

SQLite still does the querying — it is rebuilt in memory from these files on every render.
Storage format and query engine are separate concerns.

## Why no frontend framework

The page set is entirely static and the only interactive element is a client-side filter.
A React toolchain would have added `node_modules`, a `basePath` config and the static-export
deep-link trap, in exchange for nothing this site uses. Stdlib templates render 3,552 pages
in under 2 seconds.

## Layout

```
crawler/
  config.py            crawl tuning, with the probe numbers behind each value
  fetch_repos.py       GraphQL client + star-range sharding
  write_snapshot.py    first_seen merge, JSONL + gzip output
  test_crawler.py      self-checks, no network
scripts/
  gate.sql             the publish gate - one definition, used by pages and sitemaps
  velocity.sql         gap-tolerant star velocity
  prepare_data.py      loads data/ into in-memory SQLite, applies the gate
  render_site.py       HTML rendering
  generate_sitemaps.py sitemap index, shards, robots.txt
  test_pipeline.py     velocity + gate self-checks
  test_render.py       escaping, deep links, sitemap/page consistency
templates/base.html
data/
  repos.jsonl          current metadata, rewritten each run
  snapshots/           <date>.jsonl.gz, written once each
```

## The 1000-result trap

GitHub's `search` connection returns at most 1000 results however far the cursor is
followed. A plain `stars:>=2000` crawl returns exactly 1000 repos and looks successful.

Queries are bounded to star ranges, and any range holding 1000 or more is bisected until
every shard fits. The crawl refuses to finish if a splittable shard came back at the cap,
and compares the sum of shard counts against the unsharded total.

## The velocity trap

`LAG(stars, 7)` assumes seven rows exist per repo. GitHub Actions cron is best-effort and
skips runs, so row position is not day offset — on a gap it compares against the wrong date
while still labelling the result "7d".

Velocity instead joins on the most recent snapshot at or before the target date. If the
nearest one is staler than the tolerance allows, no figure is published for that window
rather than a wrong one. Repos without history show null, never zero.

## Running locally

```sh
export GITHUB_TOKEN=$(gh auth token)
python3 crawler/test_crawler.py       # self-checks
python3 crawler/fetch_repos.py        # sizing probe, writes nothing
python3 crawler/write_snapshot.py     # full crawl, ~33 min
python3 scripts/test_pipeline.py
python3 scripts/test_render.py
python3 scripts/generate_sitemaps.py  # renders site/ and sitemaps
```

## Measured, 2026-08-29

| | |
|---|---|
| Repos tracked | 32,969 (floor 2,000 stars) |
| Pages published | 2,708 (gate 14,000 stars, or +5%/7d) |
| Total URLs | 3,552 |
| Crawl | 33 min, 463 requests, 4,526/5,000 rate limit left |
| Render | 1.8 s |
| Snapshot | 468 KB/day gzipped |
| Site | 36 MB |

Tracking far more repos than get pages is deliberate: the extra rows feed velocity for
repos that have not yet earned one.

## Automation

- `crawl.yml` — 04:20 UTC daily, commits `data/`
- `deploy.yml` — on push, and on a successful crawl, renders and publishes to Pages
