"""Sitemap index and robots.txt, derived from the gate rather than the filesystem.

A sitemap that lists a URL which 404s, or omits one that exists, is worse than
having none — it trains crawlers to distrust the file. Both the pages and these
URLs come from the same published set, so they cannot drift apart.

lastmod uses each repository's pushed_at, not the generation timestamp. Stamping
every URL with "today" on every daily run teaches crawlers to ignore lastmod
entirely.
"""

import pathlib
import xml.etree.ElementTree as ET

from render_site import BASE, ORIGIN, slug

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Well under the 50,000 URL limit at current scale. Sharding now costs nothing
# and avoids a URL-structure change later, which resets accumulated crawl trust.
URLS_PER_SHARD = 10_000

# Aggressive AI and SEO crawlers hammer a static host. Throttled rather than
# blocked: discoverability inside AI assistants is real traffic for a developer
# directory. Googlebot and Bingbot stay unrestricted under the wildcard.
THROTTLED_BOTS = (
    "ClaudeBot",
    "Amazonbot",
    "Bytespider",
    "PetalBot",
    "AhrefsBot",
    "SemrushBot",
    "GPTBot",
)


def absolute(path):
    return f"{ORIGIN}{BASE}{path}"


def urlset(entries):
    root = ET.Element("urlset", xmlns=NAMESPACE)
    for path, lastmod in entries:
        node = ET.SubElement(root, "url")
        ET.SubElement(node, "loc").text = absolute(path)
        if lastmod:
            ET.SubElement(node, "lastmod").text = lastmod
    return ET.ElementTree(root)


def write_tree(tree, *parts):
    target = SITE_DIR.joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(target, encoding="utf-8", xml_declaration=True)
    return target


def collect(data):
    """Every published URL, grouped the way the sitemap index shards them."""
    core = [("/", None), ("/methodology/", None), ("/topics/", None), ("/languages/", None)]

    rankings = [(f"/trending/{name}/", None) for name, _ in
                (("day", 1), ("week", 7), ("month", 30))]
    rankings += [(f"/topics/{slug(value)}/", None) for value in data["topics"]]
    rankings += [(f"/languages/{slug(value)}/", None) for value in data["languages"]]

    repos = []
    for record in data["records"]:
        owner, name = record["full_name"].split("/", 1)
        repos.append((f"/repo/{slug(owner)}/{slug(name)}/", record.get("pushed_at")))

    return {"core": core, "rankings": rankings, "repos": repos}


def generate(data):
    groups = collect(data)
    children = []

    for name in ("core", "rankings"):
        write_tree(urlset(groups[name]), "sitemaps", f"{name}.xml")
        children.append(f"/sitemaps/{name}.xml")

    repos = groups["repos"]
    for shard_index in range(0, max(len(repos), 1), URLS_PER_SHARD):
        number = shard_index // URLS_PER_SHARD + 1
        write_tree(
            urlset(repos[shard_index:shard_index + URLS_PER_SHARD]),
            "sitemaps",
            f"repos-{number}.xml",
        )
        children.append(f"/sitemaps/repos-{number}.xml")

    index = ET.Element("sitemapindex", xmlns=NAMESPACE)
    for path in children:
        node = ET.SubElement(index, "sitemap")
        ET.SubElement(node, "loc").text = absolute(path)
    write_tree(ET.ElementTree(index), "sitemap.xml")

    write_robots()
    return sum(len(group) for group in groups.values())


def write_robots():
    blocks = ["User-Agent: *", "Allow: /", ""]
    for bot in THROTTLED_BOTS:
        blocks += [f"User-Agent: {bot}", "Allow: /", "Crawl-delay: 10", ""]
    blocks += [f"Host: {ORIGIN}{BASE}", f"Sitemap: {absolute('/sitemap.xml')}", ""]
    (SITE_DIR / "robots.txt").write_text("\n".join(blocks))


if __name__ == "__main__":
    import render_site

    site = render_site.build()
    print(f"{generate(site)} urls in sitemaps")
