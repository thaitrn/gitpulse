"""Self-checks for velocity and the publish gate.

Run: python3 scripts/test_pipeline.py

Velocity is the one place in this project where a bug produces numbers that look
completely reasonable while being wrong, so the gap case is checked explicitly.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import prepare_data


def seed(connection, repos, snapshots):
    """repos: [(full_name, stars, ...)]; snapshots: {date: {full_name: stars}}."""
    for full_name, stars, *rest in repos:
        description = rest[0] if rest else "a description"
        pushed = rest[1] if len(rest) > 1 else "2026-08-28"
        connection.execute(
            "INSERT INTO repos VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (full_name, description, "Python", "MIT", '["cli"]', stars, 1,
             "2024-01-01", pushed, "2026-01-01", 0),
        )
    for date, entries in snapshots.items():
        for full_name, stars in entries.items():
            connection.execute(
                "INSERT INTO stars_daily VALUES (?,?,?)", (full_name, date, stars)
            )


def velocity_of(connection, full_name, window):
    row = connection.execute(
        "SELECT delta, pct FROM velocity WHERE full_name=? AND window_days=?",
        (full_name, window),
    ).fetchone()
    return (row["delta"], row["pct"]) if row else (None, None)


def test_seven_day_velocity_is_correct():
    connection = prepare_data.connect()
    dates = [f"2026-08-{day:02d}" for day in range(22, 30)]  # 8 consecutive days
    seed(
        connection,
        [("a/b", 1100)],
        {date: {"a/b": 1000 + index * 20} for index, date in enumerate(dates)},
    )
    prepare_data.compute_velocity(connection, today="2026-08-29")
    delta, pct = velocity_of(connection, "a/b", 7)
    # current 1100 (from repos) vs 2026-08-22 snapshot of 1000
    assert delta == 100, delta
    assert abs(pct - 10.0) < 1e-9, pct
    print("  ok: 7d delta and pct correct on contiguous history")


def test_missing_snapshot_falls_back_to_nearest_prior():
    """The core correctness test: delete a day, velocity must still be sane."""
    connection = prepare_data.connect()
    snapshots = {
        "2026-08-21": {"a/b": 900},
        # 2026-08-22 deliberately absent - a skipped cron run
        "2026-08-28": {"a/b": 1080},
    }
    seed(connection, [("a/b", 1100)], snapshots)
    prepare_data.compute_velocity(connection, today="2026-08-29")
    delta, pct = velocity_of(connection, "a/b", 7)
    # Target is 2026-08-22; nearest prior is 2026-08-21, one day inside the
    # 3-day tolerance, so it is used rather than silently skipped.
    assert delta == 200, delta
    assert abs(pct - (200 / 900 * 100)) < 1e-9, pct
    print("  ok: gap falls back to nearest prior snapshot within tolerance")


def test_stale_substitute_is_refused():
    """A snapshot older than the tolerance must yield no row, not a bad window."""
    connection = prepare_data.connect()
    seed(connection, [("a/b", 1100)], {"2026-07-01": {"a/b": 500}})
    prepare_data.compute_velocity(connection, today="2026-08-29")
    delta, pct = velocity_of(connection, "a/b", 7)
    assert delta is None and pct is None, (delta, pct)
    print("  ok: over-stale snapshot produces null, not a mislabelled window")


def test_new_repo_has_null_velocity_not_zero():
    connection = prepare_data.connect()
    seed(connection, [("a/b", 1100)], {"2026-08-29": {"a/b": 1100}})
    prepare_data.compute_velocity(connection, today="2026-08-29")
    for window in prepare_data.WINDOWS:
        delta, pct = velocity_of(connection, "a/b", window)
        assert delta is None, (window, delta)
    print("  ok: repo with only today's snapshot has null velocity")


def test_zero_past_stars_does_not_divide_by_zero():
    connection = prepare_data.connect()
    seed(
        connection,
        [("a/b", 50)],
        {"2026-08-21": {"a/b": 0}, "2026-08-29": {"a/b": 50}},
    )
    prepare_data.compute_velocity(connection, today="2026-08-29")
    delta, pct = velocity_of(connection, "a/b", 7)
    assert delta == 50, delta
    assert pct is None, pct
    print("  ok: zero past stars gives null pct, no division error")


def test_gate_admits_big_and_accelerating_only():
    connection = prepare_data.connect()
    seed(
        connection,
        [
            ("big/one", prepare_data.PAGE_MIN_STARS + 1),
            ("small/quiet", 3000),
            ("small/rising", 3000),
            ("big/stale", prepare_data.PAGE_MIN_STARS + 1, "d", "2020-01-01"),
            ("big/nodesc", prepare_data.PAGE_MIN_STARS + 1, "   "),
        ],
        {
            "2026-08-21": {"small/rising": 2000, "small/quiet": 2990},
            "2026-08-29": {"small/rising": 3000, "small/quiet": 3000},
        },
    )
    prepare_data.compute_velocity(connection, today="2026-08-29")
    names = {record["full_name"] for record in prepare_data.published(connection)}
    assert "big/one" in names
    assert "small/rising" in names, "accelerating small repo should be promoted"
    assert "small/quiet" not in names, "flat small repo must not get a page"
    assert "big/stale" not in names, "inactive repo must not get a page"
    assert "big/nodesc" not in names, "blank description must not get a page"
    print("  ok: gate admits large-and-active plus genuinely accelerating only")


def test_trending_respects_absolute_floor():
    connection = prepare_data.connect()
    seed(
        connection,
        [("tiny/mover", prepare_data.PAGE_MIN_STARS + 1)],
        {
            "2026-08-21": {"tiny/mover": prepare_data.PAGE_MIN_STARS - 8},
            "2026-08-29": {"tiny/mover": prepare_data.PAGE_MIN_STARS + 1},
        },
    )
    prepare_data.compute_velocity(connection, today="2026-08-29")
    records = prepare_data.published(connection)
    ranked = prepare_data.trending(records, 7)
    assert ranked == [], "a 9-star move must not reach a trending page"
    print("  ok: trending floors out trivial absolute movement")


def test_facet_pages_skip_thin_topics():
    connection = prepare_data.connect()
    seed(
        connection,
        [(f"o/r{index}", prepare_data.PAGE_MIN_STARS + 1) for index in range(3)],
        {},
    )
    records = prepare_data.published(connection)
    # Every seeded repo carries the same single topic, 3 < MIN_MEMBERS.
    assert prepare_data.facet_counts(records, "topics") == {}
    print("  ok: topics below the member floor get no page")


if __name__ == "__main__":
    for check in [
        test_seven_day_velocity_is_correct,
        test_missing_snapshot_falls_back_to_nearest_prior,
        test_stale_substitute_is_refused,
        test_new_repo_has_null_velocity_not_zero,
        test_zero_past_stars_does_not_divide_by_zero,
        test_gate_admits_big_and_accelerating_only,
        test_trending_respects_absolute_floor,
        test_facet_pages_skip_thin_topics,
    ]:
        print(check.__name__)
        check()
    print("\nall checks passed")
