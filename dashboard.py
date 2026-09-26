"""Builds a self-contained, interactive HTML ROI dashboard.

Python writes the page and the starting assumptions. The maths and charts then
run in the browser (JavaScript), so a consultant can change any number live in
a client meeting. The JavaScript `calc()` mirrors `calculate_roi()` in roi.py;
if you change the formula in one place, change it in the other too.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import base64
import json
import urllib.request
from datetime import date
from html import escape
from pathlib import Path

from roi import (BENCHMARK, CURRENCIES, DEFAULT_SGD_PER_USD, FTE_HOURS_PER_YEAR, MINUTES_PER_ACTION,
                 WORKING_WEEKS, RoiResult, to_usd)

LOGO_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
}
MAX_LOGO_BYTES = 2 * 1024 * 1024


def _download_image(url: str) -> str | None:
    """Download an https image and return it as a data URI, or None if that fails."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "copilot-consultant-mcp"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read(MAX_LOGO_BYTES + 1)
            mime = resp.headers.get_content_type()
    except (OSError, ValueError):
        return None
    if len(data) > MAX_LOGO_BYTES:
        return None
    if not mime.startswith("image/"):
        mime = LOGO_TYPES.get(Path(url.split("?")[0]).suffix.lower(), "")
        if not mime:
            return None
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def logo_src(logo: str | None) -> str | None:
    """Turn a local image path or an https URL into something <img src> can use.

    Images are embedded (base64) so the HTML still works offline and when emailed.
    If an https image can't be downloaded, the page links to it instead.
    """
    if not logo:
        return None
    if logo.startswith("https://"):
        return _download_image(logo) or logo
    path = Path(logo).expanduser()
    mime = LOGO_TYPES.get(path.suffix.lower())
    if not path.is_file() or mime is None:
        raise ValueError(
            f"Logo not found or not an image: {logo}. "
            "Use a .png, .jpg, .svg, .gif or .webp file path, or an https:// URL."
        )
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def build_dashboard(
    r: RoiResult,
    client_name: str,
    currency: str = "USD",
    logo: str | None = None,
    prepared_by: str | None = None,
    partner_name: str | None = None,
    partner_logo: str | None = None,
    usage: dict | None = None,
    sgd_per_usd: float = DEFAULT_SGD_PER_USD,
    author: str = "Shenuka Fernando",
) -> str:
    """Return the full HTML page as a string.

    currency: "USD" or "SGD" - the currency of the money values in r, and the one the page opens in.
        The page has a switch to show everything in the other currency too.
    usage: the summary from copilot_export.load_copilot_export(), or None.
    """
    if currency not in CURRENCIES:
        raise ValueError(f"currency must be one of {', '.join(CURRENCIES)}.")
    if sgd_per_usd <= 0:
        raise ValueError("sgd_per_usd must be greater than zero.")
    client_src = logo_src(logo)
    partner_src = logo_src(partner_logo)

    initials = "".join(w[0] for w in client_name.split()[:2]).upper() or "?"
    client_logo = (f'<img class="logo" src="{escape(client_src, quote=True)}" alt="{escape(client_name)} logo">'
                   if client_src else f'<div class="logo logo-fallback" aria-hidden="true">{escape(initials)}</div>')
    client_logo = f'<div id="client-logo-slot">{client_logo}</div>'

    subtitle = f"Prepared {date.today():%d %B %Y}"
    # The partner (the consultancy preparing the business case) is always shown as "Prepared by",
    # with a slot the viewer can fill using the "Upload partner logo" button.
    mark = (f'<img class="partner-logo" src="{escape(partner_src, quote=True)}" alt="{escape(partner_name or "Partner")} logo">'
            if partner_src else f'<span class="partner-name">{escape(partner_name or "")}</span>')
    who = f'<span class="brand-who">{escape(prepared_by)}</span>' if prepared_by else ""
    brand = (f'<div class="brand"><span class="brand-label">Prepared by</span>'
             f'<div id="partner-logo-slot">{mark}</div>{who}</div>')

    # Starting assumptions for the page. "<" is escaped so the JSON can never close the <script> tag.
    base = {
        "users": r.users,
        "adoption": round(r.adoption_rate * 100),
        "meetings": r.meeting_hours_per_week,
        "search": r.search_actions_per_week,
        "creation": r.creation_actions_per_week,
        # Money is stored in USD; the page converts to SGD for display.
        "hourly": round(to_usd(r.hourly_cost, currency, sgd_per_usd), 4),
        "licence": round(to_usd(r.licence_cost_per_user_per_month, currency, sgd_per_usd), 4),
        "oneOff": round(to_usd(r.one_off_costs, currency, sgd_per_usd), 4),
        "realisation": round(r.realisation_rate * 100),
    }
    config = {
        "base": base, "currency": currency, "symbols": CURRENCIES, "fx": sgd_per_usd, "weeks": WORKING_WEEKS,
        "minutesPerAction": MINUTES_PER_ACTION, "fteHours": FTE_HOURS_PER_YEAR, "benchmark": BENCHMARK,
        "usage": usage,
    }
    config_json = json.dumps(config).replace("<", "\\u003c")

    return (PAGE
            .replace("__TITLE__", escape(f"{client_name} Copilot ROI"))
            .replace("__CLIENT__", escape(client_name))
            .replace("__CLIENT_LOGO__", client_logo)
            .replace("__BRAND__", brand)
            .replace("__SUBTITLE__", subtitle)
            .replace("__WEEKS__", str(WORKING_WEEKS))
            .replace("__AUTHOR__", escape(author))
            .replace("__YEAR__", str(date.today().year))
            .replace("__CONFIG_JSON__", config_json))


# ---------------------------------------------------------------------------
# The page template. Placeholders look like __NAME__ and are filled above.
# (A plain string, not an f-string, so CSS and JavaScript braces stay simple.)
# ---------------------------------------------------------------------------

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="author" content="__AUTHOR__">
<title>__TITLE__</title>
<style>
:root {
  color-scheme: light;
  --page: #f4f5f7; --surface: #ffffff; --border: rgba(11,11,11,0.08);
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #6f6e69;
  --grid: #e1e0d9; --baseline: #c3c2b7; --muted-mark: #c9c8c0; --wash: #f0efec;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a;
  --tint-1: #e8f1fc; --tint-2: #fdeee7; --tint-3: #e3f6ee;
  --good: #006300; --bad: #d03b3b;
  --hero-a: #0d366b; --hero-b: #256abf;
  --shadow: 0 1px 2px rgba(16,24,40,0.04), 0 4px 16px rgba(16,24,40,0.06);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --border: rgba(255,255,255,0.10);
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #a3a29b;
    --grid: #2c2c2a; --baseline: #383835; --muted-mark: #52514e; --wash: #2c2c2a;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
    --tint-1: #16273d; --tint-2: #35200f; --tint-3: #0f2e23;
    --good: #0ca30c; --bad: #e66767;
    --hero-a: #0d2a52; --hero-b: #1c5cab; --shadow: none;
  }
  :root:not([data-theme="light"]) img.logo,
  :root:not([data-theme="light"]) img.partner-logo { background: #ffffff; border-radius: 8px; padding: 6px 10px; }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --border: rgba(255,255,255,0.10);
  --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #a3a29b;
  --grid: #2c2c2a; --baseline: #383835; --muted-mark: #52514e; --wash: #2c2c2a;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70;
  --tint-1: #16273d; --tint-2: #35200f; --tint-3: #0f2e23;
  --good: #0ca30c; --bad: #e66767;
  --hero-a: #0d2a52; --hero-b: #1c5cab; --shadow: none;
}
:root[data-theme="dark"] img.logo,
:root[data-theme="dark"] img.partner-logo { background: #ffffff; border-radius: 8px; padding: 6px 10px; }

* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--page); color: var(--text-primary);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 28px 16px 48px; }
header { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 20px; margin-bottom: 20px; }
.title { flex: 1 1 320px; }
.logo { height: 56px; max-width: 180px; object-fit: contain; }
.logo-fallback { width: 56px; display: grid; place-items: center; border-radius: 12px;
  background: var(--surface); border: 1px solid var(--border); font-weight: 600; font-size: 20px; }
.brand { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; }
.brand-label { font-size: 12px; color: var(--text-muted); }
.partner-logo { height: 76px; max-width: 200px; object-fit: contain; display: block; }
.partner-name { font-weight: 700; font-size: 18px; }
.brand-who { font-size: 13px; color: var(--text-secondary); }
h1 { margin: 0; font-size: 24px; font-weight: 600; }
h2 { margin: 0 0 2px; font-size: 16px; font-weight: 600; }
.sub { color: var(--text-secondary); margin: 2px 0 0; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px; box-shadow: var(--shadow); }
.card-sub { color: var(--text-secondary); font-size: 14px; margin: 0 0 14px; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-bottom: 16px; align-items: stretch; }

/* Hero banner */
.hero { position: relative; overflow: hidden; border-radius: 18px; padding: 28px; margin-bottom: 16px; color: #fff;
  background: linear-gradient(135deg, var(--hero-a) 0%, var(--hero-b) 100%);
  display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr); gap: 24px; align-items: center; }
.hero::after { content: ""; position: absolute; right: -80px; top: -80px; width: 280px; height: 280px; border-radius: 50%;
  background: rgba(255,255,255,0.06); pointer-events: none; }
.hero .eyebrow { font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.85; }
.hero .big { font-size: 60px; font-weight: 700; line-height: 1.05; margin: 6px 0; }
.hero .big.neg { color: #ffd4d4; }
.hero .hero-sub { opacity: 0.9; margin-bottom: 18px; }
.pills { display: flex; flex-wrap: wrap; gap: 10px; }
.pill { background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.18); border-radius: 12px; padding: 10px 14px; min-width: 130px; }
.pill .pv { font-size: 22px; font-weight: 700; }
.pill .pl { font-size: 12px; opacity: 0.85; }
.gauge-wrap { text-align: center; position: relative; z-index: 1; }
.gauge-wrap .gl { font-size: 13px; opacity: 0.9; margin-top: 4px; }
.gauge-track { stroke: rgba(255,255,255,0.16); }
.gauge-band { stroke: rgba(255,255,255,0.38); }
.gauge-val { stroke: #ffffff; }
.gauge-text { fill: #ffffff; font-weight: 700; font-size: 34px; }
.gauge-small { fill: rgba(255,255,255,0.85); font-size: 12px; }
@media (max-width: 760px) { .hero { grid-template-columns: 1fr; } .hero .big { font-size: 44px; } }

/* Controls */
details.controls { margin-bottom: 16px; }
details.controls summary { cursor: pointer; font-weight: 600; list-style: none; display: flex; align-items: center; gap: 8px; }
details.controls summary::-webkit-details-marker { display: none; }
details.controls summary .chev { transition: transform .15s; }
details[open].controls summary .chev { transform: rotate(90deg); }
.toolbar { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; margin: 16px 0; }
.toolbar .spacer { flex: 1; }
.group-label { font-size: 13px; color: var(--text-secondary); margin-right: 8px; }
.seg { display: inline-flex; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--page); }
.seg button { border: 0; background: transparent; color: var(--text-secondary); padding: 6px 12px; font: inherit; font-size: 14px; cursor: pointer; }
.seg button + button { border-left: 1px solid var(--border); }
.seg button[aria-pressed="true"] { background: var(--series-1); color: #fff; font-weight: 600; }
.btn { border: 1px solid var(--border); background: var(--surface); color: var(--text-primary);
  border-radius: 10px; padding: 6px 12px; font: inherit; font-size: 14px; cursor: pointer; }
.btn:hover { background: var(--wash); }
.logo-tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
.btn-sm { font-size: 13px; padding: 4px 10px; cursor: pointer; display: inline-block; }
.logo-msg { font-size: 13px; color: var(--text-muted); }
.check { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--text-secondary); cursor: pointer; }
.fieldset-title { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin: 16px 0 8px; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px 24px; }
.field { display: flex; flex-direction: column; justify-content: flex-end; }
.field label { font-size: 13px; color: var(--text-secondary); }
.field .row { display: flex; gap: 10px; align-items: center; }
.field input[type=range] { flex: 1; accent-color: var(--series-1); min-width: 0; }
.field input[type=number] { width: 96px; padding: 4px 6px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--page); color: var(--text-primary); font: inherit; font-size: 14px; font-variant-numeric: tabular-nums; }
.scenario-note { font-size: 13px; color: var(--text-muted); margin: 12px 0 0; }

/* KPI tiles */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; margin-bottom: 16px; }
.kpi { display: flex; gap: 14px; align-items: flex-start; }
.icon { flex: none; width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; }
.icon svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.i1 { background: var(--tint-1); color: var(--series-1); } .i2 { background: var(--tint-2); color: var(--series-2); }
.i3 { background: var(--tint-3); color: var(--series-3); } .i4 { background: var(--wash); color: var(--text-secondary); }
.kpi .label { color: var(--text-secondary); font-size: 14px; }
.kpi .value { font-size: 28px; font-weight: 700; line-height: 1.2; margin: 2px 0; }
.kpi .note { color: var(--text-muted); font-size: 13px; }

/* Time breakdown */
.stack { display: flex; gap: 2px; height: 22px; margin: 6px 0 18px; }
.stack div { height: 100%; min-width: 2px; }
.stack div:first-child { border-radius: 6px 0 0 6px; } .stack div:last-child { border-radius: 0 6px 6px 0; }
.cats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; }
.cat { border-radius: 12px; padding: 12px; background: var(--page); }
.cat .ch { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); }
.cat .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.cat .cv { font-size: 22px; font-weight: 700; margin-top: 4px; }
.cat .cn { font-size: 12px; color: var(--text-muted); }

/* Adoption pictogram */
.people { display: grid; grid-template-columns: repeat(10, 1fr); gap: 6px; margin: 8px 0 14px; max-width: 420px; }
.people svg { width: 100%; height: auto; }
.person-on { fill: var(--series-1); } .person-off { fill: var(--muted-mark); }
.stat-line { font-size: 14px; color: var(--text-secondary); }
.stat-line strong { color: var(--text-primary); font-size: 18px; }
.meter { height: 10px; border-radius: 6px; background: var(--tint-1); overflow: hidden; margin: 6px 0 4px; }
.meter div { height: 100%; background: var(--series-1); border-radius: 6px; }

/* Charts */
svg { display: block; }
.chart svg { width: 100%; height: auto; overflow: visible; }
.gridline { stroke: var(--grid); stroke-width: 1; } .gridline.strong { stroke: var(--baseline); }
.baseline { stroke: var(--baseline); stroke-width: 1; }
.tick { fill: var(--text-muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.axis-label { fill: var(--text-secondary); font-size: 13px; }
.value-label { fill: var(--text-primary); font-size: 13px; font-weight: 600; }
.series { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.mdot { stroke: var(--surface); stroke-width: 2; }
.crosshair { stroke: var(--text-muted); stroke-width: 1; visibility: hidden; }
.hit:hover path { opacity: 0.85; }
.legend { display: flex; gap: 8px; font-size: 13px; margin: 0 0 8px; }
.legend button { border: 1px solid transparent; background: transparent; color: var(--text-secondary);
  border-radius: 6px; padding: 2px 8px; font: inherit; font-size: 13px; cursor: pointer; }
.legend button:hover { border-color: var(--border); }
.legend button[aria-pressed="false"] { opacity: 0.45; text-decoration: line-through; }
.swatch { display: inline-block; width: 12px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }

/* Tabs */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--grid); margin: 0 0 20px; overflow-x: auto; }
.tabs button { border: 0; background: transparent; color: var(--text-secondary); font: inherit; font-weight: 600;
  padding: 10px 16px; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -1px; white-space: nowrap; }
.tabs button[aria-selected="true"] { color: var(--series-1); border-bottom-color: var(--series-1); }
.tabs button:hover { color: var(--text-primary); }
.badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px;
  background: var(--tint-3); color: var(--series-3); margin-left: 6px; vertical-align: middle; }
.notice { border-radius: 12px; padding: 12px 16px; background: var(--tint-1); color: var(--text-primary); font-size: 14px; margin-bottom: 16px; }
.filters { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; margin-bottom: 16px; }
.filters label { font-size: 13px; color: var(--text-secondary); display: flex; align-items: center; gap: 8px; }
.filters select { font: inherit; font-size: 14px; padding: 5px 8px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface); color: var(--text-primary); }
.cell-meter { display: flex; align-items: center; gap: 8px; justify-content: flex-end; }
.cell-meter span.bar { width: 90px; height: 8px; border-radius: 4px; background: var(--tint-1); overflow: hidden; display: inline-block; }
.cell-meter span.bar i { display: block; height: 100%; background: var(--series-1); }
.steps { counter-reset: step; list-style: none; padding: 0; margin: 0; }
.steps li { counter-increment: step; position: relative; padding: 0 0 14px 44px; }
.steps li::before { content: counter(step); position: absolute; left: 0; top: -2px; width: 30px; height: 30px; border-radius: 50%;
  background: var(--series-1); color: #fff; display: grid; place-items: center; font-weight: 700; font-size: 14px; }
code { background: var(--wash); padding: 1px 5px; border-radius: 4px; font-size: 13px; }

table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 8px 0; border-bottom: 1px solid var(--grid); text-align: left; font-weight: 400; }
th { color: var(--text-secondary); }
td { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.method { color: var(--text-muted); font-size: 13px; margin-top: 20px; }
.credit { margin-top: 28px; padding-top: 14px; border-top: 1px solid var(--grid); color: var(--text-muted); font-size: 12px; text-align: center; }
.method h2 { color: var(--text-primary); font-size: 14px; }
.method a { color: var(--series-1); }
#tip { position: fixed; pointer-events: none; background: var(--surface); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; font-size: 13px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.12); max-width: 280px; display: none; z-index: 10; }
@media (max-width: 480px) { .grid-2 { grid-template-columns: 1fr; } .cell-meter span.bar { display: none; }
  .tabs button { padding: 10px 10px; } .brand { align-items: flex-start; text-align: left; } }
@media print {
  body { background: #fff; } .card, .hero { break-inside: avoid; box-shadow: none; }
  .no-print, .tabs { display: none !important; }
  [role="tabpanel"] { display: block !important; }
  .hero { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
</head>
<body>
<main>
  <header>
    __CLIENT_LOGO__
    <div class="title">
      <h1>__CLIENT__ · Microsoft 365 Copilot business case</h1>
      <p class="sub">__SUBTITLE__</p>
      <div class="logo-tools no-print">
        <label class="btn btn-sm"><input type="file" id="logo-file" accept="image/png,image/jpeg,image/svg+xml,image/gif,image/webp" hidden>Upload customer logo</label>
        <label class="btn btn-sm"><input type="file" id="partner-file" accept="image/png,image/jpeg,image/svg+xml,image/gif,image/webp" hidden>Upload partner logo</label>
        <button type="button" class="btn btn-sm" id="save-html" hidden>Save dashboard with these logos</button>
        <span class="logo-msg" id="logo-msg" role="status"></span>
      </div>
    </div>
    __BRAND__
  </header>

  <noscript><p class="card">Turn on JavaScript to see the interactive dashboard.</p></noscript>

  <nav class="tabs" role="tablist" aria-label="Dashboard sections">
    <button type="button" role="tab" id="tab-btn-roi" aria-controls="tab-roi" aria-selected="true">Business case</button>
    <button type="button" role="tab" id="tab-btn-usage" aria-controls="tab-usage" aria-selected="false">Usage &amp; adoption<span class="badge" id="usage-badge" hidden>Live data</span></button>
    <button type="button" role="tab" id="tab-btn-method" aria-controls="tab-method" aria-selected="false">Method &amp; sources</button>
  </nav>

  <div role="tabpanel" id="tab-roi" aria-labelledby="tab-btn-roi">
  <div class="notice" id="prefill-note" hidden></div>

  <section class="hero" aria-label="Headline results">
    <div>
      <div class="eyebrow" id="hero-label"></div>
      <div class="big" id="hero-value"></div>
      <div class="hero-sub" id="hero-sub"></div>
      <div class="pills">
        <div class="pill"><div class="pv" id="p-roi"></div><div class="pl" id="p-roi-l"></div></div>
        <div class="pill"><div class="pv" id="p-payback"></div><div class="pl">Payback</div></div>
        <div class="pill"><div class="pv" id="p-hours"></div><div class="pl">Assisted hours a year</div></div>
      </div>
    </div>
    <div class="gauge-wrap">
      <div id="gauge"></div>
      <div class="gl">3-year ROI vs Forrester SMB projection (shaded range)</div>
    </div>
  </section>

  <details class="card controls no-print" open>
    <summary><span class="chev">▸</span> Adjust assumptions live</summary>
    <div class="toolbar">
      <div><span class="group-label">Scenario</span>
        <span class="seg" id="scenario">
          <button type="button" data-s="conservative">Conservative</button>
          <button type="button" data-s="base">Client estimate</button>
          <button type="button" data-s="optimistic">Optimistic</button>
        </span></div>
      <div><span class="group-label">Time horizon</span>
        <span class="seg" id="horizon">
          <button type="button" data-y="1">1 year</button>
          <button type="button" data-y="2">2 years</button>
          <button type="button" data-y="3">3 years</button>
        </span></div>
      <label class="check"><input type="checkbox" id="include-oneoff" checked> Include one-off costs</label>
      <div><span class="group-label">Currency</span>
        <span class="seg" id="currency">
          <button type="button" data-c="USD">USD</button>
          <button type="button" data-c="SGD">SGD</button>
        </span></div>
      <label class="check">1 USD = <input type="number" id="fx" min="0.5" max="3" step="0.0001" style="width:84px;padding:4px 6px;border:1px solid var(--border);border-radius:6px;background:var(--page);color:var(--text-primary);font:inherit;font-size:14px"> SGD</label>
      <span class="spacer"></span>
      <button type="button" class="btn" id="reset">Reset</button>
      <button type="button" class="btn" id="print">Save as PDF</button>
    </div>
    <div id="fields"></div>
    <p class="scenario-note" id="scenario-note"></p>
  </details>

  <section class="kpis">
    <div class="card kpi"><div class="icon i1"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></div>
      <div><div class="label">Assisted hours per active user</div><div class="value" id="k-peruser"></div><div class="note">Per week, Microsoft method</div></div></div>
    <div class="card kpi"><div class="icon i3"><svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14c2.8 0 5 2.2 5 5"/></svg></div>
      <div><div class="label">Capacity returned</div><div class="value" id="k-fte"></div><div class="note">Full-time equivalents a year (37.5-hour week)</div></div></div>
    <div class="card kpi"><div class="icon i2"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></svg></div>
      <div><div class="label">Break-even time saving</div><div class="value" id="k-breakeven"></div><div class="note">Per active user per week to cover licences</div></div></div>
    <div class="card kpi"><div class="icon i4"><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg></div>
      <div><div class="label">Working days returned</div><div class="value" id="k-days"></div><div class="note">Per year, 7.5-hour days</div></div></div>
  </section>

  <section class="grid-2">
    <div class="card">
      <h2>Where Copilot saves time</h2>
      <p class="card-sub">Assisted hours a year by Copilot capability, Microsoft Copilot Dashboard method</p>
      <div class="stack" id="stack" aria-hidden="true"></div>
      <div class="cats" id="cats"></div>
    </div>
    <div class="card">
      <h2>Adoption</h2>
      <p class="card-sub">Only active users create value, but every licence is paid for</p>
      <div class="people" id="people" role="img"></div>
      <div class="stat-line" id="adoption-line"></div>
      <div style="margin-top:14px" class="stat-line">Break-even vs assisted time per active user</div>
      <div class="meter"><div id="be-meter"></div></div>
      <div class="stat-line" id="be-line" style="font-size:13px"></div>
    </div>
  </section>

  <section class="grid-2">
    <div class="card chart">
      <h2>From potential to realised value</h2>
      <p class="card-sub" id="bars-sub"></p>
      <div id="bars"></div>
    </div>
    <div class="card chart">
      <h2>Cumulative value vs cost</h2>
      <p class="card-sub" id="cum-sub"></p>
      <div class="legend" id="legend">
        <button type="button" data-series="value" aria-pressed="true"><span class="swatch" style="background:var(--series-1)"></span>Realised value</button>
        <button type="button" data-series="cost" aria-pressed="true"><span class="swatch" style="background:var(--series-2)"></span>Cost</button>
      </div>
      <div id="cum"></div>
    </div>
  </section>

  <section class="grid-2">
    <div class="card"><h2>Assumptions</h2><table id="t-assumptions"></table></div>
    <div class="card"><h2 id="t-results-title"></h2><table id="t-results"></table></div>
  </section>

  </div><!-- /tab-roi -->

  <div role="tabpanel" id="tab-usage" aria-labelledby="tab-btn-usage" hidden>
    <div id="usage-empty" hidden>
      <div class="card">
        <h2>Add the client's real Copilot usage</h2>
        <p class="card-sub">This tab fills in when the dashboard is created from a Microsoft Copilot Dashboard data export.</p>
        <ol class="steps">
          <li>Open the <strong>Microsoft Copilot Dashboard</strong> in Viva Insights (someone with global access, such as a Microsoft 365 Global Administrator).</li>
          <li>Select <strong>Export data</strong>, then <strong>Export by week</strong> (6 months, includes meeting hours).</li>
          <li>Save the CSV and ask the assistant: <em>"Create a usage dashboard for this client from C:\...\export.csv"</em>.</li>
        </ol>
        <p class="card-sub" style="margin:0">Needs at least 50 Copilot or Viva Insights licences in the tenant.
        <a href="https://learn.microsoft.com/viva/insights/org-team-insights/export-copilot-metrics" style="color:var(--series-1)">Microsoft's export guide</a></p>
      </div>
    </div>
    <div id="usage-content" hidden>
      <div class="filters">
        <label>Organisation <select id="f-org"></select></label>
        <label>Job function <select id="f-fn"></select></label>
        <label>Period <select id="f-period">
          <option value="4">Last 4 weeks</option><option value="12">Last 12 weeks</option><option value="0" selected>All weeks</option>
        </select></label>
        <span class="card-sub" style="margin:0" id="usage-source"></span>
      </div>
      <section class="kpis" id="usage-kpis"></section>
      <section class="grid-2">
        <div class="card chart"><h2>Active Copilot users per week</h2><p class="card-sub">Licensed users with any Copilot activity</p><div id="u-active"></div></div>
        <div class="card chart"><h2>Copilot assisted hours per week</h2><p class="card-sub">Microsoft method, calculated from the export</p><div id="u-hours"></div></div>
      </section>
      <section class="grid-2">
        <div class="card chart"><h2>Copilot actions by app</h2><p class="card-sub" id="u-apps-sub"></p><div id="u-apps"></div></div>
        <div class="card"><h2>Where the assisted hours came from</h2><p class="card-sub">Selected period, by Copilot capability</p>
          <div class="stack" id="u-stack" aria-hidden="true"></div><div class="cats" id="u-cats"></div></div>
      </section>
      <section class="card" style="margin-bottom:16px">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;align-items:center">
          <div><h2>Adoption by group</h2><p class="card-sub" style="margin:0">Latest week in the selected period</p></div>
          <span class="seg" id="u-groupby"><button type="button" data-g="org" aria-pressed="true">Organisation</button><button type="button" data-g="fn" aria-pressed="false">Job function</button></span>
        </div>
        <div style="overflow-x:auto;margin-top:12px"><table id="u-groups"></table></div>
      </section>
      <p class="method" id="usage-quality"></p>
    </div>
  </div><!-- /tab-usage -->

  <div role="tabpanel" id="tab-method" aria-labelledby="tab-btn-method" hidden>
  <div class="card method" style="margin-top:0">
    <h2>Method and sources</h2>
    <p><strong>Copilot assisted hours</strong> follow Microsoft's published method in the
    <a href="https://learn.microsoft.com/viva/insights/org-team-insights/copilot-dashboard#impact">Microsoft Copilot Dashboard (Viva Insights)</a>:
    meeting hours summarised or recapped, plus 6 minutes per search or summary action, plus 6 minutes per creation action.
    The 6-minute factors come from
    <a href="https://www.microsoft.com/en-us/worklab/work-trend-index/copilots-earliest-users-teach-us-about-generative-ai-at-work">Microsoft research with knowledge workers</a>.
    <strong>Assisted value</strong> = assisted hours × hourly rate (Microsoft's default is $72, from US Bureau of Labor Statistics data).
    Microsoft describes assisted hours as a broad, directional estimate.</p>
    <p>This business case adds: weekly activity × __WEEKS__ working weeks, licence costs for all licensed users, one-off rollout costs,
    ROI, payback and an optional realisation rate (a conservatism factor that is not part of Microsoft's method).
    Benchmark: <a href="https://www.microsoft.com/en-us/microsoft-365/blog/2024/10/17/microsoft-365-copilot-drove-up-to-353-roi-for-small-and-medium-businesses-new-study/">Forrester's projected Total Economic Impact of Microsoft 365 Copilot for SMB</a>
    (commissioned by Microsoft): 3-year ROI of 132% to 353%. Validate activity estimates with the client's Copilot Dashboard data or a pilot.</p>
    <p><strong>Usage data</strong> comes from the
    <a href="https://learn.microsoft.com/viva/insights/org-team-insights/export-copilot-metrics">Copilot Dashboard data export</a>
    (one row per person per week, anonymised IDs). The export does not include assisted hours, so they are calculated here with the formula above.
    Users count as licensed when "Total Copilot enabled days" is above zero, and active when "Total Copilot active days" is above zero.</p>
  </div>
  </div><!-- /tab-method -->

  <footer class="credit">Copilot ROI dashboard created by __AUTHOR__ · © __YEAR__ __AUTHOR__. All rights reserved.</footer>
</main>
<div id="tip" role="tooltip"></div>

<script>
(function () {
  "use strict";
  // A clean copy of the page, taken before anything is drawn, used by "Save dashboard".
  const PRISTINE = "<!doctype html>\n" + document.documentElement.outerHTML;
  const CFG = __CONFIG_JSON__;
  const BASE = CFG.base, WEEKS = CFG.weeks, MPA = CFG.minutesPerAction, BM = CFG.benchmark;
  // Money inputs in BASE are USD. state.inputs holds them in the currency on screen.
  const MONEY = ["hourly", "licence", "oneOff"];

  // ---- Inputs shown as sliders ------------------------------------------
  const GROUPS = [
    ["Copilot usage (per active user per week)", [
      { key: "meetings", label: "Meeting hours summarised or recapped", min: 0, max: Math.max(10, BASE.meetings * 2), step: 0.25 },
      { key: "search", label: "Search and summary actions", min: 0, max: Math.max(50, BASE.search * 2), step: 1 },
      { key: "creation", label: "Creation actions (drafts, rewrites, formulas)", min: 0, max: Math.max(50, BASE.creation * 2), step: 1 },
    ]],
    ["People and money", [
      { key: "users", label: "Licensed users", min: 1, max: Math.max(5000, BASE.users * 2), step: 1 },
      { key: "adoption", label: "Adoption rate (% of users active)", min: 5, max: 100, step: 5 },
      { key: "hourly", label: "Fully-loaded cost per hour", money: true, min: 1, max: Math.max(200, BASE.hourly * 2), step: 1 },
      { key: "licence", label: "Licence per user per month", money: true, min: 0, max: Math.max(100, BASE.licence * 2), step: 0.5 },
      { key: "oneOff", label: "One-off rollout costs", money: true, min: 0, max: Math.max(500000, BASE.oneOff * 2), step: 1000 },
      { key: "realisation", label: "Realisation rate (%) · optional, not in Microsoft's method", min: 5, max: 100, step: 5 },
    ]],
  ];
  const FIELDS = GROUPS.flatMap(g => g[1]);
  const round2 = v => Math.round(v * 100) / 100;
  const scale = (b, f) => ({ meetings: round2(b.meetings * f), search: Math.round(b.search * f), creation: Math.round(b.creation * f) });
  const SCENARIOS = {
    base: b => ({ ...b }),
    conservative: b => ({ ...b, ...scale(b, 0.75), adoption: 60, realisation: 50 }),
    optimistic: b => ({ ...b, ...scale(b, 1.25), adoption: 90, realisation: 100 }),
  };
  const SCENARIO_NOTES = {
    base: "Showing the client's own estimates.",
    conservative: "Conservative: 75% of the estimated Copilot activity, 60% adoption, 50% realisation.",
    optimistic: "Optimistic: 125% of the estimated Copilot activity, 90% adoption, 100% realisation.",
    custom: "Custom: assumptions changed by hand. Press Reset to go back to the client's estimates.",
  };

  const state = { inputs: {}, scenario: "base", years: 1, includeOneOff: true, show: { value: true, cost: true },
                  cur: CFG.currency, fx: CFG.fx };
  const rate = () => state.cur === "SGD" ? state.fx : 1;          // USD -> screen currency
  const CURRENCY_SYM = () => CFG.symbols[state.cur];
  function toScreen(usd) {                                         // copy of inputs with money in screen currency
    const o = { ...usd };
    MONEY.forEach(k => { o[k] = round2(usd[k] * rate()); });
    return o;
  }
  state.inputs = toScreen(BASE);

  // ---- The maths (mirrors calculate_roi in roi.py) -------------------------
  function calc(i, years, includeOneOff) {
    const adoption = i.adoption / 100, realisation = i.realisation / 100;
    const active = i.users * adoption, yearly = active * WEEKS, perAction = MPA / 60;
    const hMeet = i.meetings * yearly, hSearch = i.search * perAction * yearly, hCreate = i.creation * perAction * yearly;
    const hours = hMeet + hSearch + hCreate;                 // Copilot assisted hours a year
    const assistedValue = hours * i.hourly;                  // Copilot assisted value a year
    const realised = assistedValue * realisation;
    const licence = i.users * i.licence * 12;
    const oneOff = includeOneOff ? i.oneOff : 0;
    const value = realised * years, cost = licence * years + oneOff, net = value - cost;
    const cost3 = licence * 3 + oneOff;
    const monthlyNet = (realised - licence) / 12;
    const perHour = active * WEEKS * i.hourly * realisation;
    return {
      active, hMeet, hSearch, hCreate, hours, assistedValue, realisedYear: realised, licenceYear: licence, oneOff,
      perUserWeek: yearly > 0 ? hours / yearly : 0,
      potential: assistedValue / adoption * years, afterAdoption: assistedValue * years,
      value, cost, net, roi: cost > 0 ? net / cost * 100 : Infinity,
      roi3: cost3 > 0 ? (realised * 3 - cost3) / cost3 * 100 : Infinity,
      payback: monthlyNet > 0 ? oneOff / monthlyNet : null,
      breakEvenMin: perHour > 0 ? licence / perHour * 60 : Infinity,
      productiveHours: hours * realisation,
      fte: hours * realisation / CFG.fteHours,
    };
  }

  // ---- Formatting ---------------------------------------------------------
  const nf = v => Math.round(v).toLocaleString("en-GB");
  const money = v => (v < 0 ? "-" : "") + CURRENCY_SYM() + nf(Math.abs(v));
  function compact(v) {
    const sign = v < 0 ? "-" : "", a = Math.abs(v);
    for (const [size, suf] of [[1e9, "B"], [1e6, "M"], [1e3, "K"]]) {
      if (a >= size) return sign + CURRENCY_SYM() + (a / size).toFixed(1).replace(/\.0$/, "") + suf;
    }
    return sign + CURRENCY_SYM() + nf(a);
  }
  function niceTicks(max, count = 4) {
    if (max <= 0) return [0, 1];
    const raw = max / count, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw);
    const ticks = [];
    for (let t = 0; t <= max + step * 0.999; t += step) ticks.push(t);
    return ticks;
  }
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pct = v => isFinite(v) ? nf(v) + "%" : "n/a";
  const paybackText = p => p === null ? "Not reached" : p < 1 ? "< 1 month" : p.toFixed(1) + " months";

  // ---- Controls -----------------------------------------------------------
  document.getElementById("fields").innerHTML = GROUPS.map(([title, fields]) =>
    `<div class="fieldset-title">${esc(title)}</div><div class="fields">` + fields.map(f => `
      <div class="field">
        <label for="n-${f.key}">${esc(f.label)}${f.money ? ' (<span class="cur-sym"></span>)' : ""}</label>
        <div class="row">
          <input type="range" id="r-${f.key}" min="${f.min}" max="${f.max}" step="${f.step}" aria-label="${esc(f.label)}">
          <input type="number" id="n-${f.key}" min="${f.min}" max="${f.max}" step="${f.money ? "any" : f.step}">
        </div>
      </div>`).join("") + `</div>`).join("");

  FIELDS.forEach(f => {
    const range = document.getElementById("r-" + f.key), num = document.getElementById("n-" + f.key);
    const update = (v, from) => {
      if (v === "" || isNaN(+v)) return;
      const k = f.money ? rate() : 1;
      const n = Math.min(Math.max(+v, f.min * k), f.max * k);
      state.inputs[f.key] = n; state.scenario = "custom";
      if (from !== range) range.value = n;
      if (from !== num) num.value = n;
      render();
    };
    range.addEventListener("input", () => update(range.value, range));
    num.addEventListener("input", () => update(num.value, num));
  });
  function syncFields() {
    document.querySelectorAll(".cur-sym").forEach(el => { el.textContent = CURRENCY_SYM(); });
    document.getElementById("fx").value = state.fx;
    FIELDS.forEach(f => {
      if (f.money) {                                                 // slider range follows the currency
        const k = rate(), r = document.getElementById("r-" + f.key);
        r.min = Math.round(f.min * k); r.max = Math.round(f.max * k);
        r.step = f.step; document.getElementById("n-" + f.key).max = r.max;
      }
      document.getElementById("r-" + f.key).value = state.inputs[f.key];
      document.getElementById("n-" + f.key).value = state.inputs[f.key];
    });
  }
  document.querySelectorAll("#scenario button").forEach(b => b.addEventListener("click", () => {
    state.scenario = b.dataset.s; state.inputs = toScreen(SCENARIOS[b.dataset.s](BASE)); syncFields(); render();
  }));
  document.querySelectorAll("#horizon button").forEach(b => b.addEventListener("click", () => { state.years = +b.dataset.y; render(); }));
  document.getElementById("include-oneoff").addEventListener("change", e => { state.includeOneOff = e.target.checked; render(); });
  document.querySelectorAll("#legend button").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.series, other = k === "value" ? "cost" : "value";
    if (state.show[k] && !state.show[other]) return;       // keep at least one line visible
    state.show[k] = !state.show[k]; render();
  }));
  document.getElementById("reset").addEventListener("click", () => {
    Object.assign(state, { scenario: "base", years: 1, includeOneOff: true, show: { value: true, cost: true } });
    state.inputs = toScreen(BASE);
    document.getElementById("include-oneoff").checked = true; syncFields(); render();
  });
  document.getElementById("print").addEventListener("click", () => window.print());

  // Switching currency converts the money inputs, so every number on the page stays equivalent.
  function convertInputs(fromRate, toRate) {
    MONEY.forEach(k => { state.inputs[k] = round2(state.inputs[k] / fromRate * toRate); });
  }
  document.querySelectorAll("#currency button").forEach(b => b.addEventListener("click", () => {
    if (b.dataset.c === state.cur) return;
    const before = rate(); state.cur = b.dataset.c; convertInputs(before, rate());
    syncFields(); render(); if (U) renderUsage();
  }));
  document.getElementById("fx").addEventListener("change", e => {
    const v = +e.target.value;
    if (!(v >= 0.5 && v <= 3)) { e.target.value = state.fx; return; }
    const before = rate(); state.fx = v; convertInputs(before, rate());
    syncFields(); render(); if (U) renderUsage();
  });

  // ---- Infographics -------------------------------------------------------
  function gaugeSvg(roi3) {
    const W = 340, H = 180, cx = 170, cy = 150, R = 110, SW = 18;
    const max = Math.max(400, Math.ceil((isFinite(roi3) ? roi3 : 0) / 100) * 100 + 50);
    const f = v => Math.min(Math.max(v / max, 0), 1);
    const pt = fr => { const a = Math.PI * (1 - fr); return [cx + R * Math.cos(a), cy - R * Math.sin(a)]; };
    const arc = (f1, f2) => { const [x1, y1] = pt(f1), [x2, y2] = pt(f2); return `M${x1.toFixed(1)},${y1.toFixed(1)} A${R},${R} 0 0 1 ${x2.toFixed(1)},${y2.toFixed(1)}`; };
    const v = isFinite(roi3) ? roi3 : max;
    // Benchmark labels sit just outside the arc so they never overlap it.
    const outside = fr => { const a = Math.PI * (1 - fr), rr = R + SW / 2 + 8; return [cx + rr * Math.cos(a), cy - rr * Math.sin(a), Math.cos(a)]; };
    const [lx, ly, lc] = outside(f(BM.low)), [hx, hy, hc] = outside(f(BM.high));
    const anchor = c => c < -0.2 ? "end" : c > 0.2 ? "start" : "middle";
    return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:340px;margin:0 auto" role="img" aria-label="3-year ROI ${pct(roi3)} against a benchmark range of ${BM.low}% to ${BM.high}%">
      <path d="${arc(0, 1)}" class="gauge-track" stroke-width="${SW}" fill="none" stroke-linecap="round"/>
      <path d="${arc(f(BM.low), f(BM.high))}" class="gauge-band" stroke-width="${SW}" fill="none"/>
      ${v > 0 ? `<path d="${arc(0, Math.max(f(v), 0.004))}" class="gauge-val" stroke-width="6" fill="none" stroke-linecap="round"/>` : ""}
      <circle cx="${pt(f(v))[0].toFixed(1)}" cy="${pt(f(v))[1].toFixed(1)}" r="9" fill="#fff" stroke="rgba(13,54,107,0.6)" stroke-width="3"/>
      <text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" class="gauge-small" text-anchor="${anchor(lc)}" dominant-baseline="middle">${BM.low}%</text>
      <text x="${hx.toFixed(1)}" y="${hy.toFixed(1)}" class="gauge-small" text-anchor="${anchor(hc)}" dominant-baseline="middle">${BM.high}%</text>
      <text x="${cx}" y="${cy - 18}" class="gauge-text" text-anchor="middle">${pct(roi3)}</text>
      <text x="${cx}" y="${cy + 4}" class="gauge-small" text-anchor="middle">3-year ROI</text>
    </svg>`;
  }

  const PERSON = '<svg viewBox="0 0 24 32"><circle cx="12" cy="7" r="6"/><path d="M2 31v-8a10 10 0 0 1 20 0v8z"/></svg>';

  function renderInfographics(r) {
    const i = state.inputs;
    // Time breakdown
    const cats = [
      ["Meeting summaries", r.hMeet, "var(--series-1)", i.meetings + " h a week, counted in full"],
      ["Search and summaries", r.hSearch, "var(--series-2)", i.search + " actions a week × " + MPA + " min"],
      ["Creation", r.hCreate, "var(--series-3)", i.creation + " actions a week × " + MPA + " min"],
    ];
    const total = r.hours || 1;
    document.getElementById("stack").innerHTML = cats.map(([n, h, c]) =>
      h > 0 ? `<div style="flex:${h} 1 0;background:${c}" title="${esc(n)}"></div>` : "").join("");
    document.getElementById("cats").innerHTML = cats.map(([n, h, c, note]) => `
      <div class="cat"><div class="ch"><span class="dot" style="background:${c}"></span>${esc(n)}</div>
        <div class="cv">${nf(h)} h</div><div class="cn">${Math.round(h / total * 100)}% · ${esc(note)}</div></div>`).join("");

    // Adoption pictogram (1 icon = 10% of licensed users)
    const on = Math.round(i.adoption / 10);
    const people = document.getElementById("people");
    people.innerHTML = Array.from({ length: 10 }, (_, k) => PERSON.replace("<svg", `<svg class="${k < on ? "person-on" : "person-off"}"`)).join("");
    people.setAttribute("aria-label", `${on} in 10 licensed users active`);
    document.getElementById("adoption-line").innerHTML =
      `<strong>${nf(r.active)}</strong> of ${nf(i.users)} licensed users active (${i.adoption}%)`;

    // Break-even meter: minutes needed vs minutes assisted per active user per week
    const assistedMin = r.perUserWeek * 60 * (i.realisation / 100);
    const share = assistedMin > 0 ? Math.min(r.breakEvenMin / assistedMin, 1) : 1;
    document.getElementById("be-meter").style.width = (share * 100).toFixed(1) + "%";
    document.getElementById("be-line").textContent = isFinite(r.breakEvenMin)
      ? `${nf(r.breakEvenMin)} min needed of ${nf(assistedMin)} min assisted a week` +
        (assistedMin >= r.breakEvenMin ? ` · ${(assistedMin / r.breakEvenMin).toFixed(1)}× the break-even point` : " · below break-even")
      : "Break-even not applicable";

    document.getElementById("gauge").innerHTML = gaugeSvg(r.roi3);
  }

  // ---- Charts -------------------------------------------------------------
  function barsSvg(r) {
    const rows = [
      ["Full potential", r.potential, "var(--muted-mark)", "If every licensed user were active"],
      ["Assisted value", r.afterAdoption, "var(--muted-mark)", "Microsoft method: assisted hours × hourly rate"],
      ["Realised value", r.value, "var(--series-1)", state.inputs.realisation + "% realisation rate applied"],
      ["Total cost", r.cost, "var(--series-2)", state.includeOneOff ? "Licences plus one-off rollout costs" : "Licences only"],
    ];
    const W = 480, LW = 124, VW = 64, RH = 56, BH = 24, PW = W - LW - VW;
    const top = Math.max(...rows.map(x => x[1])) || 1;
    let out = "";
    rows.forEach(([label, v, color, note], k) => {
      const y = k * RH + 8, w = Math.max(v / top * PW, 2), rx = Math.min(4, w / 2), x2 = LW + w;
      const d = `M${LW},${y} H${x2 - rx} Q${x2},${y} ${x2},${y + rx} V${y + BH - rx} Q${x2},${y + BH} ${x2 - rx},${y + BH} H${LW} Z`;
      out += `<g class="hit" data-tip="${esc(label + ": " + money(v) + " - " + note)}">
        <rect x="0" y="${y - 16}" width="${W}" height="${RH}" fill="transparent"/>
        <text x="${LW - 12}" y="${y + BH / 2}" class="axis-label" text-anchor="end" dominant-baseline="middle">${label}</text>
        <path d="${d}" fill="${color}"/>
        <text x="${x2 + 8}" y="${y + BH / 2}" class="value-label" dominant-baseline="middle">${compact(v)}</text></g>`;
    });
    const H = rows.length * RH + 8;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Bar chart of full potential, assisted value, realised value and total cost">
      <line x1="${LW}" y1="0" x2="${LW}" y2="${H - 8}" class="baseline"/>${out}</svg>`;
  }

  let cumPoints = [];
  function cumSvg(r) {
    const months = state.years * 12;
    cumPoints = [];
    for (let m = 0; m <= months; m++) cumPoints.push({ m, value: r.realisedYear / 12 * m, cost: r.oneOff + r.licenceYear / 12 * m });
    const W = 480, H = 300, L = 52, R = 64, T = 12, B = 32, PW = W - L - R, PH = H - T - B;
    const visible = cumPoints.flatMap(p => [state.show.value ? p.value : 0, state.show.cost ? p.cost : 0]);
    const ticks = niceTicks(Math.max(...visible)), yMax = ticks[ticks.length - 1];
    const x = m => L + m / months * PW, y = v => T + PH - v / yMax * PH;
    let s = ticks.map(t => `<line x1="${L}" y1="${y(t)}" x2="${L + PW}" y2="${y(t)}" class="${t === 0 ? "baseline" : "gridline"}"/>
      <text x="${L - 8}" y="${y(t)}" class="tick" text-anchor="end" dominant-baseline="middle">${compact(t)}</text>`).join("");
    const step = months <= 12 ? 3 : 12;
    for (let m = 0; m < months; m += step) s += `<text x="${x(m)}" y="${H - 10}" class="tick" text-anchor="middle">${m === 0 ? "Start" : "Month " + m}</text>`;
    const pts = k => cumPoints.map(p => `${x(p.m).toFixed(1)},${y(p[k]).toFixed(1)}`).join(" ");
    if (state.show.value) s += `<path d="M${x(0)},${y(0)} L${pts("value").replace(/ /g, " L")} L${x(months)},${y(0)} Z" fill="var(--series-1)" opacity="0.1"/>`;
    if (state.show.cost) s += `<polyline points="${pts("cost")}" class="series" stroke="var(--series-2)"/>`;
    if (state.show.value) s += `<polyline points="${pts("value")}" class="series" stroke="var(--series-1)"/>`;
    if (r.payback !== null && r.payback >= 0.5 && r.payback <= months && state.show.value && state.show.cost) {
      const px = x(r.payback), py = y(r.realisedYear / 12 * r.payback);
      s += `<line x1="${px}" y1="${T}" x2="${px}" y2="${T + PH}" class="gridline strong"/>
        <circle cx="${px}" cy="${py}" r="5" class="mdot" fill="var(--text-primary)"/>
        <text x="${px + 8}" y="${Math.min(py + 20, T + PH - 6)}" class="value-label">Payback · month ${r.payback.toFixed(1)}</text>`;
    }
    const end = cumPoints[cumPoints.length - 1];
    [["value", "var(--series-1)"], ["cost", "var(--series-2)"]].forEach(([k, c]) => {
      if (!state.show[k]) return;
      s += `<circle cx="${x(months)}" cy="${y(end[k])}" r="4" class="mdot" fill="${c}"/>
        <text x="${x(months) + 10}" y="${y(end[k])}" class="value-label" dominant-baseline="middle">${compact(end[k])}</text>`;
    });
    s += `<line id="crosshair" x1="0" x2="0" y1="${T}" y2="${T + PH}" class="crosshair"/>
      <rect id="cum-hit" x="${L}" y="${T}" width="${PW}" height="${PH}" fill="transparent"/>`;
    return `<svg id="cum-chart" viewBox="0 0 ${W} ${H}" data-l="${L}" data-pw="${PW}" data-months="${months}" role="img"
      aria-label="Line chart of cumulative realised value against cumulative cost">${s}</svg>`;
  }

  // ---- Tooltips -----------------------------------------------------------
  const tip = document.getElementById("tip");
  function showTip(html, e) {
    tip.innerHTML = html; tip.style.display = "block";
    tip.style.left = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8) + "px";
    tip.style.top = (e.clientY + 14) + "px";
  }
  const hideTip = () => { tip.style.display = "none"; };
  function wireTooltips() {
    document.querySelectorAll("#bars .hit").forEach(g => {
      g.addEventListener("mousemove", e => showTip(esc(g.dataset.tip), e));
      g.addEventListener("mouseleave", hideTip);
    });
    const svg = document.getElementById("cum-chart"), hit = document.getElementById("cum-hit"), cross = document.getElementById("crosshair");
    const L = +svg.dataset.l, PW = +svg.dataset.pw, months = +svg.dataset.months;
    hit.addEventListener("mousemove", e => {
      const p0 = svg.createSVGPoint(); p0.x = e.clientX; p0.y = e.clientY;
      const local = p0.matrixTransform(svg.getScreenCTM().inverse());
      const m = Math.max(0, Math.min(months, Math.round((local.x - L) / PW * months)));
      const p = cumPoints[m], cx = L + m / months * PW;
      cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.style.visibility = "visible";
      showTip(`<strong>${m === 0 ? "Start" : "Month " + m}</strong><br>Realised value: ${money(p.value)}<br>Cost: ${money(p.cost)}<br>Net: ${money(p.value - p.cost)}`, e);
    });
    hit.addEventListener("mouseleave", () => { cross.style.visibility = "hidden"; hideTip(); });
  }

  // ---- Render everything from state ---------------------------------------
  const setText = (id, t) => { document.getElementById(id).textContent = t; };
  const rows = items => items.map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");

  function render() {
    const i = state.inputs, r = calc(i, state.years, state.includeOneOff);
    document.querySelectorAll("#scenario button").forEach(b => b.setAttribute("aria-pressed", b.dataset.s === state.scenario));
    document.querySelectorAll("#horizon button").forEach(b => b.setAttribute("aria-pressed", +b.dataset.y === state.years));
    document.querySelectorAll("#currency button").forEach(b => b.setAttribute("aria-pressed", b.dataset.c === state.cur));
    document.querySelectorAll("#legend button").forEach(b => b.setAttribute("aria-pressed", state.show[b.dataset.series]));
    setText("scenario-note", SCENARIO_NOTES[state.scenario]);

    const period = state.years === 1 ? "Year-one" : state.years + "-year";
    setText("hero-label", period + " net benefit");
    const hv = document.getElementById("hero-value");
    hv.textContent = money(r.net); hv.className = "big" + (r.net < 0 ? " neg" : "");
    setText("hero-sub", money(r.value) + " realised value against " + money(r.cost) + " total cost");
    setText("p-roi", pct(r.roi)); setText("p-roi-l", period + " ROI");
    setText("p-payback", paybackText(r.payback));
    setText("p-hours", nf(r.hours));

    setText("k-peruser", r.perUserWeek.toFixed(1) + " h");
    setText("k-fte", r.fte.toFixed(1) + " FTE");
    setText("k-breakeven", isFinite(r.breakEvenMin) ? nf(r.breakEvenMin) + " min" : "n/a");
    setText("k-days", nf(r.productiveHours / 7.5));

    renderInfographics(r);
    setText("bars-sub", (state.years === 1 ? "Year one" : "Over " + state.years + " years") + ", " + state.cur);
    setText("cum-sub", "First " + state.years * 12 + " months, " + state.cur);
    document.getElementById("bars").innerHTML = barsSvg(r);
    document.getElementById("cum").innerHTML = cumSvg(r);
    wireTooltips();

    document.getElementById("t-assumptions").innerHTML = rows([
      ["Licensed users", nf(i.users)],
      ["Adoption rate", i.adoption + "%"],
      ["Meeting hours summarised per active user per week", String(i.meetings)],
      ["Search and summary actions per active user per week", String(i.search)],
      ["Creation actions per active user per week", String(i.creation)],
      ["Minutes assisted per action (Microsoft)", String(MPA)],
      ["Fully-loaded cost per hour", money(i.hourly)],
      ["Licence cost per user per month", CURRENCY_SYM() + i.licence.toLocaleString("en-GB", { maximumFractionDigits: 2 })],
      ["One-off rollout costs", state.includeOneOff ? money(i.oneOff) : "Excluded"],
      ["Realisation rate (optional)", i.realisation + "%"],
      ["Working weeks per year", String(WEEKS)],
      ["Currency", state.cur + (state.cur === "SGD" ? " (1 USD = " + state.fx + " SGD)" : "")],
    ]);
    setText("t-results-title", period + " results");
    document.getElementById("t-results").innerHTML = rows([
      ["Copilot assisted hours a year", nf(r.hours)],
      ["Copilot assisted value a year", money(r.assistedValue)],
      ["Realised value", money(r.value)],
      ["Licence cost", money(r.licenceYear * state.years)],
      ["Total cost", money(r.cost)],
      ["Net benefit", money(r.net)],
      ["ROI", pct(r.roi)],
      ["3-year ROI (benchmark " + BM.low + "–" + BM.high + "%)", pct(r.roi3)],
    ]);
  }

  // ---- Tabs ---------------------------------------------------------------
  const TABS = ["roi", "usage", "method"];
  function showTab(name) {
    TABS.forEach(t => {
      document.getElementById("tab-btn-" + t).setAttribute("aria-selected", t === name);
      document.getElementById("tab-" + t).hidden = t !== name;
    });
    hideTip();
    if (name === "usage") renderUsage();
  }
  TABS.forEach(t => document.getElementById("tab-btn-" + t).addEventListener("click", () => showTab(t)));
  document.querySelector(".tabs").addEventListener("keydown", e => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const cur = TABS.findIndex(t => document.getElementById("tab-btn-" + t).getAttribute("aria-selected") === "true");
    const next = TABS[(cur + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    showTab(next); document.getElementById("tab-btn-" + next).focus();
  });

  // ---- Usage & adoption tab (from a Copilot Dashboard export) -------------
  const U = CFG.usage;
  const APP_NAMES = ["Teams", "Outlook", "Word", "Excel", "PowerPoint", "Copilot Chat", "Copilot app", "OneNote", "Edge"];
  const ustate = { org: "", fn: "", period: 0, groupBy: "org" };

  function columnsSvg(points, fmt, label) {
    // points: [{label, v}] - single series, one hue, rounded tops.
    const W = 480, H = 240, L = 52, R = 8, T = 16, B = 30, PW = W - L - R, PH = H - T - B;
    const ticks = niceTicks(Math.max(...points.map(p => p.v), 1)), yMax = ticks[ticks.length - 1];
    const n = points.length, band = PW / n, bw = Math.min(24, band * 0.7);
    const y = v => T + PH - v / yMax * PH;
    let s = ticks.map(t => `<line x1="${L}" y1="${y(t)}" x2="${L + PW}" y2="${y(t)}" class="${t === 0 ? "baseline" : "gridline"}"/>
      <text x="${L - 8}" y="${y(t)}" class="tick" text-anchor="end" dominant-baseline="middle">${fmt(t)}</text>`).join("");
    const every = Math.ceil(n / 6);
    points.forEach((p, k) => {
      const x = L + band * k + (band - bw) / 2, h = Math.max(PH - (y(p.v) - T), p.v > 0 ? 2 : 0), top = T + PH - h, rx = Math.min(4, bw / 2, h);
      const d = h > 0 ? `M${x},${T + PH} V${top + rx} Q${x},${top} ${x + rx},${top} H${x + bw - rx} Q${x + bw},${top} ${x + bw},${top + rx} V${T + PH} Z` : "";
      s += `<g class="hit" data-tip="${esc(p.label + ": " + fmt(p.v) + " " + label)}"><rect x="${L + band * k}" y="${T}" width="${band}" height="${PH}" fill="transparent"/>
        <path d="${d}" fill="var(--series-1)"/></g>`;
      if (k % every === 0) s += `<text x="${x + bw / 2}" y="${H - 8}" class="tick" text-anchor="middle">${esc(p.label)}</text>`;
    });
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Column chart of ${esc(label)} per week">${s}</svg>`;
  }

  function hbarsSvg(items, fmt) {
    const W = 480, LW = 104, VW = 56, RH = 32, BH = 18, PW = W - LW - VW;
    const top = Math.max(...items.map(i => i[1]), 1);
    let out = "";
    items.forEach(([label, v], k) => {
      const y = k * RH + 4, w = Math.max(v / top * PW, v > 0 ? 2 : 0), rx = Math.min(4, w / 2), x2 = LW + w;
      const d = w > 0 ? `M${LW},${y} H${x2 - rx} Q${x2},${y} ${x2},${y + rx} V${y + BH - rx} Q${x2},${y + BH} ${x2 - rx},${y + BH} H${LW} Z` : "";
      out += `<g class="hit" data-tip="${esc(label + ": " + fmt(v) + " actions")}"><rect x="0" y="${y - 7}" width="${W}" height="${RH}" fill="transparent"/>
        <text x="${LW - 10}" y="${y + BH / 2}" class="axis-label" text-anchor="end" dominant-baseline="middle">${esc(label)}</text>
        <path d="${d}" fill="var(--series-1)"/>
        <text x="${x2 + 8}" y="${y + BH / 2}" class="value-label" dominant-baseline="middle">${fmt(v)}</text></g>`;
    });
    const H = items.length * RH + 4;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Bar chart of Copilot actions by app">
      <line x1="${LW}" y1="0" x2="${LW}" y2="${H - 4}" class="baseline"/>${out}</svg>`;
  }

  const shortDate = iso => { const d = new Date(iso + "T00:00:00"); return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }); };
  const compactNum = v => v >= 1e6 ? (v / 1e6).toFixed(1).replace(/\.0$/, "") + "M" : v >= 1e3 ? (v / 1e3).toFixed(1).replace(/\.0$/, "") + "K" : nf(v);

  function initUsage() {
    if (!U) { document.getElementById("usage-empty").hidden = false; return; }
    document.getElementById("usage-content").hidden = false;
    document.getElementById("usage-badge").hidden = false;
    const opt = (list, all) => `<option value="">${all}</option>` + list.map(v => `<option>${esc(v)}</option>`).join("");
    document.getElementById("f-org").innerHTML = opt(U.organizations, "All organisations");
    document.getElementById("f-fn").innerHTML = opt(U.functions, "All job functions");
    document.getElementById("f-org").addEventListener("change", e => { ustate.org = e.target.value; renderUsage(); });
    document.getElementById("f-fn").addEventListener("change", e => { ustate.fn = e.target.value; renderUsage(); });
    document.getElementById("f-period").addEventListener("change", e => { ustate.period = +e.target.value; renderUsage(); });
    document.querySelectorAll("#u-groupby button").forEach(b => b.addEventListener("click", () => { ustate.groupBy = b.dataset.g; renderUsage(); }));
    const w = U.weeks;
    document.getElementById("usage-source").textContent = `${U.source} · weeks of ${shortDate(w[0])} to ${shortDate(w[w.length - 1])}`;
    const q = [];
    if (U.missing_metrics.length) q.push(`${U.missing_metrics.length} expected metric columns were not in this export and count as zero: ${U.missing_metrics.join("; ")}.`);
    if (!U.has_meeting_hours) q.push("No meeting hours column (day-level exports don't include it), so meeting summaries aren't counted.");
    if (!U.has_person_id) q.push("No person ID column was found, so each row is treated as one person.");
    document.getElementById("usage-quality").textContent = q.join(" ");
    const r = U.roi_inputs, note = document.getElementById("prefill-note");
    note.hidden = false;
    note.innerHTML = `<strong>Pre-filled from real usage:</strong> licensed users, adoption and Copilot activity come from the client's Copilot Dashboard export: the average of the last ${r.weeks_used} weeks, projected over a full year. Cost, licence price and rollout costs are estimates. See the Usage &amp; adoption tab for the history.`;
  }

  function renderUsage() {
    if (!U) return;
    const weeksAll = U.weeks, weeks = ustate.period ? weeksAll.slice(-ustate.period) : weeksAll, wset = new Set(weeks);
    const rows = U.rows.filter(r => wset.has(r.w) && (!ustate.org || r.org === ustate.org) && (!ustate.fn || r.fn === ustate.fn));
    const g = k => rows.reduce((a, r) => a + (r[k] || 0), 0);
    const byWeek = weeks.map(w => {
      const rs = rows.filter(r => r.w === w), sum = k => rs.reduce((a, r) => a + (r[k] || 0), 0);
      return { w, lic: sum("lic"), act: sum("act"), ret: sum("ret"), chat: sum("chatUnlic"),
               hours: sum("meet") + (sum("search") + sum("create")) * MPA / 60 };
    });
    const last = byWeek[byWeek.length - 1] || { lic: 0, act: 0, ret: 0, chat: 0 };
    const hMeet = g("meet"), hSearch = g("search") * MPA / 60, hCreate = g("create") * MPA / 60, hours = hMeet + hSearch + hCreate;
    const hourly = state.inputs.hourly;
    const pctOf = (a, b) => b > 0 ? Math.round(a / b * 100) + "%" : "n/a";
    const tile = (icon, cls, label, value, note) => `<div class="card kpi"><div class="icon ${cls}">${icon}</div>
      <div><div class="label">${label}</div><div class="value">${value}</div><div class="note">${note}</div></div></div>`;
    const IC = {
      users: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14c2.8 0 5 2.2 5 5"/></svg>',
      bolt: '<svg viewBox="0 0 24 24"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
      clock: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
      coin: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M9 9h4.5a2 2 0 0 1 0 4H9v-4zm0 4h5"/></svg>',
    };
    document.getElementById("usage-kpis").innerHTML =
      tile(IC.users, "i1", "Active users (latest week)", `${nf(last.act)} <span style="font-size:16px;color:var(--text-secondary)">/ ${nf(last.lic)}</span>`, `${pctOf(last.act, last.lic)} of licensed users · ${pctOf(last.ret, last.lic)} returning (28 days)`) +
      tile(IC.bolt, "i2", "Copilot actions", compactNum(g("actions")), `${weeks.length} weeks · ${nf(last.act ? g("actions") / Math.max(g("act"), 1) : 0)} per active user per week`) +
      tile(IC.clock, "i3", "Copilot assisted hours", nf(hours), `${weeks.length} weeks, Microsoft method`) +
      tile(IC.coin, "i4", "Copilot assisted value", compact(hours * hourly), `At ${CURRENCY_SYM()}${hourly.toLocaleString("en-GB", { maximumFractionDigits: 2 })} an hour (set on the Business case tab)`);

    document.getElementById("u-active").innerHTML = columnsSvg(byWeek.map(b => ({ label: shortDate(b.w), v: b.act })), nf, "active users");
    document.getElementById("u-hours").innerHTML = columnsSvg(byWeek.map(b => ({ label: shortDate(b.w), v: b.hours })), nf, "assisted hours");

    const apps = APP_NAMES.map(a => [a, g("app_" + a)]).filter(a => a[1] > 0).sort((a, b) => b[1] - a[1]);
    document.getElementById("u-apps-sub").textContent = weeks.length + " weeks, all Copilot actions";
    document.getElementById("u-apps").innerHTML = apps.length ? hbarsSvg(apps, compactNum) : '<p class="card-sub">No app-level action columns in this export.</p>';

    const cats = [["Meeting summaries", hMeet, "var(--series-1)"], ["Search and summaries", hSearch, "var(--series-2)"], ["Creation", hCreate, "var(--series-3)"]];
    document.getElementById("u-stack").innerHTML = cats.map(([n, h, c]) => h > 0 ? `<div style="flex:${h} 1 0;background:${c}" title="${esc(n)}"></div>` : "").join("");
    document.getElementById("u-cats").innerHTML = cats.map(([n, h, c]) => `<div class="cat"><div class="ch"><span class="dot" style="background:${c}"></span>${esc(n)}</div>
      <div class="cv">${nf(h)} h</div><div class="cn">${hours ? Math.round(h / hours * 100) : 0}% of assisted hours</div></div>`).join("");

    // Adoption by group, latest week in the period
    document.querySelectorAll("#u-groupby button").forEach(b => b.setAttribute("aria-pressed", b.dataset.g === ustate.groupBy));
    const lastW = weeks[weeks.length - 1], groups = {};
    rows.filter(r => r.w === lastW).forEach(r => {
      const k = r[ustate.groupBy], x = groups[k] || (groups[k] = { lic: 0, act: 0, hours: 0 });
      x.lic += r.lic || 0; x.act += r.act || 0;
    });
    rows.forEach(r => { const x = groups[r[ustate.groupBy]]; if (x) x.hours += (r.meet || 0) + ((r.search || 0) + (r.create || 0)) * MPA / 60; });
    const list = Object.entries(groups).sort((a, b) => b[1].lic - a[1].lic);
    document.getElementById("u-groups").innerHTML =
      `<tr><th scope="col">${ustate.groupBy === "org" ? "Organisation" : "Job function"}</th><td style="color:var(--text-secondary);font-weight:400">Licensed</td>
       <td style="color:var(--text-secondary);font-weight:400">Active</td><td style="color:var(--text-secondary);font-weight:400">Adoption</td>
       <td style="color:var(--text-secondary);font-weight:400">Assisted hours</td></tr>` +
      list.map(([k, x]) => {
        const p = x.lic ? x.act / x.lic : 0;
        return `<tr><th scope="row">${esc(k)}</th><td>${nf(x.lic)}</td><td>${nf(x.act)}</td>
          <td><span class="cell-meter"><span class="bar"><i style="width:${(p * 100).toFixed(0)}%"></i></span>${Math.round(p * 100)}%</span></td><td>${nf(x.hours)}</td></tr>`;
      }).join("");

    document.querySelectorAll("#tab-usage .hit").forEach(el => {
      el.addEventListener("mousemove", e => showTip(esc(el.dataset.tip), e));
      el.addEventListener("mouseleave", hideTip);
    });
  }

  // ---- Logo uploads (stay in this browser until saved) --------------------
  const uploaded = {};                                   // slot id -> <img> HTML
  const logoMsg = document.getElementById("logo-msg");
  function wireUpload(inputId, slotId, cls, alt) {
    document.getElementById(inputId).addEventListener("change", e => {
      const file = e.target.files[0];
      if (!file) return;
      if (!/^image\/(png|jpeg|svg\+xml|gif|webp)$/.test(file.type)) { logoMsg.textContent = "Please choose a PNG, JPG, SVG, GIF or WebP image."; return; }
      if (file.size > 2 * 1024 * 1024) { logoMsg.textContent = "That image is over 2 MB. Please use a smaller logo."; return; }
      const reader = new FileReader();
      reader.onload = () => {
        uploaded[slotId] = `<img class="${cls}" src="${esc(reader.result)}" alt="${alt}">`;
        document.getElementById(slotId).innerHTML = uploaded[slotId];
        document.getElementById("save-html").hidden = false;
        logoMsg.textContent = alt + " added. Save the dashboard to keep it.";
      };
      reader.readAsDataURL(file);
    });
  }
  wireUpload("logo-file", "client-logo-slot", "logo", "Customer logo");
  wireUpload("partner-file", "partner-logo-slot", "partner-logo", "Partner logo");
  document.getElementById("save-html").addEventListener("click", () => {
    const doc = new DOMParser().parseFromString(PRISTINE, "text/html");
    Object.entries(uploaded).forEach(([slot, html]) => { doc.getElementById(slot).innerHTML = html; });
    const html = "<!doctype html>\n" + doc.documentElement.outerHTML;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    a.download = document.title.replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "_") + ".html";
    document.body.appendChild(a); a.click(); a.remove();
    logoMsg.textContent = "Saved. Send the downloaded file to the client.";
  });

  initUsage();
  syncFields();
  render();
  if (U) renderUsage();
})();
</script>
</body>
</html>
"""
