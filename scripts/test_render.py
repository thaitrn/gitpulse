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
        target = site_dir / "repo" / "dotted" / "some.thing.js" / "index.html"
        assert target.exists(), "dotted repo name did not produce a page"
        print("  ok: repo name containing dots resolves to index.html")


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


def test_titles_are_unique():
    with tempfile.TemporaryDirectory() as tmp:
        _data, site_dir = build_into(tmp)
        titles = [
            re.search(r"<title>(.*?)</title>", path.read_text(), re.S).group(1)
            for path in site_dir.rglob("index.html")
        ]
        duplicates = {title for title in titles if titles.count(title) > 1}
        assert not duplicates, f"duplicate titles: {duplicates}"
        print(f"  ok: {len(titles)} pages, all titles unique")


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
        test_crawled_text_is_escaped,
        test_json_ld_is_valid_json_and_cannot_break_out,
        test_velocity_branch_promotes_only_the_riser,
        test_titles_are_unique,
        test_canonical_matches_actual_path,
        test_robots_lists_sitemap_and_throttles_bots,
    ]:
        print(check.__name__)
        check()
    print("\nall checks passed")
