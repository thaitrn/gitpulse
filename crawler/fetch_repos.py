"""GitHub GraphQL client with star-range sharding.

The search connection returns at most SEARCH_RESULT_CAP (1000) results no matter
how far the cursor is followed. A naive `stars:>=2000` crawl therefore returns
1000 repos and looks like it succeeded. Every query here is bounded to a star
range small enough to stay under the cap, and any range that would be truncated
is bisected until it fits.

Stdlib only: no third-party HTTP client, so the workflow needs no install step.
"""

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request

from config import (
    MAX_RETRIES,
    MAX_STARS,
    MIN_RATE_LIMIT_REMAINING,
    MIN_STARS,
    PAGE_SIZE,
    RETRY_BASE_DELAY,
    SEARCH_RESULT_CAP,
)

API_URL = "https://api.github.com/graphql"

COUNT_QUERY = """
query($q: String!) {
  rateLimit { cost remaining }
  search(query: $q, type: REPOSITORY) { repositoryCount }
}
"""

PAGE_QUERY = """
query($q: String!, $first: Int!, $after: String) {
  rateLimit { cost remaining }
  search(query: $q, type: REPOSITORY, first: $first, after: $after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        nameWithOwner
        description
        stargazerCount
        forkCount
        primaryLanguage { name }
        licenseInfo { spdxId }
        repositoryTopics(first: 20) { nodes { topic { name } } }
        createdAt
        pushedAt
        isArchived
      }
    }
  }
}
"""


class RateLimitExhausted(RuntimeError):
    """Raised when the hourly budget drops too low to finish safely."""


class ShardTruncated(RuntimeError):
    """Raised when a fetched shard was capped, meaning silent data loss."""


class GitHubClient:
    def __init__(self, token):
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        self._token = token
        self.requests_made = 0
        self.remaining = None

    def _post(self, query, variables):
        payload = json.dumps({"query": query, "variables": variables}).encode()
        request = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Authorization": f"bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "gitpulse-crawler",
            },
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())

    def query(self, query, variables):
        """POST with retry on transient failures and secondary rate limits."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                body = self._post(query, variables)
            except urllib.error.HTTPError as error:
                # 401/403 on a bad token is permanent; retrying just hides it.
                if error.code in (401, 404):
                    raise
                last_error = error
            except (
                urllib.error.URLError,
                TimeoutError,
                http.client.HTTPException,
            ) as error:
                # Covers dropped/truncated connections (e.g. IncompleteRead),
                # which are as transient as a URLError and should retry the same way.
                last_error = error
            else:
                errors = body.get("errors") or []
                transient = [e for e in errors if e.get("type") == "RATE_LIMITED"]
                if errors and not transient:
                    raise RuntimeError(f"GraphQL error: {errors}")
                if not errors:
                    self.requests_made += 1
                    limit = (body.get("data") or {}).get("rateLimit") or {}
                    if limit.get("remaining") is not None:
                        self.remaining = limit["remaining"]
                        if self.remaining < MIN_RATE_LIMIT_REMAINING:
                            raise RateLimitExhausted(
                                f"rate limit remaining={self.remaining}, aborting"
                            )
                    return body["data"]
                last_error = RuntimeError(f"rate limited: {errors}")

            time.sleep(RETRY_BASE_DELAY * (2**attempt))

        raise RuntimeError(f"giving up after {MAX_RETRIES} attempts: {last_error}")

    def count(self, search_query):
        data = self.query(COUNT_QUERY, {"q": search_query})
        return data["search"]["repositoryCount"]

    def paginate(self, search_query):
        """Yield every node of a query already known to fit under the cap."""
        cursor = None
        while True:
            data = self.query(
                PAGE_QUERY,
                {"q": search_query, "first": PAGE_SIZE, "after": cursor},
            )
            search = data["search"]
            for node in search["nodes"]:
                if node:  # non-Repository results come back as empty objects
                    yield node
            page = search["pageInfo"]
            if not page["hasNextPage"]:
                return
            cursor = page["endCursor"]


def star_range_query(low, high):
    return f"stars:{low}..{high} sort:stars"


def crawl_shards(client, low=MIN_STARS, high=MAX_STARS, report=print):
    """Recursively bisect [low, high] until each shard fits under the cap.

    Yields (shard_low, shard_high, count, nodes). The caller is responsible for
    deduplication; adjacent shards are disjoint by construction, but a repo can
    cross a boundary mid-run.
    """
    search_query = star_range_query(low, high)
    count = client.count(search_query)

    if count == 0:
        return

    if count >= SEARCH_RESULT_CAP:
        if low >= high:
            # More than 1000 repos share one exact star count. Nothing to split;
            # the tail is unreachable through search. Surface it rather than
            # pretending the shard was complete.
            report(f"  WARNING: {count} repos at exactly {low} stars, capped")
            nodes = list(client.paginate(search_query))
            yield low, high, count, nodes
            return
        middle = (low + high) // 2
        yield from crawl_shards(client, low, middle, report)
        yield from crawl_shards(client, middle + 1, high, report)
        return

    nodes = list(client.paginate(search_query))
    report(f"  {low}..{high}: {count} repos, {len(nodes)} fetched")
    yield low, high, count, nodes


def normalise(node):
    """Flatten a GraphQL node into the stored record shape."""
    language = node.get("primaryLanguage") or {}
    licence = node.get("licenseInfo") or {}
    topics = node.get("repositoryTopics", {}).get("nodes") or []
    return {
        "full_name": node["nameWithOwner"],
        "description": node.get("description"),
        "language": language.get("name"),
        "license": licence.get("spdxId"),
        "topics": [t["topic"]["name"] for t in topics if t and t.get("topic")],
        "stars": node["stargazerCount"],
        "forks": node["forkCount"],
        "created_at": (node.get("createdAt") or "")[:10] or None,
        "pushed_at": (node.get("pushedAt") or "")[:10] or None,
        "archived": bool(node.get("isArchived")),
    }


def fetch_all(client, report=print):
    """Fetch every repo at or above MIN_STARS.

    Returns (records_by_full_name, diagnostics). Raises ShardTruncated if the
    sharding self-check fails, because a truncated crawl corrupts the dataset in
    a way that is invisible downstream.
    """
    total_expected = client.count(f"stars:>={MIN_STARS}")
    report(f"expecting ~{total_expected} repos at stars>={MIN_STARS}")

    records = {}
    shard_sum = 0
    shards = 0
    for low, high, count, nodes in crawl_shards(client, report=report):
        shard_sum += count
        shards += 1
        if count >= SEARCH_RESULT_CAP and low < high:
            raise ShardTruncated(f"shard {low}..{high} returned {count}")
        for node in nodes:
            record = normalise(node)
            records[record["full_name"]] = record

    drift = abs(shard_sum - total_expected) / max(total_expected, 1)
    diagnostics = {
        "total_expected": total_expected,
        "shard_sum": shard_sum,
        "shards": shards,
        "unique": len(records),
        "drift": drift,
        "requests": client.requests_made,
        "rate_limit_remaining": client.remaining,
    }
    return records, diagnostics


def main():
    """Standalone sizing probe: print counts without writing anything."""
    client = GitHubClient(os.environ.get("GITHUB_TOKEN"))
    for threshold in (500, 1000, 2000, 5000, 10000, 12000):
        print(f"stars:>={threshold}\t{client.count(f'stars:>={threshold}')}")
    print(f"rate limit remaining: {client.remaining}", file=sys.stderr)


if __name__ == "__main__":
    main()
