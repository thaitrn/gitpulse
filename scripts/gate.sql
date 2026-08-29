-- The publish gate: the single definition of which repos get a page.
--
-- Pages, sitemaps and the search index all read from this one query. A repo
-- that passes here and is missing from a sitemap, or a sitemap URL that does
-- not exist, both damage crawl trust — so there is exactly one source of truth.
--
-- Parameters: :page_min_stars, :min_velocity_pct, :min_abs_delta, :active_days
--
-- Two ways in:
--   1. Large and still maintained.
--   2. Smaller but genuinely accelerating. The crawl floor sits far below
--      :page_min_stars precisely so this branch has a population to draw from.
--
-- The percentage alone is gameable by small repos: 500 -> 600 stars is +20% and
-- would outrank 50,000 -> 55,000 at +10%. :min_abs_delta puts a floor under it.
--
-- Velocity is null until enough history accrues. Null fails both comparisons in
-- SQL, so during the first week the gate degrades to stars-only. That is the
-- intended behaviour, not a bug to work around.

SELECT
    r.full_name,
    r.description,
    r.language,
    r.license,
    r.topics_json,
    r.stars,
    r.forks,
    r.created_at,
    r.pushed_at,
    r.first_seen,
    v1.delta  AS star_1d,
    v1.pct    AS star_1d_pct,
    v7.delta  AS star_7d,
    v7.pct    AS star_7d_pct,
    v30.delta AS star_30d,
    v30.pct   AS star_30d_pct
FROM repos AS r
LEFT JOIN velocity AS v1  ON v1.full_name  = r.full_name AND v1.window_days  = 1
LEFT JOIN velocity AS v7  ON v7.full_name  = r.full_name AND v7.window_days  = 7
LEFT JOIN velocity AS v30 ON v30.full_name = r.full_name AND v30.window_days = 30
WHERE r.archived = 0
  AND r.description IS NOT NULL
  AND trim(r.description) <> ''
  AND r.pushed_at > date('now', '-' || :active_days || ' day')
  AND (
        r.stars >= :page_min_stars
        OR (v7.pct >= :min_velocity_pct AND v7.delta >= :min_abs_delta)
      )
ORDER BY r.stars DESC;
