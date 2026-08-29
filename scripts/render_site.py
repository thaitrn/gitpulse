"""Render the published set to static HTML, once per locale.

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

import i18n
import prepare_data
from i18n import LOCALES, LOCALE_NAMES, LOCALE_TAGS, t

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
TEMPLATE = string.Template((ROOT / "templates" / "base.html").read_text())

# GitHub Pages project site lives under /<repo>. Every internal link is built
# from this, so moving to a custom domain is a one-line change.
BASE = "/gitpulse"
ORIGIN = "https://thaitrn.github.io"

WINDOWS = {1: "day", 7: "week", 30: "month"}

# List caps. Measured 2026-08-29: only 8 of 837 facet pages hold more than 200
# members (largest 514), so raising the cap would add weight to exactly the
# heaviest pages for almost no reach. Caps stay; what changes is that a truncated
# list now says so.
TRENDING_CAP = 100
FACET_CAP = 200
HOME_CAP = 30
NAV_ITEMS = (
    ("day", "/trending/day/"),
    ("week", "/trending/week/"),
    ("month", "/trending/month/"),
    ("topics", "/topics/"),
    ("languages", "/languages/"),
    ("methodology", "/methodology/"),
)

# Below this many points a line is noise rather than a trend, so the repo page
# shows stat tiles instead of a chart.
MIN_POINTS_FOR_CHART = 4

# Geometric arrows as inline SVG rather than emoji or text glyphs: consistent
# across platforms, inherits currentColor, and stays aria-hidden because the
# direction is already stated in the adjacent aria-label.
ARROW_UP = ('<svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">'
            '<path d="M5 1 9 8.5H1Z" fill="currentColor"/></svg>')
ARROW_DOWN = ('<svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">'
              '<path d="M5 9 1 1.5h8Z" fill="currentColor"/></svg>')


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def slug(value):
    """URL-safe single path segment.

    Topic and language names come from the API and can contain slashes, dots and
    unicode. Percent-encoding with an empty safe set guarantees one segment, so
    a crafted name can never escape its directory.
    """
    return urllib.parse.quote(str(value), safe="")


def compact(number):
    """12,345 -> 12.3k. Keeps dense list rows scannable; detail pages use full."""
    if number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M".replace(".0M", "M")
    if number >= 1_000:
        return f"{number / 1_000:.1f}k".replace(".0k", "k")
    return str(number)


def root(locale):
    """URL prefix for a locale, e.g. "/gitpulse" or "/gitpulse/vi"."""
    return f"{BASE}{i18n.prefix(locale)}"


def site_path(locale, path):
    """Filesystem path parts for a locale-relative URL path."""
    parts = [segment for segment in path.strip("/").split("/") if segment]
    return ([locale] if locale != LOCALES[0] else []) + parts


def write(locale, path, markup):
    target = SITE_DIR.joinpath(*site_path(locale, path)) / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markup)
    return target


def alternates(path):
    """hreflang links so the locales read as translations, not duplicate content."""
    links = [
        f'<link rel="alternate" hreflang="{LOCALE_TAGS[code]}" '
        f'href="{ORIGIN}{root(code)}{path}">'
        for code in LOCALES
    ]
    links.append(
        f'<link rel="alternate" hreflang="x-default" '
        f'href="{ORIGIN}{root(LOCALES[0])}{path}">'
    )
    return "\n".join(links)


def nav_markup(locale, current):
    items = "".join(
        f'<a href="{root(locale)}{href}"'
        f'{" aria-current=\"page\"" if key == current else ""}>'
        f"{esc(t(locale, f'nav_{key}'))}</a>"
        for key, href in NAV_ITEMS
    )
    return f'<nav aria-label="{esc(t(locale, "nav_label"))}">{items}</nav>'


def language_switcher(locale, path):
    """Links to the same page in every locale, not just to each locale's home."""
    items = "".join(
        f'<a href="{root(code)}{path}" lang="{LOCALE_TAGS[code]}"'
        f'{" aria-current=\"true\"" if code == locale else ""}>'
        f"{esc(LOCALE_NAMES[code])}</a>"
        for code in LOCALES
    )
    return (f'<div class="langs" role="group" '
            f'aria-label="{esc(t(locale, "lang_label"))}">{items}</div>')


def page(locale, title, description, path, body, generated_at,
         nav_key=None, head_extra=""):
    return TEMPLATE.substitute(
        lang=LOCALE_TAGS[locale],
        title=esc(title),
        description=esc(description),
        canonical=esc(f"{ORIGIN}{root(locale)}{path}"),
        alternates=alternates(path),
        skip_label=esc(t(locale, "skip")),
        home_href=f"{root(locale)}/",
        nav=nav_markup(locale, nav_key),
        lang_switcher=language_switcher(locale, path),
        methodology_href=f"{root(locale)}/methodology/",
        footer_data=esc(t(locale, "footer_data", date=generated_at[:10])),
        footer_how=esc(t(locale, "footer_how")),
        footer_source=esc(t(locale, "footer_source")),
        body=body,
        head_extra=head_extra,
    )


def repo_path(full_name):
    owner, name = full_name.split("/", 1)
    return f"/repo/{slug(owner)}/{slug(name)}/"


def momentum(locale, record, window=7):
    """The differentiator, given its own column and the largest number on a card.

    Direction is carried by an arrow and a signed number, never by colour alone.
    """
    delta, pct = record.get(f"star_{window}d"), record.get(f"star_{window}d_pct")
    if delta is None or pct is None:
        return ('<div class="momentum"><span class="mom-value mom-none">&mdash;</span>'
                f'<span class="mom-sub">{esc(t(locale, "no_history"))}</span></div>')
    arrow = ARROW_UP if delta > 0 else ARROW_DOWN
    css = "mom-up" if delta > 0 else "mom-down"
    label = f"{delta:+,} {t(locale, 'stars')}, {window}d"
    return (f'<div class="momentum"><span class="mom-value {css}" '
            f'aria-label="{esc(label)}">{arrow}{pct:+.1f}%</span>'
            f'<span class="mom-sub">{delta:+,} &middot; {window}d</span></div>')


def avatar_tile(owner):
    """Deterministic letter tile: same owner, same colour, everywhere, always.

    Real avatar images would mean one request per row to a third-party host,
    which this site does not make — and would leak visitor traffic and add
    layout shift. Only a derived integer hue reaches the style attribute; the
    owner string never does, so there is no CSS injection path.
    """
    initial = next((c for c in owner if c.isalnum()), "?").upper()
    hue = sum(ord(c) for c in owner) % 360
    return (f'<div class="card-avatar" aria-hidden="true" '
            f'style="background:hsl({hue} 45% var(--tile-l))">{esc(initial)}</div>')


def other_windows(record, data, current_window):
    """Windows other than this one where the repo is also ranked.

    A repo trending across several windows is a stronger signal than one
    appearing in a single window. The data is already computed; this is a set
    membership check, not a new query.
    """
    found = []
    for window, name in WINDOWS.items():
        if window == current_window:
            continue
        if any(row["full_name"] == record["full_name"]
               for row in data["trending"][window][:TRENDING_CAP]):
            found.append(name)
    return found


def repo_card(locale, record, whitelist, window=7, rank=None, data=None):
    owner, name = record["full_name"].split("/", 1)
    pills = "".join(
        f'<a href="{root(locale)}/topics/{slug(topic)}/">{esc(topic)}</a>'
        for topic in prepare_data.card_topics(record, whitelist)
    )
    # Curation leaves roughly a fifth of cards with no qualifying topic. An empty
    # .tags element still carries its top margin, so emitting it would put a
    # phantom gap under those cards and break the list's vertical rhythm.
    topics = f'<div class="tags">{pills}</div>' if pills else ""
    meta = [f"{compact(record['stars'])} {esc(t(locale, 'stars'))}"]
    if record.get("language"):
        meta.append(
            f'<a href="{root(locale)}/languages/{slug(record["language"])}/">'
            f'{esc(record["language"])}</a>'
        )
    if record.get("pushed_at"):
        meta.append(f"{esc(t(locale, 'pushed'))} {esc(record['pushed_at'])}")
    if data is not None:
        meta += [
            f'<span class="badge-window">{esc(t(locale, f"also_{name}"))}</span>'
            for name in other_windows(record, data, window)
        ]
    rank_markup = f'<div class="card-rank">{rank}</div>' if rank else ""
    return f"""<article class="card">{rank_markup}
{avatar_tile(owner)}
<div>
<h3 class="card-title"><a href="{root(locale)}{repo_path(record['full_name'])}"><span class="owner">{esc(owner)}/</span>{esc(name)}</a></h3>
<p class="card-desc">{esc(record.get('description'))}</p>
<div class="card-meta">{''.join(f'<span>{item}</span>' for item in meta)}</div>
{topics}
</div>
{momentum(locale, record, window)}
</article>"""


def window_state(data, window):
    """"accumulating" | "no_movers" | "ranked" for one window.

    Mirrors ranking_source(): the state and the sentence describing it come from
    one value, so a page cannot say something the data does not support. The
    windows fill at different times — 1-day needs two snapshots, 7-day needs
    eight — so a single site-wide counter cannot speak for any of them.
    """
    if not data["diagnostics"]["with_velocity_by_window"].get(window):
        return "accumulating"
    if not data["trending"][window]:
        return "no_movers"
    return "ranked"


def snapshots_needed(window):
    """Minimum daily snapshots before a window can produce a figure."""
    return window + 1


def window_state_notice(locale, data, window):
    """The one message this window's page should carry, if any."""
    state = window_state(data, window)
    if state == "ranked":
        return ""
    if state == "no_movers":
        return fallback_notice(locale)
    return (f'<div class="notice"><h3>{esc(t(locale, "notice_title"))}</h3>'
            f'<p>{esc(t(locale, "notice_body", have=data["diagnostics"]["snapshots_loaded"], need=snapshots_needed(window)))}'
            f"</p></div>")


def history_notice(locale, data, window=7):
    """Site-wide summary for pages that are not about one window.

    The home page leads with the weekly ranking, so it speaks for that window.
    """
    return window_state_notice(locale, data, window)


def sparkline(points, width=560, height=48):
    """Inline SVG polyline. Below MIN_POINTS_FOR_CHART a line would be noise."""
    values = [stars for _date, stars in points]
    if len(values) < MIN_POINTS_FOR_CHART:
        return ""
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
        f'role="img" aria-label="{values[0]:,} to {values[-1]:,} over {len(values)} days">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="1.75" '
        f'stroke-linejoin="round" points="{coords}"/></svg>'
    )


def stat_tiles(locale, record):
    """Always rendered: the accessible text form of the same numbers as the chart."""
    tiles = []
    for window, name in WINDOWS.items():
        delta = record.get(f"star_{window}d")
        pct = record.get(f"star_{window}d_pct")
        value = (
            f"{delta:+,} <span style='font-size:15px;color:var(--muted)'>({pct:+.1f}%)</span>"
            if delta is not None and pct is not None
            else '<span style="color:var(--muted)">&mdash;</span>'
        )
        tiles.append(
            f'<div class="stat"><span class="stat-label">'
            f'{esc(t(locale, f"window_{name}"))}</span>'
            f'<span class="stat-value">{value}</span></div>'
        )
    return f'<div class="stats">{"".join(tiles)}</div>'


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


def render_repo_pages(locale, data):
    for record in data["records"]:
        full_name = record["full_name"]
        owner, name = full_name.split("/", 1)
        history = data["history"].get(full_name, [])
        topics = "".join(
            f'<a href="{root(locale)}/topics/{slug(topic)}/">{esc(topic)}</a>'
            for topic in record["topics"]
        )
        chart = sparkline(history) or (
            f'<p class="mom-sub" style="font-size:14px">'
            f'{esc(t(locale, "repo_no_chart", have=len(history), need=MIN_POINTS_FOR_CHART))}'
            f"</p>"
        )
        facts = [
            f"{record['stars']:,} {esc(t(locale, 'stars'))}",
            f"{record['forks']:,} {esc(t(locale, 'forks'))}",
        ]
        if record.get("language"):
            facts.append(esc(record["language"]))
        if record.get("license"):
            facts.append(esc(record["license"]))
        facts.append(f"{esc(t(locale, 'pushed'))} {esc(record.get('pushed_at'))}")

        body = f"""<h1><span style="color:var(--muted);font-weight:450">{esc(owner)}/</span>{esc(name)}</h1>
<p class="lede">{esc(record.get('description'))}</p>
<div class="card-meta" style="margin-bottom:var(--s5)">{''.join(f'<span>{item}</span>' for item in facts)}</div>
<p><a href="https://github.com/{esc(full_name)}" target="_blank" rel="noopener noreferrer">{esc(t(locale, 'repo_github'))} &rarr;</a></p>
<h2>{esc(t(locale, 'repo_momentum'))}</h2>
{stat_tiles(locale, record)}
{chart}
<h2>{esc(t(locale, 'repo_topics'))}</h2>
<div class="tags">{topics or f'<span class="mom-sub">{esc(t(locale, "repo_none"))}</span>'}</div>
{json_ld(record)}"""
        write(
            locale,
            repo_path(full_name),
            page(
                locale,
                f"{full_name} — {record.get('language') or 'repository'}",
                (record.get("description") or full_name)[:155],
                repo_path(full_name),
                body,
                data["generated_at"],
            ),
        )


def ranking_source(data, window):
    """Decide what a trending list is actually ordered by.

    Returns ("growth", rows) or ("stars", rows). Previously the fallback was an
    `or` inside the render call, so the page's lede claimed growth ranking while
    showing a star-ordered list whenever a window had no qualifying movers. The
    page must not be able to describe itself differently from what it did, so
    the decision and the wording now come from the same value.
    """
    ranked = data["trending"][window]
    if ranked:
        return "growth", ranked
    # Before real velocity exists, ordering by total stars produces the all-time
    # list — median age of the top 100 was 7.6 years on a page titled "trending".
    # Lifetime stars per day needs no history and drops that to 0.5 years.
    by_rate = [r for r in data["records"] if r.get("star_rate") is not None]
    if by_rate:
        by_rate.sort(key=lambda r: (-r["star_rate"], r["full_name"]))
        return "rate", by_rate
    return "stars", data["records"]


def limited(rows, cap):
    """Slice a list and hand back the true total in one call.

    Returning both from one place is what stops the page from cutting rows while
    the surrounding copy implies completeness — the same failure the trending
    lede had. Callers must render `showing_note` with the total.
    """
    return rows[:cap], len(rows)


def showing_note(locale, shown, total):
    """Silent when nothing was cut: "Showing 12 of 12" is noise, not honesty."""
    if shown >= total:
        return ""
    return (f'<p class="mom-sub" style="font-size:14px;margin-bottom:var(--s4)">'
            f'{esc(t(locale, "showing_note", shown=f"{shown:,}", total=f"{total:,}"))}</p>')


def fallback_notice(locale):
    return (f'<div class="notice"><h3>{esc(t(locale, "fallback_title"))}</h3>'
            f'<p>{esc(t(locale, "fallback_body", delta=prepare_data.MIN_ABS_DELTA))}'
            f"</p></div>")


def render_trending(locale, data):
    for window, name in WINDOWS.items():
        order, pool = ranking_source(data, window)
        ranked, total = limited(pool, TRENDING_CAP)
        listing = "".join(
            repo_card(locale, record, data["topics"], window, rank=index, data=data)
            for index, record in enumerate(ranked, 1)
        )
        lede = t(locale, f"lede_{name}") if order == "growth" else t(locale, f"lede_{order}")
        explanation = window_state_notice(locale, data, window)
        path = f"/trending/{name}/"
        write(
            locale,
            path,
            page(
                locale,
                f"{t(locale, f'window_{name}')} — gitpulse",
                t(locale, f"desc_{name}"),
                path,
                f"<h1>{esc(t(locale, f'window_{name}'))}</h1>"
                f'<p class="lede">{esc(lede)}</p>'
                f"{explanation}{showing_note(locale, len(ranked), total)}{listing}",
                data["generated_at"],
                nav_key=name,
            ),
        )


def render_facets(locale, data):
    for kind, counts in (("topics", data["topics"]), ("languages", data["languages"])):
        heading = t(locale, f"{kind}_h1")
        rows = "".join(
            f'<tr><td><a href="{root(locale)}/{kind}/{slug(value)}/">{esc(value)}</a></td>'
            f"<td>{count}</td></tr>"
            for value, count in counts.items()
        )
        write(
            locale,
            f"/{kind}/",
            page(
                locale,
                f"{heading} — gitpulse",
                t(locale, "facet_desc", kind=heading.lower()),
                f"/{kind}/",
                f"<h1>{esc(heading)}</h1>"
                f'<p class="lede">'
                f'{esc(t(locale, "facet_lede", count=len(counts), kind=heading.lower(), min=prepare_data.MIN_MEMBERS_FOR_FACET_PAGE))}</p>'
                f"<table><thead><tr><th>{esc(heading)}</th>"
                f"<th>{esc(t(locale, 'col_repositories'))}</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>",
                data["generated_at"],
                nav_key=kind,
            ),
        )
        for value in counts:
            members = [
                record
                for record in data["records"]
                if (value in record["topics"] if kind == "topics"
                    else record.get("language") == value)
            ]
            shown, total = limited(members, FACET_CAP)
            listing = "".join(
                repo_card(locale, record, data["topics"]) for record in shown
            )
            path = f"/{kind}/{slug(value)}/"
            write(
                locale,
                path,
                page(
                    locale,
                    t(locale, "facet_page_title", value=value),
                    t(locale, "facet_page_desc", value=value),
                    path,
                    f"<h1>{esc(value)}</h1>"
                    f'<p class="lede">{esc(t(locale, "facet_members", count=f"{total:,}"))}</p>'
                    f"{showing_note(locale, len(shown), total)}{listing}",
                    data["generated_at"],
                    nav_key=kind,
                ),
            )


def render_home(locale, data):
    # Through ranking_source, not a second copy of the same fallback: the home
    # page had its own `or data["records"]`, so it kept showing the all-time list
    # after the trending pages stopped. Duplicated decision logic is what produced
    # this defect class in the first place.
    _order, pool = ranking_source(data, 7)
    ranked, _total = limited(pool, HOME_CAP)
    listing = "".join(
        repo_card(locale, record, data["topics"], rank=index, data=data)
        for index, record in enumerate(ranked, 1)
    )
    selection = (f'<p class="mom-sub" style="font-size:14px;margin-bottom:var(--s4)">'
                 f'{esc(t(locale, "home_selection_note", shown=len(ranked)))}</p>')
    search = f"""<label for="q" style="display:block;font-size:14px;color:var(--muted);margin-bottom:var(--s2)">{esc(t(locale, 'search_label'))}</label>
<input type="search" id="q" placeholder="{esc(t(locale, 'search_placeholder'))}" autocomplete="off">
<div id="results" aria-live="polite"></div>
<script>
const box=document.getElementById('q'),out=document.getElementById('results');
const NONE={json.dumps(t(locale, 'search_none'))},STARS={json.dumps(t(locale, 'stars'))},ROOT={json.dumps(root(locale))};
let index=null,timer;
const esc=s=>s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
const compact=n=>n>=1000?(n/1000).toFixed(1).replace(/\\.0$/,'')+'k':n;
box.addEventListener('input',()=>{{clearTimeout(timer);timer=setTimeout(run,150)}});
async function run(){{
  const term=box.value.trim().toLowerCase();
  if(term.length<2){{out.innerHTML='';return}}
  if(!index){{index=await(await fetch({json.dumps(BASE)}+'/data/index.json')).json()}}
  const hits=index.filter(r=>r.n.toLowerCase().includes(term)||(r.d||'').toLowerCase().includes(term)).slice(0,50);
  out.innerHTML=hits.length?hits.map(r=>{{
    const [owner,...rest]=r.n.split('/');
    return `<article class="card"><div><h3 class="card-title"><a href="${{ROOT}}/repo/${{r.n.split('/').map(encodeURIComponent).join('/')}}/"><span class="owner">${{esc(owner)}}/</span>${{esc(rest.join('/'))}}</a></h3><p class="card-desc">${{esc(r.d||'')}}</p><div class="card-meta"><span>${{compact(r.s)}} ${{STARS}}</span></div></div></article>`;
  }}).join(''):`<p class="mom-sub" style="font-size:15px">${{NONE}}</p>`;
}}
</script>"""
    diagnostics = data["diagnostics"]
    body = f"""<h1>{esc(t(locale, 'home_h1'))}</h1>
<p class="lede">{esc(t(locale, 'home_lede', tracked=f"{diagnostics['total_repos']:,}", published=f"{diagnostics['published']:,}"))}</p>
{search}
<h2>{esc(t(locale, 'rising'))}</h2>
{history_notice(locale, data)}
{selection}
{listing}"""
    write(
        locale,
        "/",
        page(
            locale,
            t(locale, "home_title"),
            t(locale, "home_desc"),
            "/",
            body,
            data["generated_at"],
        ),
    )


def render_methodology(locale, data):
    diagnostics = data["diagnostics"]
    body = f"""<h1>{esc(t(locale, 'methodology_h1'))}</h1>
<p class="lede">{esc(t(locale, 'methodology_lede'))}</p>
<h2>{esc(t(locale, 'm_tracked_h'))}</h2>
<p>{t(locale, 'm_tracked_p', gate=f"{prepare_data.PAGE_MIN_STARS:,}", floor="2,000", tracked=f"{diagnostics['total_repos']:,}", published=f"{diagnostics['published']:,}")}</p>
<h2>{esc(t(locale, 'm_velocity_h'))}</h2>
<p>{esc(t(locale, 'm_velocity_p1'))}</p>
<p>{esc(t(locale, 'm_velocity_p2', tolerance=prepare_data.STALENESS_TOLERANCE))}</p>
<h2>{esc(t(locale, 'm_rank_h'))}</h2>
<p>{t(locale, 'm_rank_p', delta=prepare_data.MIN_ABS_DELTA)}</p>
<h2>{esc(t(locale, 'm_gate_h'))}</h2>
<p>{esc(t(locale, 'm_gate_p', days=prepare_data.ACTIVE_DAYS, pct=prepare_data.MIN_VELOCITY_PCT, members=prepare_data.MIN_MEMBERS_FOR_FACET_PAGE))}</p>
<p>{esc(t(locale, 'm_stat_p', count=f"{diagnostics['with_velocity']:,}"))}</p>"""
    write(
        locale,
        "/methodology/",
        page(
            locale,
            t(locale, "methodology_title"),
            t(locale, "methodology_desc"),
            "/methodology/",
            body,
            data["generated_at"],
            nav_key="methodology",
        ),
    )


def render_search_index(data):
    """Slim index for client-side filtering, shared by every locale.

    Repository names and descriptions are not translated, so one file serves all
    locales rather than three identical copies.
    """
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
    for locale in LOCALES:
        render_home(locale, data)
        render_trending(locale, data)
        render_repo_pages(locale, data)
        render_facets(locale, data)
        render_methodology(locale, data)
    data["diagnostics"]["search_index_bytes"] = render_search_index(data)
    data["diagnostics"]["locales"] = len(LOCALES)
    return data


if __name__ == "__main__":
    result = build()
    print(json.dumps(result["diagnostics"], indent=2))
