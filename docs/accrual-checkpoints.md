# Accrual checkpoints

Star history cannot be backfilled — GitHub only ever reports a repository's
*current* count — so several code paths ship long before they can run on real
data. This file names when each becomes verifiable and what to check.

Without it, "verify when the data exists" is an intention that quietly never
happens, and every one of these paths renders numbers to users.

## Why the windows arrive separately

Each velocity window needs `window + 1` daily snapshots. They do not fill
together, and code that assumes they do has already caused one production defect
(the accumulating notice contradicting a live 1-day ranking).

| Snapshots | Earliest date | First becomes real |
|---|---|---|
| 2 | 2026-08-30 | 1-day velocity · `/trending/day` growth ranking · cross-window badge |
| 4 | 2026-09-01 | sparkline on repo pages (`MIN_POINTS_FOR_CHART`) |
| 8 | 2026-09-06 | 7-day velocity · publish-gate velocity branch · `with_velocity` non-zero |
| 31 | 2026-09-29 | 30-day velocity |

Dates assume the 04:20 UTC cron holds from 2026-08-30. GitHub's scheduler is
best-effort, so these are earliest dates. A missed day pushes everything after it.
Track the snapshot count, not the calendar: `ls data/snapshots/ | wc -l`.

Every render prints `with_velocity_by_window`, so the deploy log states which
windows are live without anyone having to remember to look.

## The first 1-day figure spans 11.6 hours, not 24

Velocity is keyed on snapshot **dates**, not elapsed time. The first snapshot was
written at 2026-08-29 16:45 UTC by a manual run; the second arrives at
2026-08-30 04:20 UTC from the cron. Their dates differ by one, so the delta is
labelled "1 day" while covering 11.6 hours.

Consequences for the first checkpoint, so neither is mistaken for a defect:

- 1-day deltas will read roughly half what a full day would produce. Do not
  conclude the calculation is wrong when spot-checking against GitHub — compare
  against the same 11.6-hour span, not against 24 hours.
- `MIN_ABS_DELTA = 50` is therefore applied to a half-length window. If nothing
  clears it, `/trending/day` correctly falls back to stars-per-day and says so.
  That is the gate working, not a bug.

Cron-to-cron gaps are ~24 hours, so this affects only the first pair. It is not
worth special-casing a transient, but it is worth not misreading.

## Checkpoint: 2 snapshots

The cross-window badge renders here, not at 8 — on `/trending/week`,
`other_windows` checks the day and month windows, so a repo in the daily ranking
gets an "also today" badge even while the weekly page is still on the
stars-per-day fallback.

- [ ] `/trending/day` ranks by growth and carries **no** accumulating notice
- [ ] `/trending/week` and `/month` fall back to stars-per-day **with** a notice
      stating 8 and 31 snapshots respectively, and say so in the lede
- [ ] At least one cross-window badge renders somewhere
- [ ] Spot-check three repos' 1-day deltas against GitHub's actual change
- [ ] Measure the 1-day delta distribution — `MIN_ABS_DELTA = 50` was chosen
      without data and a day is a short window; it may filter everything

## Checkpoint: 4 snapshots

- [ ] Repo pages render a sparkline instead of the stat-tile fallback
- [ ] The polyline's shape matches the numbers in the stat tiles
- [ ] No momentum value overflows its column at 375px

## Checkpoint: 8 snapshots

- [ ] 7-day figures present; `/trending/week` ranks by growth
- [ ] The publish gate's velocity branch promotes at least one sub-threshold repo
- [ ] Re-measure published count and re-tune `PAGE_MIN_STARS` if it left
      2,000–3,000 (14,000 was chosen over the closer-fitting 13,000 specifically
      to leave headroom for this)
- [ ] `/methodology` numbers still match the constants, in all three locales

## Checkpoint: 31 snapshots

- [ ] 30-day figures present; `/trending/month` ranks by growth
- [ ] Snapshot storage still reasonable (468 KB/day, ~14 MB by this point)

## Recording outcomes

Tick the box, or write down that the checkpoint was missed and why. A checkpoint
that passed silently and one that was never looked at are indistinguishable
afterwards, which defeats the purpose.
