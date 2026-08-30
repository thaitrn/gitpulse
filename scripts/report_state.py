"""Report which accrual checkpoints the dataset has reached.

Runs on every deploy. The checkpoints in docs/accrual-checkpoints.md become
verifiable at different snapshot counts, weeks apart, and "remember to look when
the data arrives" is an intention that quietly never happens. This makes the
state something the deploy log states rather than something to recall.

Exits non-zero only on a contradiction — a window holding figures while its page
would still claim to be waiting — because that is the defect class this project
keeps producing.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import prepare_data
import render_site

# Snapshot counts at which a previously-unverifiable path first runs for real.
CHECKPOINTS = {
    2: "1-day velocity · /trending/day growth ranking · cross-window badge",
    4: "sparkline on repo pages",
    8: "7-day velocity · publish-gate velocity branch",
    31: "30-day velocity",
}


def main():
    data = prepare_data.build()
    diagnostics = data["diagnostics"]
    snapshots = diagnostics["snapshots_loaded"]
    by_window = diagnostics["with_velocity_by_window"]

    print(f"snapshots: {snapshots}")
    print(f"published: {diagnostics['published']:,} of {diagnostics['total_repos']:,} tracked")
    print()

    print("windows:")
    for window, name in render_site.WINDOWS.items():
        order, rows = render_site.ranking_source(data, window)
        count = by_window.get(window) or 0
        needed = render_site.snapshots_needed(window)
        state = render_site.window_state(data, window)
        print(f"  {name:<6} figures={count:<6} state={state:<12} "
              f"ordering={order:<7} (needs {needed} snapshots)")
    print()

    print("checkpoints:")
    for needed, what in sorted(CHECKPOINTS.items()):
        mark = "reached" if snapshots >= needed else f"at {needed} snapshots"
        print(f"  [{'x' if snapshots >= needed else ' '}] {mark:<18} {what}")
    print()

    # The recurring defect in this codebase is a page describing something the
    # code did not do. Assert the one invariant that would catch the next one.
    failures = []
    for window, name in render_site.WINDOWS.items():
        order, _rows = render_site.ranking_source(data, window)
        state = render_site.window_state(data, window)
        if order == "growth" and state != "ranked":
            failures.append(f"/trending/{name}: ranks by growth but state is {state}")
        if state == "ranked" and order != "growth":
            failures.append(f"/trending/{name}: has figures but orders by {order}")

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        return 1

    print("no window contradicts its own page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
