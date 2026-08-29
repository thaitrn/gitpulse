"""Serialise a crawl into append-only storage.

Two outputs, deliberately both text:

    data/repos.jsonl              current metadata, rewritten each run
    data/snapshots/<date>.jsonl.gz  stars on that date, written once, never edited

A binary SQLite file committed daily would store a fresh full blob in git every
day and grow to multiple GB within a year, with no way to reclaim it afterwards.
Immutable per-day files stay one blob each, forever. SQLite is still used later
as an in-memory query engine, rebuilt from these files at page-generation time.

first_seen is carried forward from the previous run. It is the only stored field
that cannot be recovered from the API, so a partial fetch must never overwrite it.
"""

import datetime as dt
import gzip
import json
import os
import pathlib
import sys

from config import MIN_FETCH_RATIO
from fetch_repos import GitHubClient, fetch_all

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
REPOS_PATH = DATA_DIR / "repos.jsonl"
SNAPSHOT_DIR = DATA_DIR / "snapshots"


def load_previous():
    """Return {full_name: first_seen} from the last run, empty on first run."""
    if not REPOS_PATH.exists():
        return {}
    previous = {}
    with REPOS_PATH.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            previous[record["full_name"]] = record.get("first_seen")
    return previous


def merge_first_seen(records, previous, today):
    """Preserve first_seen for known repos, stamp today for new ones."""
    for full_name, record in records.items():
        record["first_seen"] = previous.get(full_name) or today
    return records


def write_repos(records):
    """Write sorted JSONL so git diffs stay small and reviewable."""
    REPOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPOS_PATH.open("w") as handle:
        for full_name in sorted(records):
            handle.write(json.dumps(records[full_name], sort_keys=True) + "\n")


def write_snapshot(records, today):
    """Write today's star counts. Re-running the same day overwrites, never appends."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{today}.jsonl.gz"
    # mtime=0 keeps the gzip header byte-identical across reruns of the same data,
    # so an unchanged re-run produces no git diff.
    with gzip.GzipFile(path, "wb", mtime=0) as raw:
        for full_name in sorted(records):
            row = {"r": full_name, "s": records[full_name]["stars"]}
            raw.write((json.dumps(row, sort_keys=True) + "\n").encode())
    return path


def main():
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    client = GitHubClient(os.environ.get("GITHUB_TOKEN"))

    records, diagnostics = fetch_all(client)
    print(json.dumps(diagnostics, indent=2))

    previous = load_previous()
    if previous and len(records) < len(previous) * MIN_FETCH_RATIO:
        raise SystemExit(
            f"refusing to write: fetched {len(records)} repos vs "
            f"{len(previous)} previously (below {MIN_FETCH_RATIO:.0%}). "
            "Likely a partial fetch; first_seen would be lost."
        )

    merge_first_seen(records, previous, today)
    write_repos(records)
    snapshot_path = write_snapshot(records, today)

    new_repos = sum(1 for r in records.values() if r["first_seen"] == today)
    print(
        f"wrote {len(records)} repos ({new_repos} new) "
        f"-> {REPOS_PATH.name}, {snapshot_path.name}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
