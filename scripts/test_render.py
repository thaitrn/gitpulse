"""Self-checks for rendering and sitemaps, against a synthetic dataset.

Run: python3 scripts/test_render.py

Covers the failure modes that are invisible locally but fatal in production: a
sitemap URL with no file behind it, a deep link that only works under client-side
navigation, and crawled text escaping into markup.
"""

import gzip
import json
import pathlib
import re
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import generate_sitemaps
import prepare_data
import render_site
from i18n import LOCALES, LOCALE_TAGS

# Repos chosen to exercise the awkward cases: a dot in the name, a quote and a
# script tag in a description, unicode, and a repo below the star gate that is
# only published because it is accelerating.
SYNTHETIC = [
    ("big/one", 50_000, "A large well-known project"),
    ("dotted/some.thing.js", 30_000, 'Has "quotes" and <script>alert(1)</script>'),
    ("uni/proje-kt", 20_000, "Unicode topic: café, naïve"),
    ("rising/small", 3_000, "Small but accelerating"),
    ("quiet/small", 3_000, "Small and flat"),
]


def write_dataset(directory):
    snapshots = directory / "snapshots"
    snapshots.mkdir(parents=True)

    repos = []
    for full_name, stars, description in SYNTHETIC:
        repos.append(
            {
                "full_name": full_name,
                "description": description,
                "language": "Python",
                "license": "MIT",
                "topics": ["cli", "café"],
                "stars": stars,
                "forks": 10,
                "created_at": "2024-01-01",
                "pushed_at": "2026-08-28",
                "first_seen": "2026-01-01",
                "archived": False,
            }
        )
    (directory / "repos.jsonl").write_text(
        "\n".join(json.dumps(record) for record in repos) + "\n"
    )

    # Eight consecutive days so 7-day velocity is real. "rising/small" grows
    # enough to be promoted by the velocity branch; "quiet/small" does not.
    for index, day in enumerate(range(22, 30)):
        date = f"2026-08-{day:02d}"
        with gzip.open(snapshots / f"{date}.jsonl.gz", "wt") as handle:
            for full_name, stars, _description in SYNTHETIC:
                if full_name == "rising/small":
                    value = 2_000 + index * 125
                elif full_name == "quiet/small":
                    value = 2_995 + index
                else:
                    value = stars - (7 - index) * 100
                handle.write(json.dumps({"r": full_name, "s": value}) + "\n")


def build_into(tmp):
    data_dir = pathlib.Path(tmp) / "data"
    site_dir = pathlib.Path(tmp) / "site"
    write_dataset(data_dir)

    prepare_data.DATA_DIR = data_dir
    render_site.SITE_DIR = site_dir
    generate_sitemaps.SITE_DIR = site_dir

    data = render_site.build()
    generate_sitemaps.generate(data)
    return data, site_dir


def sitemap_paths(site_dir):
    """Every <loc> across the index's children, as site-relative paths."""
    paths = []
    for shard in (site_dir / "sitemaps").glob("*.xml"):
        for match in re.findall(r"<loc>([^<]+)</loc>", shard.read_text()):
            paths.append(match.replace(render_site.ORIGIN + render_site.BASE, ""))
    return paths


def test_every_sitemap_url_has_a_file():
    """The one that matters: a listed URL with no file behind it is a 404."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        missing = [
            path
            for path in sitemap_paths(site_dir)
            if not (site_dir / path.strip("/") / "index.html").exists()
            and path.strip("/") != ""
        ]
        assert not missing, f"sitemap lists URLs with no page: {missing[:5]}"
        print(f"  ok: all {len(sitemap_paths(site_dir))} sitemap urls resolve to a file")


def test_deep_link_is_a_real_index_html():
    """Static hosts serve <path>/index.html; a bare file would 404 on deep link."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for locale in LOCALES:
            base = site_dir if locale == LOCALES[0] else site_dir / locale
            target = base / "repo" / "dotted" / "some.thing.js" / "index.html"
            assert target.exists(), f"{locale}: dotted repo name did not produce a page"
        print("  ok: dotted repo name resolves to index.html in every locale")


def test_titles_are_unique_within_each_locale():
    """Titles repeat across translations by design, but never inside one locale."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for locale in LOCALES:
            base = site_dir if locale == LOCALES[0] else site_dir / locale
            paths = [
                path for path in base.rglob("index.html")
                if locale != LOCALES[0]
                or not any(part in LOCALES[1:] for part in path.parts)
            ]
            titles = [
                re.search(r"<title>(.*?)</title>", path.read_text(), re.S).group(1)
                for path in paths
            ]
            duplicates = {title for title in titles if titles.count(title) > 1}
            assert not duplicates, f"{locale}: duplicate titles {duplicates}"
        print("  ok: titles unique within each locale")


def test_hreflang_covers_every_locale_and_x_default():
    """Without these, the translations read as duplicate content."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        markup = (site_dir / "index.html").read_text()
        for locale in LOCALES:
            tag = LOCALE_TAGS[locale]
            assert f'hreflang="{tag}"' in markup, f"missing hreflang for {tag}"
        assert 'hreflang="x-default"' in markup
        print("  ok: hreflang alternates present for all locales plus x-default")


def test_lang_attribute_matches_locale():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for locale in LOCALES:
            base = site_dir if locale == LOCALES[0] else site_dir / locale
            markup = (base / "index.html").read_text()
            assert f'<html lang="{LOCALE_TAGS[locale]}"' in markup, locale
        print("  ok: html lang attribute matches each locale")


def test_translated_chrome_actually_differs():
    """Guards against a locale silently falling back to English everywhere."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        english = (site_dir / "index.html").read_text()
        for locale in LOCALES[1:]:
            markup = (site_dir / locale / "index.html").read_text()
            english_h1 = re.search(r"<h1>(.*?)</h1>", english, re.S).group(1)
            other_h1 = re.search(r"<h1>(.*?)</h1>", markup, re.S).group(1)
            assert other_h1 != english_h1, f"{locale} h1 was not translated"
        print("  ok: each locale renders translated chrome")


def test_page_never_claims_growth_ranking_it_did_not_do():
    """A window with no qualifying movers must say so, not mislabel star order.

    Regression: the fallback used to be an `or` inside the render call, so the
    lede kept claiming "ranked by star growth" while showing a star-ordered
    list. Fails without the ranking_source split.
    """
    with tempfile.TemporaryDirectory() as tmp:
        data, site_dir = build_into(tmp)

        # Force the 1-day window empty while 7-day history still exists, which
        # is exactly the state the global "accumulating" notice cannot describe.
        data["trending"][1] = []
        data["diagnostics"]["with_velocity"] = len(data["records"])
        render_site.SITE_DIR = site_dir
        render_site.render_trending(render_site.LOCALES[0], data)

        markup = (site_dir / "trending" / "day" / "index.html").read_text()
        growth_claim = render_site.t("en", "lede_day")
        assert growth_claim not in markup, "page claimed growth ranking it did not do"
        assert render_site.t("en", "lede_stars") in markup, "star ordering not stated"
        assert render_site.t("en", "fallback_title") in markup, "no explanation shown"
        print("  ok: empty window states star ordering and explains why")


def test_ranking_source_reports_what_it_returns():
    with tempfile.TemporaryDirectory() as tmp:
        data, _site_dir = build_into(tmp)
        order, rows = render_site.ranking_source(data, 7)
        assert order == "growth" and rows, order
        data["trending"][7] = []
        order, rows = render_site.ranking_source(data, 7)
        assert order == "stars" and rows, order
        print("  ok: ranking_source labels growth vs stars correctly")


def test_no_broken_plural_in_any_locale():
    """Regression: the lede rendered "over 1 days"."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for locale in LOCALES:
            base = site_dir if locale == LOCALES[0] else site_dir / locale
            markup = (base / "trending" / "day" / "index.html").read_text()
            assert "1 days" not in markup, f"{locale}: broken plural"
        print("  ok: no broken plural in any locale")


def test_avatar_tile_is_deterministic_and_decorative():
    first = render_site.avatar_tile("codecrafters-io")
    assert first == render_site.avatar_tile("codecrafters-io"), "colour not stable"
    assert 'aria-hidden="true"' in first, "decorative tile exposed to screen readers"
    assert ">C</div>" in first, first
    assert render_site.avatar_tile("other-owner") != first, "all owners same colour"
    print("  ok: avatar tile stable per owner, decorative, distinct across owners")


def test_avatar_tile_cannot_inject_css():
    """Only a derived integer reaches the style attribute."""
    hostile = 'x";background:url(javascript:alert(1));"'
    markup = render_site.avatar_tile(hostile)
    assert "javascript:" not in markup, markup
    assert "url(" not in markup, markup
    assert re.search(r"background:hsl\(\d{1,3} 45% var\(--tile-l\)\)", markup), markup
    print("  ok: hostile owner name cannot reach the style attribute")


def test_cross_window_badge_excludes_current_window():
    with tempfile.TemporaryDirectory() as tmp:
        data, _site_dir = build_into(tmp)
        record = data["trending"][7][0]
        names = render_site.other_windows(record, data, 7)
        assert "week" not in names, "badge named the window being viewed"
        assert names, "expected the top weekly repo to rank in another window too"
        print(f"  ok: cross-window badge lists {names}, never the current window")


def test_cross_window_badge_renders_translated():
    with tempfile.TemporaryDirectory() as tmp:
        data, site_dir = build_into(tmp)
        for locale in LOCALES:
            base = site_dir if locale == LOCALES[0] else site_dir / locale
            markup = (base / "trending" / "week" / "index.html").read_text()
            assert 'class="badge-window"' in markup, f"{locale}: no badge rendered"
            assert render_site.esc(render_site.t(locale, "also_day")) in markup, locale
        print("  ok: cross-window badge present and translated in every locale")


def test_truncated_list_states_shown_of_total():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        rows = [{"full_name": f"o/r{i}"} for i in range(500)]
        shown, total = render_site.limited(rows, render_site.FACET_CAP)
        assert len(shown) == render_site.FACET_CAP and total == 500
        note = render_site.showing_note("en", len(shown), total)
        assert "200" in note and "500" in note, note
        print("  ok: truncated list reports shown-of-total")


def test_complete_list_says_nothing():
    """"Showing 12 of 12" is noise, not honesty."""
    assert render_site.showing_note("en", 12, 12) == ""
    assert render_site.showing_note("en", 13, 12) == ""
    print("  ok: complete list renders no truncation note")


def test_truncation_note_present_in_every_locale():
    for locale in LOCALES:
        note = render_site.showing_note(locale, 200, 500)
        assert note and "200" in note and "500" in note, (locale, note)
        assert "1 days" not in note
    print("  ok: truncation note translated in every locale")


def test_ranking_source_returns_full_pool_not_a_slice():
    """The cap belongs to the renderer that discloses it, not to the ranking."""
    with tempfile.TemporaryDirectory() as tmp:
        data, _site_dir = build_into(tmp)
        _order, pool = render_site.ranking_source(data, 7)
        assert len(pool) == len(data["trending"][7]) or len(pool) == len(data["records"])
        print("  ok: ranking_source hands back the whole pool")


def test_card_topics_are_curated_not_raw():
    """Cards must not dump every GitHub topic, and never a stoplisted one."""
    whitelist = {"alpha": 40, "beta": 9, "gamma": 7, "hacktoberfest": 300,
                 "python": 200, "mine": 12}
    record = {
        "full_name": "someone/mine",
        "language": "Python",
        "topics": ["hacktoberfest", "python", "mine", "alpha", "beta", "gamma"],
    }
    picked = prepare_data.card_topics(record, whitelist)
    assert len(picked) <= prepare_data.MAX_CARD_TOPICS, picked
    assert "hacktoberfest" not in picked, "stoplisted topic rendered"
    assert "python" not in picked, "topic duplicating the language chip rendered"
    assert "mine" not in picked, "topic repeating the repo name rendered"
    # Rarest-first: gamma(7) then beta(9), not alpha(40).
    assert picked == ["gamma", "beta"], picked
    print("  ok: cards show rarest qualifying topics, stoplist and dupes removed")


def test_card_with_no_topics_emits_no_tag_row():
    """An empty .tags element keeps its margin, leaving a phantom gap."""
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for path in site_dir.rglob("index.html"):
            assert '<div class="tags"></div>' not in path.read_text(), path
        print("  ok: no empty tag rows rendered")


def test_card_topic_ordering_is_deterministic():
    """Equal frequencies must break alphabetically so git diffs stay stable."""
    whitelist = {"zeta": 10, "alpha": 10, "mid": 10}
    record = {"full_name": "o/r", "language": None,
              "topics": ["zeta", "mid", "alpha"]}
    assert prepare_data.card_topics(record, whitelist) == ["alpha", "mid"]
    print("  ok: topic ordering deterministic on frequency ties")


def test_every_card_pill_links_to_a_page_that_exists():
    """A pill pointing at an ungenerated topic page is a 404 in a hot path."""
    with tempfile.TemporaryDirectory() as tmp:
        data, site_dir = build_into(tmp)
        generated = {
            path.parent.name
            for path in (site_dir / "topics").glob("*/index.html")
        }
        for record in data["records"]:
            for topic in prepare_data.card_topics(record, data["topics"]):
                assert render_site.slug(topic) in generated, (
                    f"{record['full_name']} pill '{topic}' has no topic page"
                )
        print("  ok: every card pill resolves to a generated topic page")


def test_repo_detail_still_shows_all_topics():
    """Curation applies to cards only; the detail page stays complete."""
    with tempfile.TemporaryDirectory() as tmp:
        data, site_dir = build_into(tmp)
        record = next(r for r in data["records"] if r["topics"])
        owner, name = record["full_name"].split("/", 1)
        markup = (site_dir / "repo" / owner / name / "index.html").read_text()
        for topic in record["topics"]:
            assert render_site.esc(topic) in markup, f"detail page dropped {topic}"
        print("  ok: repo detail page still lists every topic")


def test_crawled_text_is_escaped():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        markup = (
            site_dir / "repo" / "dotted" / "some.thing.js" / "index.html"
        ).read_text()
        assert "<script>alert(1)</script>" not in markup, "description was not escaped"
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in markup
        print("  ok: script tag in a description renders as literal text")


def test_json_ld_is_valid_json_and_cannot_break_out():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        markup = (
            site_dir / "repo" / "dotted" / "some.thing.js" / "index.html"
        ).read_text()
        block = re.search(
            r'<script type="application/ld\+json">(.*?)</script>', markup, re.S
        )
        assert block, "no JSON-LD emitted"
        payload = json.loads(block.group(1).replace("<\\/", "</"))
        assert payload["@type"] == "SoftwareSourceCode"
        assert "aggregateRating" not in payload, "no invented ratings allowed"
        print("  ok: JSON-LD parses and contains only crawled facts")


def test_velocity_branch_promotes_only_the_riser():
    with tempfile.TemporaryDirectory() as tmp:
        data, _site_dir = build_into(tmp)
        names = {record["full_name"] for record in data["records"]}
        assert "rising/small" in names, "accelerating sub-threshold repo not promoted"
        assert "quiet/small" not in names, "flat sub-threshold repo was published"
        print("  ok: velocity branch promotes the riser, not the flat repo")


def test_canonical_matches_actual_path():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        for path in site_dir.rglob("index.html"):
            relative = path.parent.relative_to(site_dir).as_posix()
            expected = f"{render_site.ORIGIN}{render_site.BASE}/" + (
                "" if relative == "." else relative + "/"
            )
            canonical = re.search(
                r'<link rel="canonical" href="([^"]+)"', path.read_text()
            ).group(1)
            assert canonical == expected, f"{relative}: {canonical} != {expected}"
        print("  ok: every canonical matches its deployed path")


def test_robots_lists_sitemap_and_throttles_bots():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        robots = (site_dir / "robots.txt").read_text()
        assert "Sitemap: " in robots and "sitemap.xml" in robots
        assert robots.count("Crawl-delay: 10") == len(generate_sitemaps.THROTTLED_BOTS)
        print("  ok: robots.txt throttles named bots and points at the sitemap")


if __name__ == "__main__":
    for check in [
        test_every_sitemap_url_has_a_file,
        test_deep_link_is_a_real_index_html,
        test_titles_are_unique_within_each_locale,
        test_hreflang_covers_every_locale_and_x_default,
        test_lang_attribute_matches_locale,
        test_translated_chrome_actually_differs,
        test_page_never_claims_growth_ranking_it_did_not_do,
        test_ranking_source_reports_what_it_returns,
        test_no_broken_plural_in_any_locale,
        test_avatar_tile_is_deterministic_and_decorative,
        test_avatar_tile_cannot_inject_css,
        test_cross_window_badge_excludes_current_window,
        test_cross_window_badge_renders_translated,
        test_truncated_list_states_shown_of_total,
        test_complete_list_says_nothing,
        test_truncation_note_present_in_every_locale,
        test_ranking_source_returns_full_pool_not_a_slice,
        test_card_topics_are_curated_not_raw,
        test_card_with_no_topics_emits_no_tag_row,
        test_card_topic_ordering_is_deterministic,
        test_every_card_pill_links_to_a_page_that_exists,
        test_repo_detail_still_shows_all_topics,
        test_crawled_text_is_escaped,
        test_json_ld_is_valid_json_and_cannot_break_out,
        test_velocity_branch_promotes_only_the_riser,
        test_canonical_matches_actual_path,
        test_robots_lists_sitemap_and_throttles_bots,
    ]:
        print(check.__name__)
        check()
    print("\nall checks passed")
