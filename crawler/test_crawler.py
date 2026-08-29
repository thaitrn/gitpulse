"""Self-checks for the two places this crawler can be silently wrong.

Run: python3 crawler/test_crawler.py

No framework, no network. A fake client replays a synthetic star distribution so
the sharding recursion can be checked against a known-correct answer.
"""

import gzip
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import write_snapshot
from config import MIN_STARS, SEARCH_RESULT_CAP
from fetch_repos import ShardTruncated, crawl_shards, fetch_all, normalise


class FakeClient:
    """Serves counts and nodes from a fixed {stars: repo_count} distribution."""

    def __init__(self, distribution):
        self.distribution = distribution
        self.requests_made = 0
        self.remaining = 5000
        self.capped_pages = []

    def _repos_in(self, low, high):
        return [
            (stars, index)
            for stars, count in self.distribution.items()
            if low <= stars <= high
            for index in range(count)
        ]

    def count(self, search_query):
        self.requests_made += 1
        if search_query.startswith("stars:>="):
            low = int(search_query.split(">=")[1].split()[0])
            return len(self._repos_in(low, 10**9))
        span = search_query.split("stars:")[1].split()[0]
        low, high = (int(part) for part in span.split(".."))
        return len(self._repos_in(low, high))

    def paginate(self, search_query):
        span = search_query.split("stars:")[1].split()[0]
        low, high = (int(part) for part in span.split(".."))
        found = self._repos_in(low, high)
        # Mirror the real API: never return more than the cap, even when more exist.
        if len(found) > SEARCH_RESULT_CAP:
            self.capped_pages.append((low, high, len(found)))
            found = found[:SEARCH_RESULT_CAP]
        for stars, index in found:
            yield {
                "nameWithOwner": f"owner{stars}/repo{index}",
                "description": "d",
                "stargazerCount": stars,
                "forkCount": 1,
                "primaryLanguage": {"name": "Python"},
                "licenseInfo": {"spdxId": "MIT"},
                "repositoryTopics": {"nodes": [{"topic": {"name": "cli"}}]},
                "createdAt": "2024-01-02T00:00:00Z",
                "pushedAt": "2026-08-28T00:00:00Z",
                "isArchived": False,
            }


def test_sharding_covers_everything_without_truncation():
    """Dense low-star band forces many splits; nothing may be lost or capped.

    Every individual star value stays under the cap, matching reality: no single
    exact star count on GitHub holds 1000+ repos. A range that does is only ever
    the sum of several values, which bisection can separate.
    """
    distribution = {MIN_STARS + offset: 300 for offset in range(20)}
    distribution[MIN_STARS + 900] = 30
    client = FakeClient(distribution)
    records, diagnostics = fetch_all(client, report=lambda *_: None)

    expected = sum(distribution.values())
    assert diagnostics["unique"] == expected, (diagnostics["unique"], expected)
    assert len(records) == expected
    assert not client.capped_pages, f"a shard was truncated: {client.capped_pages}"
    assert diagnostics["drift"] < 1e-9, diagnostics["drift"]
    print(f"  ok: {expected} repos across {diagnostics['shards']} shards, none capped")


def test_shard_never_yields_over_cap():
    """Every shard handed back must be under the cap, or it lost rows."""
    distribution = {MIN_STARS + offset: 400 for offset in range(12)}
    client = FakeClient(distribution)
    for low, high, count, _nodes in crawl_shards(
        client, report=lambda *_: None
    ):
        # low == high is the unsplittable case, reported as a warning by design.
        if low < high:
            assert count < SEARCH_RESULT_CAP, (low, high, count)
    print("  ok: no splittable shard exceeded the cap")


def test_unsplittable_shard_is_flagged_not_silent():
    """>1000 repos at one exact star count cannot be split; it must warn."""
    client = FakeClient({MIN_STARS + 3: SEARCH_RESULT_CAP + 500})
    warnings = []
    list(crawl_shards(client, report=warnings.append))
    assert any("WARNING" in w for w in warnings), warnings
    print("  ok: unsplittable shard surfaced a warning")


def test_truncated_shard_raises():
    """fetch_all must refuse a capped splittable shard rather than under-report."""
    client = FakeClient({MIN_STARS: 10})

    def lying_crawl(*_args, **_kwargs):
        yield MIN_STARS, MIN_STARS + 100, SEARCH_RESULT_CAP + 1, []

    original = sys.modules["fetch_repos"].crawl_shards
    sys.modules["fetch_repos"].crawl_shards = lying_crawl
    try:
        fetch_all(client, report=lambda *_: None)
    except ShardTruncated:
        print("  ok: truncated shard raised")
    else:
        raise AssertionError("truncated shard was accepted")
    finally:
        sys.modules["fetch_repos"].crawl_shards = original


def test_first_seen_survives_and_stamps_new():
    """Known repos keep their original date; only genuinely new ones get today."""
    records = {
        "a/old": {"full_name": "a/old", "stars": 5},
        "b/new": {"full_name": "b/new", "stars": 7},
    }
    previous = {"a/old": "2026-01-01"}
    merged = write_snapshot.merge_first_seen(records, previous, "2026-08-29")
    assert merged["a/old"]["first_seen"] == "2026-01-01"
    assert merged["b/new"]["first_seen"] == "2026-08-29"
    print("  ok: first_seen preserved for known, stamped for new")


def test_snapshot_rerun_is_byte_identical():
    """Same data twice must produce no git diff, so reruns stay idempotent."""
    records = {"a/b": {"full_name": "a/b", "stars": 12}}
    with tempfile.TemporaryDirectory() as tmp:
        original_dir = write_snapshot.SNAPSHOT_DIR
        write_snapshot.SNAPSHOT_DIR = pathlib.Path(tmp)
        try:
            first = write_snapshot.write_snapshot(records, "2026-08-29").read_bytes()
            second = write_snapshot.write_snapshot(records, "2026-08-29").read_bytes()
            assert first == second, "rerun produced a different file"
            rows = gzip.decompress(first).decode().strip().split("\n")
            assert json.loads(rows[0]) == {"r": "a/b", "s": 12}
        finally:
            write_snapshot.SNAPSHOT_DIR = original_dir
    print("  ok: snapshot rerun byte-identical")


def test_normalise_tolerates_null_fields():
    """Repos with no language, licence, topics or description must not crash."""
    record = normalise(
        {
            "nameWithOwner": "a/b",
            "description": None,
            "stargazerCount": 1,
            "forkCount": 0,
            "primaryLanguage": None,
            "licenseInfo": None,
            "repositoryTopics": {"nodes": []},
            "createdAt": "2024-01-02T00:00:00Z",
            "pushedAt": "2026-08-28T00:00:00Z",
            "isArchived": True,
        }
    )
    assert record["language"] is None and record["license"] is None
    assert record["topics"] == [] and record["archived"] is True
    assert record["created_at"] == "2024-01-02"
    print("  ok: null fields normalise cleanly")


if __name__ == "__main__":
    for check in [
        test_sharding_covers_everything_without_truncation,
        test_shard_never_yields_over_cap,
        test_unsplittable_shard_is_flagged_not_silent,
        test_truncated_shard_raises,
        test_first_seen_survives_and_stamps_new,
        test_snapshot_rerun_is_byte_identical,
        test_normalise_tolerates_null_fields,
    ]:
        print(check.__name__)
        check()
    print("\nall checks passed")
