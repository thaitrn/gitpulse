-- Star velocity for one window, computed against the nearest snapshot at or
-- before the target date.
--
-- Parameters: :today (latest snapshot date), :w (window in days),
--             :tolerance (max extra days a substitute snapshot may be stale)
--
-- Why not LAG(stars, :w): that assumes exactly :w rows exist per repo. GitHub
-- Actions cron is best-effort and skips runs, and a failed run leaves no file,
-- so row position does not equal day offset. On a gap, LAG silently compares
-- against the wrong date while still labelling the result "7d" — wrong numbers
-- that look right.
--
-- Instead: pick the most recent snapshot on or before (today - w days). If the
-- nearest one is staler than the tolerance allows, produce no row at all rather
-- than a mislabelled window. No row means null downstream, which the gate
-- treats as "does not qualify", never as zero growth.

INSERT INTO velocity (full_name, window_days, delta, pct)
SELECT
    current.full_name,
    :w,
    current.stars - past.past_stars,
    CASE
        WHEN past.past_stars > 0
        THEN (current.stars - past.past_stars) * 100.0 / past.past_stars
    END
FROM repos AS current
JOIN (
    SELECT snapshot.full_name, snapshot.stars AS past_stars
    FROM stars_daily AS snapshot
    JOIN (
        SELECT full_name, MAX(date) AS nearest
        FROM stars_daily
        WHERE date <= date(:today, '-' || :w || ' day')
          -- Refuse a substitute that is too old to honestly call a :w-day window.
          AND date >= date(:today, '-' || (:w + :tolerance) || ' day')
        GROUP BY full_name
    ) AS pick
      ON pick.full_name = snapshot.full_name
     AND pick.nearest = snapshot.date
) AS past
  ON past.full_name = current.full_name;
