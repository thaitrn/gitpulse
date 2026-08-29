"""Load the crawled files into SQLite, apply the gate, emit the published set.

SQLite is used here as a query engine, not as storage: it is built in memory
from data/ on every run and thrown away. Storage stays append-only text so git
keeps one immutable blob per day instead of a fresh copy of a growing binary.

Output is a plain Python structure consumed by render_site.py. Nothing
downstream knows about SQLite, gzip, or the snapshot format.
"""

import datetime as dt
import gzip
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"

# Publish gate. Measured against the 2026-08-29 crawl of 32,969 repos:
#
#   12,000 -> 3,227 published    14,000 -> 2,708
#   13,000 -> 2,941              15,000 -> 2,458
#
# 14,000 rather than the 13,000 that fits the 2-3k target exactly: the velocity
# branch below is still dormant (one snapshot, no history) and will promote
# additional sub-threshold repos once a week of data exists. The headroom is for
# them. The crawl floor (crawler/config.py, 2,000) sits far below this precisely
# so that branch has a population to draw from.
PAGE_MIN_STARS = 14_000
MIN_VELOCITY_PCT = 5.0
MIN_ABS_DELTA = 50
ACTIVE_DAYS = 180

# Velocity windows, and how stale a substitute snapshot may be before the window
# stops being honest. 3 days absorbs the occasional skipped cron run without
# letting a "7d" figure silently span three weeks.
WINDOWS = (1, 7, 30)
STALENESS_TOLERANCE = 3

# Only the newest snapshots matter for the widest window; loading every file
# ever written would grow unboundedly for no gain.
SNAPSHOT_LOAD_DAYS = max(WINDOWS) + STALENESS_TOLERANCE + 2

# A topic or language page listing a handful of repos is thin content that drags
# on site-wide quality signals. The same threshold decides which topics are real
# enough to show as pills on a card, so a pill always links to a page that exists
# and has peers.
MIN_MEMBERS_FOR_FACET_PAGE = 5

# Cards show at most this many topics. Measured 2026-08-29: repos carry a median
# of 7 raw topics (mean 8.5, max 20), of which 4 clear the threshold above.
# Rendering all of them fills each row with near-duplicate keywords.
MAX_CARD_TOPICS = 2

# Frequent enough to clear the threshold, but they describe a repo's meta status
# rather than its subject. Chosen from the real corpus, not guessed: hacktoberfest
# is the second most common topic overall (270 of 2,708 published repos), and
# awesome/awesome-list/open-source all sit inside the top 40.
TOPIC_STOPLIST = frozenset({
    "hacktoberfest", "awesome", "awesome-list", "awesome-lists", "list", "lists",
    "open-source", "opensource", "oss", "free", "github", "software",
})

# Topics that merely restate the repo's primary language, which the card already
# shows as its own chip. "Python · python" is duplication, not information.
LANGUAGE_TOPIC_ALIASES = {
    "go": {"golang"},
    "c#": {"csharp", "dotnet"},
    "c++": {"cpp", "cplusplus"},
    "javascript": {"js"},
    "typescript": {"ts"},
    "shell": {"bash", "sh"},
    "jupyter notebook": {"jupyter", "notebook"},
}

SCHEMA = """
CREATE TABLE repos (
    full_name   TEXT PRIMARY KEY,
    description TEXT,
    language    TEXT,
    license     TEXT,
    topics_json TEXT NOT NULL,
    stars       INTEGER NOT NULL,
    forks       INTEGER NOT NULL,
    created_at  TEXT,
    pushed_at   TEXT,
    first_seen  TEXT,
    archived    INTEGER NOT NULL
);
CREATE TABLE stars_daily (
    full_name TEXT NOT NULL,
    date      TEXT NOT NULL,
    stars     INTEGER NOT NULL,
    PRIMARY KEY (full_name, date)
);
CREATE TABLE velocity (
    full_name   TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    delta       INTEGER,
    pct         REAL,
    PRIMARY KEY (full_name, window_days)
);
CREATE INDEX idx_snapshot_date ON stars_daily(date);
"""


def connect():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def load_repos(connection, path=None):
    path = path or DATA_DIR / "repos.jsonl"
    rows = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            rows.append(
                (
                    record["full_name"],
                    record.get("description"),
                    record.get("language"),
                    record.get("license"),
                    json.dumps(record.get("topics") or []),
                    record["stars"],
                    record["forks"],
                    record.get("created_at"),
                    record.get("pushed_at"),
                    record.get("first_seen"),
                    int(bool(record.get("archived"))),
                )
            )
    connection.executemany(
        "INSERT INTO repos VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    return len(rows)


def snapshot_files(snapshot_dir=None, limit=SNAPSHOT_LOAD_DAYS):
    snapshot_dir = snapshot_dir or DATA_DIR / "snapshots"
    files = sorted(snapshot_dir.glob("*.jsonl.gz"))
    return files[-limit:]


def load_snapshots(connection, files):
    for path in files:
        date = path.name.removesuffix(".jsonl.gz")
        rows = []
        with gzip.open(path, "rt") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                rows.append((row["r"], date, row["s"]))
        connection.executemany(
            "INSERT OR REPLACE INTO stars_daily VALUES (?,?,?)", rows
        )
    return len(files)


def latest_snapshot_date(connection):
    row = connection.execute("SELECT MAX(date) AS d FROM stars_daily").fetchone()
    return row["d"]


def compute_velocity(connection, today=None):
    """Fill the velocity table for every window. No-op when there is no history."""
    today = today or latest_snapshot_date(connection)
    if today is None:
        return
    statement = (SCRIPTS_DIR / "velocity.sql").read_text()
    for window in WINDOWS:
        connection.execute(
            statement,
            {"today": today, "w": window, "tolerance": STALENESS_TOLERANCE},
        )


def published(connection):
    """Rows passing the gate, with topics decoded."""
    statement = (SCRIPTS_DIR / "gate.sql").read_text()
    rows = connection.execute(
        statement,
        {
            "page_min_stars": PAGE_MIN_STARS,
            "min_velocity_pct": MIN_VELOCITY_PCT,
            "min_abs_delta": MIN_ABS_DELTA,
            "active_days": ACTIVE_DAYS,
        },
    ).fetchall()
    records = []
    for row in rows:
        record = dict(row)
        record["topics"] = json.loads(record.pop("topics_json"))
        records.append(record)
    return records


def star_history(connection, full_names, days=30):
    """{full_name: [(date, stars), ...]} for the sparkline, newest last."""
    history = {name: [] for name in full_names}
    cutoff = dt.date.today() - dt.timedelta(days=days)
    for row in connection.execute(
        "SELECT full_name, date, stars FROM stars_daily "
        "WHERE date >= ? ORDER BY date",
        (cutoff.isoformat(),),
    ):
        if row["full_name"] in history:
            history[row["full_name"]].append((row["date"], row["stars"]))
    return history


def card_topics(record, whitelist):
    """The few topics worth showing on a card, most specific first.

    Ranked by ascending corpus frequency: a rarer qualifying topic distinguishes
    this repo, while a very common one mostly restates the category. Ties break
    alphabetically so output is byte-stable across runs.
    """
    language = (record.get("language") or "").lower()
    owner, name = record["full_name"].lower().split("/", 1)
    # Repos commonly tag themselves with their own name; the card already shows it.
    redundant = ({language} | LANGUAGE_TOPIC_ALIASES.get(language, set())
                 | {owner, name})
    eligible = [
        topic
        for topic in record["topics"]
        if topic in whitelist
        and topic.lower() not in TOPIC_STOPLIST
        and topic.lower() not in redundant
    ]
    eligible.sort(key=lambda topic: (whitelist[topic], topic))
    return eligible[:MAX_CARD_TOPICS]


def facet_counts(records, key):
    """Count published repos per topic or language, above the thin-content floor."""
    counts = {}
    for record in records:
        values = record["topics"] if key == "topics" else [record.get("language")]
        for value in values:
            if value:
                counts[value] = counts.get(value, 0) + 1
    return {
        value: count
        for value, count in sorted(counts.items(), key=lambda kv: -kv[1])
        if count >= MIN_MEMBERS_FOR_FACET_PAGE
    }


def trending(records, window):
    """Published repos ranked by percentage growth, floored by absolute delta."""
    key_pct, key_delta = f"star_{window}d_pct", f"star_{window}d"
    ranked = [
        record
        for record in records
        if record.get(key_pct) is not None
        and record.get(key_delta) is not None
        and record[key_delta] >= MIN_ABS_DELTA
    ]
    ranked.sort(key=lambda record: record[key_pct], reverse=True)
    return ranked


def build():
    """Return everything render_site.py needs, plus diagnostics."""
    connection = connect()
    total_repos = load_repos(connection)
    files = snapshot_files()
    load_snapshots(connection, files)
    compute_velocity(connection)

    records = published(connection)
    history = star_history(connection, [r["full_name"] for r in records])

    return {
        "records": records,
        "history": history,
        "topics": facet_counts(records, "topics"),
        "languages": facet_counts(records, "language"),
        "trending": {window: trending(records, window) for window in WINDOWS},
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "diagnostics": {
            "total_repos": total_repos,
            "snapshots_loaded": len(files),
            "published": len(records),
            "with_velocity": sum(
                1 for r in records if r.get("star_7d_pct") is not None
            ),
            # Per window, because the windows fill at different times: 1-day needs
            # two snapshots, 7-day needs eight. A single counter cannot describe
            # what any given window's page is showing once they diverge.
            "with_velocity_by_window": {
                window: sum(
                    1 for r in records if r.get(f"star_{window}d_pct") is not None
                )
                for window in WINDOWS
            },
        },
    }


if __name__ == "__main__":
    print(json.dumps(build()["diagnostics"], indent=2))
