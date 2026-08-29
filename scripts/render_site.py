"""Render the published set to static HTML.

Every page is written as <path>/index.html so a deep link resolves on a plain
static host without rewrite rules — the standard trap that makes a statically
exported site work under client-side navigation but 404 when a search engine
lands on it directly.

All crawled text (descriptions, topics, names) is arbitrary input from GitHub
users and is escaped at every insertion point. Nothing here builds markup by
concatenating unescaped crawled strings.
"""

import html
import json
import pathlib
import string
import urllib.parse

import prepare_data

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
TEMPLATE = string.Template((ROOT / "templates" / "base.html").read_text())

# GitHub Pages project site lives under /<repo>. Every internal link is built
# from this, so moving to a custom domain is a one-line change.
BASE = "/gitpulse"
ORIGIN = "https://thaitrn.github.io"

WINDOW_LABELS = {1: ("day", "Today"), 7: ("week", "This week"), 30: ("month", "This month")}


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def slug(value):
    """URL-safe single path segment.

    Topic and language names come from the API and can contain slashes, dots and
    unicode. Percent-encoding with an empty safe set guarantees one segment, so
    a crafted name can never escape its directory.
    """
    return urllib.parse.quote(str(value), safe="")


def write(path_parts, markup):
    target = SITE_DIR.joinpath(*path_parts) / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup)
    return target


def page(title, description, canonical_path, body, generated_at, head_extra=""):
    return TEMPLATE.substitute(
        title=esc(title),
        description=esc(description),
        canonical=esc(f"{ORIGIN}{BASE}{canonical_path}"),
        base=BASE,
        body=body,
        head_extra=head_extra,
        generated_note=esc(f"Updated {generated_at[:10]}."),
    )


def repo_url(full_name):
    owner, name = full_name.split("/", 1)
    return f"{BASE}/repo/{slug(owner)}/{slug(name)}/"


def velocity_badge(record, window=7):
    delta, pct = record.get(f"star_{window}d"), record.get(f"star_{window}d_pct")
    if delta is None or pct is None:
        return '<span class="down">no history yet</span>'
    css = "up" if delta > 0 else "down"
    return f'<span class="{css}">{delta:+,} ({pct:+.1f}%) / {window}d</span>'


def repo_card(record, window=7):
    topics = "".join(
        f'<a href="{BASE}/topics/{slug(topic)}/">{esc(topic)}</a>'
        for topic in record["topics"][:6]
    )
    language = (
        f'<a href="{BASE}/languages/{slug(record["language"])}/">{esc(record["language"])}</a>'
        if record.get("language")
        else ""
    )
    return f"""<div class="repo">
<div class="repo-name"><a href="{repo_url(record['full_name'])}">{esc(record['full_name'])}</a></div>
<p class="repo-desc">{esc(record.get('description'))}</p>
<div class="meta"><span>{record['stars']:,} stars</span>{f'<span>{language}</span>' if language else ''}<span>{velocity_badge(record, window)}</span></div>
<div class="tags">{topics}</div>
</div>"""


def sparkline(points, width=520, height=44):
    """Inline SVG from (date, stars) pairs. No chart library for a polyline."""
    values = [stars for _date, stars in points]
    if len(values) < 2:
        return '<p class="empty">Not enough history for a chart yet.</p>'
    low, high = min(values), max(values)
    span = (high - low) or 1
    step = width / (len(values) - 1)
    # Coerced to float before interpolation: crawled numbers never reach markup
    # as raw strings.
    coords = " ".join(
        f"{index * step:.1f},{height - (float(value) - low) / span * (height - 4) - 2:.1f}"
        for index, value in enumerate(values)
    )
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="Star history, {values[0]:,} to {values[-1]:,}">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.5" points="{coords}"/></svg>'
    )


def render_repo_pages(data):
    for record in data["records"]:
        full_name = record["full_name"]
        owner, name = full_name.split("/", 1)
        history = data["history"].get(full_name, [])
        topics = "".join(
            f'<a href="{BASE}/topics/{slug(topic)}/">{esc(topic)}</a>'
            for topic in record["topics"]
        )
        rows = "".join(
            f"<tr><td>{label}</td><td>{velocity_badge(record, window)}</td></tr>"
            for window, (_slug, label) in WINDOW_LABELS.items()
        )
        body = f"""<h2>{esc(full_name)}</h2>
<p class="repo-desc">{esc(record.get('description'))}</p>
<div class="meta">
<span>{record['stars']:,} stars</span><span>{record['forks']:,} forks</span>
{f"<span>{esc(record['language'])}</span>" if record.get('language') else ''}
{f"<span>{esc(record['license'])}</span>" if record.get('license') else ''}
<span>pushed {esc(record.get('pushed_at'))}</span>
</div>
<p><a href="https://github.com/{esc(full_name)}" target="_blank" rel="noopener noreferrer">View on GitHub &rarr;</a></p>
<h2>Star history</h2>
{sparkline(history)}
<table><tbody>{rows}</tbody></table>
<h2>Topics</h2>
<div class="tags">{topics or '<span class="empty">none</span>'}</div>
{json_ld(record)}"""
        write(
            ["repo", slug(owner), slug(name)],
            page(
                f"{full_name} — {record.get('language') or 'repository'}",
                (record.get("description") or full_name)[:155],
                f"/repo/{slug(owner)}/{slug(name)}/",
                body,
                data["generated_at"],
            ),
        )


def json_ld(record):
    """SoftwareSourceCode from crawled facts only. No invented ratings.

    Serialised with json.dumps, never string concatenation: a description
    containing a quote or </script> must not break out of the script element.
    """
    payload = {
        "@context": "https://schema.org",
        "@type": "SoftwareSourceCode",
        "name": record["full_name"],
        "description": record.get("description"),
        "codeRepository": f"https://github.com/{record['full_name']}",
        "programmingLanguage": record.get("language"),
        "license": record.get("license"),
    }
    payload = {key: value for key, value in payload.items() if value}
    encoded = json.dumps(payload).replace("</", "<\\/")
    return f'<script type="application/ld+json">{encoded}</script>'


def render_trending(data):
    for window, (window_slug, label) in WINDOW_LABELS.items():
        ranked = data["trending"][window][:100]
        listing = "".join(repo_card(record, window) for record in ranked) or (
            '<p class="empty">Not enough snapshot history yet. Velocity needs '
            "several consecutive daily crawls before this page has numbers.</p>"
        )
        write(
            ["trending", window_slug],
            page(
                f"Trending repositories — {label.lower()}",
                f"GitHub repositories gaining stars fastest over the last {window} day(s).",
                f"/trending/{window_slug}/",
                f"<h2>{esc(label)}</h2>{listing}",
                data["generated_at"],
            ),
        )


def render_facets(data):
    for kind, counts, heading in (
        ("topics", data["topics"], "Topics"),
        ("languages", data["languages"], "Languages"),
    ):
        index_rows = "".join(
            f'<tr><td><a href="{BASE}/{kind}/{slug(value)}/">{esc(value)}</a></td>'
            f"<td>{count}</td></tr>"
            for value, count in counts.items()
        )
        write(
            [kind],
            page(
                f"{heading} — gitpulse",
                f"Browse tracked GitHub repositories by {kind[:-1]}.",
                f"/{kind}/",
                f"<h2>{heading}</h2><table><tbody>{index_rows}</tbody></table>",
                data["generated_at"],
            ),
        )
        for value in counts:
            members = [
                record
                for record in data["records"]
                if (value in record["topics"] if kind == "topics" else record.get("language") == value)
            ]
            listing = "".join(repo_card(record) for record in members[:200])
            write(
                [kind, slug(value)],
                page(
                    f"{value} repositories",
                    f"Tracked GitHub repositories for {value}.",
                    f"/{kind}/{slug(value)}/",
                    f"<h2>{esc(value)}</h2>{listing}",
                    data["generated_at"],
                ),
            )


def render_home(data):
    week = data["trending"][7][:30]
    listing = "".join(repo_card(record) for record in week)
    if not listing:
        listing = "".join(repo_card(record) for record in data["records"][:30])
    search = """<input type="search" id="q" placeholder="Filter tracked repositories..." autocomplete="off">
<div id="results"></div>
<script>
const box=document.getElementById('q'),out=document.getElementById('results');
let index=null;
const esc=s=>s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
box.addEventListener('input',async()=>{
  const term=box.value.trim().toLowerCase();
  if(term.length<2){out.innerHTML='';return}
  if(!index){index=await(await fetch('BASE_PATH/data/index.json')).json()}
  const hits=index.filter(r=>r.n.toLowerCase().includes(term)||(r.d||'').toLowerCase().includes(term)).slice(0,50);
  out.innerHTML=hits.map(r=>`<div class="repo"><div class="repo-name"><a href="BASE_PATH/repo/${r.n.split('/').map(encodeURIComponent).join('/')}/">${esc(r.n)}</a></div><p class="repo-desc">${esc(r.d||'')}</p><div class="meta"><span>${r.s.toLocaleString()} stars</span></div></div>`).join('')||'<p class="empty">No matches.</p>';
});
</script>""".replace("BASE_PATH", BASE)
    body = f"""<h2>Search</h2>{search}
<h2>Rising this week</h2>{listing}"""
    write(
        [],
        page(
            "gitpulse — GitHub repositories, ranked by momentum",
            "Daily star snapshots across GitHub, turned into real 1d/7d/30d growth "
            "rates. Only substantive repositories get a page.",
            "/",
            body,
            data["generated_at"],
        ),
    )


def render_methodology(data):
    diagnostics = data["diagnostics"]
    body = f"""<h2>Methodology</h2>
<p>Every figure comes from GitHub's public API. Nothing is invented, and there
are no editorial ratings.</p>
<h2>What gets tracked</h2>
<p>Repositories at or above <strong>{prepare_data.PAGE_MIN_STARS:,}</strong> stars get a page.
Repositories from <strong>{2000:,}</strong> stars upward are tracked in the dataset without a
page, so a smaller project that starts accelerating can be promoted. Currently
{diagnostics['total_repos']:,} tracked, {diagnostics['published']:,} published.</p>
<h2>How velocity is computed</h2>
<p>Star counts are snapshotted once a day. GitHub exposes only the current
count, so history has to be accumulated and cannot be backfilled.</p>
<p>A window compares the current count against the most recent snapshot on or
before that many days ago. If the nearest available snapshot is more than
{prepare_data.STALENESS_TOLERANCE} days staler than the target, no figure is published for that window
rather than a mislabelled one. A repository without enough history shows no
velocity at all, never zero.</p>
<h2>Ranking</h2>
<p>Trending pages rank by percentage growth, but only for repositories that
also gained at least <strong>{prepare_data.MIN_ABS_DELTA}</strong> stars in the window. Percentage alone
favours tiny absolute moves on small repositories.</p>
<h2>Publishing thresholds</h2>
<p>A repository gets a page when it is not archived, has a description, was
pushed within {prepare_data.ACTIVE_DAYS} days, and either passes the star threshold above or gained
at least {prepare_data.MIN_VELOCITY_PCT}% over 7 days. Topic and language pages need at least
{prepare_data.MIN_MEMBERS_FOR_FACET_PAGE} members.</p>
<p>{diagnostics['with_velocity']:,} published repositories currently have enough
history for a 7-day figure.</p>"""
    write(
        ["methodology"],
        page(
            "Methodology — gitpulse",
            "How repositories are tracked, ranked and published.",
            "/methodology/",
            body,
            data["generated_at"],
        ),
    )


def render_search_index(data):
    """Slim index for client-side filtering: short keys keep the payload small."""
    index = [
        {
            "n": record["full_name"],
            "d": (record.get("description") or "")[:160],
            "s": record["stars"],
        }
        for record in data["records"]
    ]
    target = SITE_DIR / "data"
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    return len(json.dumps(index))


def build():
    data = prepare_data.build()
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    render_home(data)
    render_trending(data)
    render_repo_pages(data)
    render_facets(data)
    render_methodology(data)
    index_bytes = render_search_index(data)
    data["diagnostics"]["search_index_bytes"] = index_bytes
    return data


if __name__ == "__main__":
    result = build()
    print(json.dumps(result["diagnostics"], indent=2))
