"""Copilot Consultant MCP server.

A beginner-friendly MCP server with tools a Microsoft Copilot consultant
uses in client conversations: tier recommendation, readiness checks,
use-case ideas, ROI estimates, an HTML ROI dashboard and Build-Along
session plans.

Files: server.py (MCP tools), consulting.py (tiers, readiness, use cases), roi.py (the maths),
dashboard.py (the HTML), deck.py (the PowerPoint), copilot_export.py (reads a Copilot Dashboard export),
graph_usage.py (downloads Copilot usage reports from Microsoft Graph).

Run locally for Claude Desktop:  python server.py
Run as a web service for Microsoft 365 (Copilot Studio, Cowork, declarative agents):
    python server.py --http            (Streamable HTTP at /mcp; see DEPLOYMENT.md)

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import argparse
import base64
import binascii
import datetime
import os
import secrets
import tempfile
from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

import graph_usage
from dashboard import build_dashboard
from consulting import (INDUSTRY_NOTES, TIERS, USE_CASES, Currency, Function, Industry, Tier,
                        pick_tier, score_readiness)
from copilot_export import load_copilot_export
from deck import build_deck
from roi import BENCHMARK, DEFAULT_SGD_PER_USD, WORKING_WEEKS, calculate_roi, from_usd, to_usd

AUTHOR = "Shenuka Fernando"

mcp = MCPServer(
    "copilot-consultant",
    title="Copilot Consultant",
    description=f"Copilot consulting tools and ROI dashboards. Created by {AUTHOR}.",
    version="1.0.0",
)

# Dashboards are saved next to this file, whatever folder the app starts us from.
OUTPUT_DIR = Path(__file__).parent / "output"


# ---------------------------------------------------------------------------
# Hosting: when running as a web service, generated files are served from
# /files/<name> with an unguessable name, and tools return a download link.
# ---------------------------------------------------------------------------

def public_base_url() -> str | None:
    """The server's public https address, from PUBLIC_BASE_URL or Azure Container Apps' own variables."""
    if os.environ.get("PUBLIC_BASE_URL"):
        return os.environ["PUBLIC_BASE_URL"].rstrip("/")
    name, suffix = os.environ.get("CONTAINER_APP_NAME"), os.environ.get("CONTAINER_APP_ENV_DNS_SUFFIX")
    return f"https://{name}.{suffix}" if name and suffix else None


HOSTED = False          # set to True by --http in main()


def output_path(stem: str, suffix: str) -> Path:
    """Where to save a generated file. Hosted files get a random prefix so links can't be guessed."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in stem).strip("_") or "client"
    if HOSTED:
        safe = f"{secrets.token_urlsafe(12)}_{safe}"
    return OUTPUT_DIR / f"{safe}{suffix}"


def where(path: Path) -> str:
    """Tell the user where the file is: a local path, or a download link when hosted."""
    base = public_base_url() if HOSTED else None
    if base:
        return f"download: {base}/files/{path.name}"
    return f"saved to: {path.resolve()}"


# A Copilot Dashboard export attached in Copilot Cowork arrives as base64 content.
ExportFile = Annotated[str, Field(
    default="",
    description="Copilot Cowork: the Copilot Dashboard export CSV attached in the conversation. "
                "Leave empty when you give copilot_export_csv as a file path.",
    json_schema_extra={"contentEncoding": "base64"})]


def materialise_export(path: str | None, content: str | None) -> str | None:
    """Return a CSV path, writing base64 content from Cowork to a temporary file if needed."""
    if path or not content:
        return path
    try:
        data = base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("The attached export couldn't be read. Attach the CSV from Copilot Dashboard > Export data.")
    tmp = Path(tempfile.mkdtemp()) / "copilot_export.csv"
    tmp.write_bytes(data)
    return str(tmp)


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


def creates_file(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, read_only_hint=False, destructive_hint=False, open_world_hint=False)

ASSETS_DIR = Path(__file__).parent / "assets"

# Default partner branding, shown as "Prepared by" on every dashboard unless
# create_roi_dashboard is given a different partner_name / partner_logo.
DEFAULT_PARTNER_NAME = "Shenuka INC"
DEFAULT_PARTNER_LOGO = ASSETS_DIR / "partners" / "shenuka-inc.png"

# Logo folders: drop files here named after the organisation, e.g. contoso.png.
LOGO_DIRS = {"customer": ASSETS_DIR / "customers", "partner": ASSETS_DIR / "partners"}
LOGO_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".gif", ".webp"}


def _simple(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def find_logo(kind: str, name: str) -> Path | None:
    """Find a logo in assets/customers or assets/partners whose file name matches a name.

    "Contoso Retail" matches contoso.png or contoso-retail.svg.
    """
    folder = LOGO_DIRS[kind]
    if not folder.is_dir() or not _simple(name):
        return None
    wanted = _simple(name)
    files = [f for f in folder.iterdir() if f.suffix.lower() in LOGO_SUFFIXES]
    for f in files:                                        # exact match first
        if _simple(f.stem) == wanted:
            return f
    for f in sorted(files, key=lambda f: -len(f.stem)):    # then the longest partial match
        stem = _simple(f.stem)
        if stem and (stem in wanted or wanted in stem):
            return f
    return None


def resolve_logo(kind: str, logo: str | None, name: str | None) -> str | None:
    """Work out which logo to use.

    logo can be a file path, an https:// URL, a name saved in the logo folder, or empty
    (then we look in the folder for the organisation's name).
    """
    if logo and (logo.startswith("https://") or Path(logo).expanduser().is_file()):
        return logo
    found = find_logo(kind, logo or name or "")
    if found:
        return str(found)
    if logo:
        raise ValueError(
            f"{kind.capitalize()} logo not found: {logo}. Give a file path, an https:// URL, or save the "
            f"logo in {LOGO_DIRS[kind]} named after the {kind} (e.g. contoso.png).")
    return None

# ---------------------------------------------------------------------------
# Reference data (edit these to match your own consulting playbook)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tools: the AI decides when to call these
# ---------------------------------------------------------------------------

@mcp.tool(annotations=READ_ONLY)
def recommend_tier(
    needs_code: bool,
    connects_to_business_systems: bool,
    multi_step_workflow: bool,
    team_has_developers: bool,
) -> str:
    """Recommend the right Copilot build tier (1, 2 or 3) for a client scenario.

    Use this when a client asks whether to use Agent Builder, Copilot Studio
    or Azure AI Foundry.

    Args:
        needs_code: The solution needs custom code, custom models or evaluations.
        connects_to_business_systems: The agent must call APIs or systems like CRM/ERP.
        multi_step_workflow: The agent must run a process with several steps or approvals.
        team_has_developers: The client team includes professional developers.
    """
    t = pick_tier(needs_code, connects_to_business_systems, multi_step_workflow, team_has_developers)
    note = f"\nNote: {t['note']}" if t["note"] else ""
    return (f"Recommended: {t['tier']} - {t['name']} ({t['approach']})\n"
            f"Why: {t['reason']}.\n"
            f"Typical audience: {t['audience']}{note}")


@mcp.tool(annotations=READ_ONLY)
def assess_readiness(
    has_copilot_licences: bool,
    data_governance_in_place: bool,
    sharepoint_permissions_reviewed: bool,
    executive_sponsor: bool,
    change_management_plan: bool,
) -> str:
    """Score a client's Copilot adoption readiness out of 100 and list the gaps.

    Use this during discovery calls to show where the client stands today.
    """
    r = score_readiness(has_copilot_licences=has_copilot_licences,
                        data_governance_in_place=data_governance_in_place,
                        sharepoint_permissions_reviewed=sharepoint_permissions_reviewed,
                        executive_sponsor=executive_sponsor,
                        change_management_plan=change_management_plan)
    lines = [f"Readiness score: {r['score']}/100 - {r['status']}"]
    if r["gaps"]:
        lines.append("Gaps to close:")
        lines += [f"  - {g['label']}" for g in r["gaps"]]
    return "\n".join(lines)


@mcp.tool(annotations=READ_ONLY)
def find_use_cases(industry: Industry, function: Function) -> str:
    """Suggest Copilot agent use cases for a client's industry and business function."""
    ideas = "\n".join(f"  {i}. {idea}" for i, idea in enumerate(USE_CASES[function], 1))
    return (f"Use cases for {function} in {industry}:\n{ideas}\n"
            f"Industry tip: {INDUSTRY_NOTES[industry]}")


def _both(amount: float, currency: str, sgd_per_usd: float) -> str:
    """Show an amount in USD and SGD, e.g. 'US$1,000 (S$1,280)'."""
    usd = to_usd(amount, currency, sgd_per_usd)
    sgd = from_usd(usd, "SGD", sgd_per_usd)
    sign = "-" if amount < 0 else ""
    return f"{sign}US${abs(usd):,.0f} ({sign}S${abs(sgd):,.0f})"


def _roi_or_error(**kwargs):
    try:
        return calculate_roi(**kwargs), None
    except ValueError as err:
        return None, f"Error: {err}"


@mcp.tool(annotations=READ_ONLY)
def estimate_roi(
    users: int,
    hourly_cost: float,
    licence_cost_per_user_per_month: float,
    meeting_hours_per_week: float,
    search_actions_per_week: float,
    creation_actions_per_week: float,
    adoption_rate: float = 1.0,
    realisation_rate: float = 1.0,
    one_off_costs: float = 0.0,
    currency: Currency = "USD",
    sgd_per_usd: float = DEFAULT_SGD_PER_USD,
) -> str:
    """Estimate Copilot ROI using Microsoft's "Copilot assisted hours" method. Shows USD and SGD.

    Before calling, make sure the user has given the hourly cost and licence price (and any rollout
    costs). If they haven't, ask for them; never assume or invent these values.

    Microsoft's method (Copilot Dashboard in Viva Insights): assisted hours =
    meeting hours summarised + 6 minutes per search/summary action + 6 minutes
    per creation action; assisted value = assisted hours x hourly rate.
    Use real activity numbers from the client's Copilot Dashboard where possible
    (see summarise_copilot_export), otherwise agree estimates with the client.
    Use the client's own licence price; do not assume one.

    Args:
        users: Number of licensed users.
        hourly_cost: Fully-loaded cost of one employee hour (Microsoft's default is $72).
        licence_cost_per_user_per_month: Licence cost per user per month.
        meeting_hours_per_week: Meeting hours summarised or recapped by Copilot, per active user per week.
        search_actions_per_week: Search and summary actions per active user per week (6 minutes each).
        creation_actions_per_week: Creation actions per active user per week (6 minutes each).
        adoption_rate: Share of licensed users who actively use Copilot (0-1).
        realisation_rate: Optional conservatism factor (0-1); not part of Microsoft's method. Keep 1.0 to match it.
        one_off_costs: Rollout costs such as training, governance work and partner fees.
        currency: Currency of hourly_cost, licence cost and one_off_costs: "USD" or "SGD".
        sgd_per_usd: Exchange rate, SGD per 1 USD. Update it to today's rate if needed.
    """
    if sgd_per_usd <= 0:
        return "Error: sgd_per_usd must be greater than zero."
    r, err = _roi_or_error(
        users=users, hourly_cost=hourly_cost, licence_cost_per_user_per_month=licence_cost_per_user_per_month,
        meeting_hours_per_week=meeting_hours_per_week, search_actions_per_week=search_actions_per_week,
        creation_actions_per_week=creation_actions_per_week, adoption_rate=adoption_rate,
        realisation_rate=realisation_rate, one_off_costs=one_off_costs)
    if err:
        return err

    if r.payback_months is None:
        payback = "not reached (monthly value does not cover licence cost)"
    elif r.payback_months < 1:
        payback = "under 1 month"
    else:
        payback = f"{r.payback_months:.1f} months"
    m = lambda v: _both(v, currency, sgd_per_usd)
    return (f"Copilot assisted hours a year: {r.assisted_hours:,.0f} "
            f"({r.assisted_hours_per_user_per_week:.1f} h per active user per week)\n"
            f"Copilot assisted value a year: {m(r.assisted_value)}\n"
            f"Realised value (after realisation rate): {m(r.realised_value)}\n"
            f"Total year-one cost: {m(r.total_cost)}\n"
            f"Net benefit year one: {m(r.net_benefit)}\n"
            f"ROI year one: {r.roi_pct:,.0f}% | 3-year ROI: {r.roi_3yr_pct:,.0f}% "
            f"(Forrester SMB projection {BENCHMARK['low']}-{BENCHMARK['high']}%)\n"
            f"Payback: {payback}\n"
            f"Break-even: each active user needs {r.break_even_minutes:.0f} assisted minutes a week\n"
            f"(Microsoft assisted-hours method, {WORKING_WEEKS} working weeks a year, "
            f"1 USD = {sgd_per_usd} SGD.)")


@mcp.tool(annotations=READ_ONLY)
def summarise_copilot_export(csv_path: str | None = None, copilot_export_file: ExportFile = "") -> str:
    """Summarise a Microsoft Copilot Dashboard data export (CSV) and calculate Copilot assisted hours.

    The client gets the file from Copilot Dashboard (Viva Insights) > Export data > Export by week.
    Returns real adoption and activity numbers that can be used in estimate_roi or create_roi_dashboard.

    Args:
        csv_path: Full path to the exported CSV file.
        copilot_export_file: In Copilot Cowork, the attached export CSV instead of a path.
    """
    try:
        csv_path = materialise_export(csv_path, copilot_export_file)
        if not csv_path:
            return "Error: give csv_path, or attach the Copilot Dashboard export CSV."
        u = load_copilot_export(csv_path)
    except ValueError as err:
        return f"Error: {err}"
    r = u["roi_inputs"]
    lines = [
        f"File: {u['source']} ({len(u['weeks'])} weeks, {u['weeks'][0]} to {u['weeks'][-1]})",
        f"Organisations: {len(u['organizations'])}, job functions: {len(u['functions'])}",
        f"Copilot assisted hours (whole export, Microsoft method): {u['assisted_hours_total']:,.0f}",
        f"Last {r['weeks_used']} weeks: {r['users']} licensed users, {r['adoption_rate']:.0%} active",
        f"Per active user per week: {r['meeting_hours_per_week']} meeting hours summarised, "
        f"{r['search_actions_per_week']} search/summary actions, {r['creation_actions_per_week']} creation actions",
        f"Matched {u['matched_metrics']} metric columns.",
    ]
    if u["missing_metrics"]:
        lines.append(f"Missing columns (counted as zero): {', '.join(u['missing_metrics'])}")
    return "\n".join(lines)


@mcp.tool(annotations=ToolAnnotations(title="Download Copilot usage from Microsoft Graph", read_only_hint=False,
                                      destructive_hint=False, open_world_hint=True))
def download_copilot_usage(period: graph_usage.Period = "D28", tenant_profile: str = "",
                           save_to: str = "") -> str:
    """Download the client's Microsoft 365 Copilot usage reports (v2) from Microsoft Graph as CSV files.

    Uses the Entra ID app registration set up in environment variables (see INSTALL.md); never ask the
    user for a secret in the chat. Saves three CSVs (user detail, summary, daily trend) to the Downloads
    folder and returns adoption, prompts and a prompt-based estimate of search/summary actions per week
    that can go into estimate_roi or create_roi_dashboard as search_actions_per_week. Graph doesn't
    include meeting hours or creation actions: ask the user for those, or use a Copilot Dashboard export.

    Args:
        period: D7, D28, D90 or D180 (the last 7, 28, 90 or 180 days).
        tenant_profile: Optional name of a client set up with its own variables, e.g. "contoso" for
            COPILOT_GRAPH_TENANT_ID_CONTOSO. Leave empty for the default COPILOT_GRAPH_* variables.
        save_to: Optional folder to save to (local only). Default: your Downloads folder.
    """
    try:
        cfg = graph_usage.settings(tenant_profile)
        token = graph_usage.get_token(cfg)
        reports = {name: graph_usage.fetch_report(name, period, token) for name in graph_usage.REPORTS}
    except graph_usage.GraphError as err:
        return f"Error: {err}"

    stamp = datetime.date.today().isoformat()
    label = tenant_profile or "tenant"
    folder = Path(save_to).expanduser() if save_to and not HOSTED else Path.home() / "Downloads"
    saved = []
    for name, text in reports.items():
        stem = f"copilot_usage_{label}_{name}_{period}_{stamp}"
        path = output_path(stem, ".csv") if HOSTED or not folder.is_dir() else folder / f"{stem}.csv"
        path.write_text(text, encoding="utf-8")
        saved.append(f"- {name.replace('_', ' ')}: {where(path)}")

    s = graph_usage.summarise(reports["user_detail"], reports["summary"], period)
    lines = [f"Microsoft 365 Copilot usage, last {s['period_days']} days (Microsoft Graph, report v2)",
             f"Licensed users: {s['enabled_users']:,}, active: {s['active_users'] or 0:,} ({s['adoption_rate']:.0%})"]
    if s["prompts"] is not None:
        lines.append(f"Prompts submitted: {s['prompts']:,.0f} "
                     f"({s['prompts_per_active_user_per_week']:.1f} per active user per week)")
        lines.append(f"Prompt-based assisted hours (6 min each, Microsoft method): {s['prompt_assisted_hours']:,.0f}")
    if "avg_active_days" in s:
        lines.append(f"Average active days per active user: {s['avg_active_days']:.1f}")
    if s["apps"]:
        lines.append("Active / enabled users by app:")
        lines += [f"  {a['app']}: {a['active']:,} / {a['enabled']:,}" for a in s["apps"]]
    lines += ["Files:", *saved,
              f"For ROI: users={s['enabled_users']}, adoption_rate={s['adoption_rate']:.2f}, "
              f"search_actions_per_week={s['prompts_per_active_user_per_week']:.1f}. "
              "Graph has no meeting hours or creation actions: ask the user for those estimates, "
              "or use a Copilot Dashboard export for the exact figures. Licensed users only."]
    return "\n".join(lines)


@mcp.tool(annotations=creates_file("Create ROI dashboard"))
def create_roi_dashboard(
    client_name: str,
    hourly_cost: float,
    licence_cost_per_user_per_month: float,
    copilot_export_csv: str | None = None,
    users: int | None = None,
    meeting_hours_per_week: float | None = None,
    search_actions_per_week: float | None = None,
    creation_actions_per_week: float | None = None,
    adoption_rate: float | None = None,
    realisation_rate: float = 1.0,
    one_off_costs: float = 0.0,
    currency: Currency = "USD",
    sgd_per_usd: float = DEFAULT_SGD_PER_USD,
    logo: str | None = None,
    partner_name: str | None = None,
    partner_logo: str | None = None,
    prepared_by: str | None = None,
    copilot_export_file: ExportFile = "",
) -> str:
    """Create an interactive, multi-tab HTML Copilot ROI dashboard and return where it was saved.

    Before calling, make sure the user has given the hourly cost and licence price (and any rollout
    costs). If they haven't, ask for them; never assume or invent these values.

    Tabs: Business case (live ROI with sliders, scenarios and time horizon), Usage & adoption
    (real data when a Copilot Dashboard export is given, filterable by organisation and job
    function), and Method & sources. Uses Microsoft's "Copilot assisted hours" method.

    Either give copilot_export_csv (users, adoption and activity then come from real data),
    or give users and the three activity numbers yourself. Any value you give overrides the export.

    Args:
        client_name: The customer's name, shown in the title.
        hourly_cost: Fully-loaded cost of one employee hour (Microsoft's default is $72).
        licence_cost_per_user_per_month: Licence cost per user per month.
        copilot_export_csv: Path to a Copilot Dashboard export CSV (Export data > Export by week).
        users: Number of licensed users.
        meeting_hours_per_week: Meeting hours summarised or recapped by Copilot, per active user per week.
        search_actions_per_week: Search and summary actions per active user per week (6 minutes each).
        creation_actions_per_week: Creation actions per active user per week (6 minutes each).
        adoption_rate: Share of licensed users who actively use Copilot (0-1).
        realisation_rate: Optional conservatism factor (0-1); not part of Microsoft's method.
        one_off_costs: Rollout costs such as training, governance work and partner fees.
        currency: Currency of the money values given, "USD" or "SGD". The dashboard opens in it and
            has a switch to show everything in the other currency.
        sgd_per_usd: Exchange rate, SGD per 1 USD (editable on the dashboard too).
        logo: The customer's logo: a file path, an https:// URL (downloaded and embedded), or a
            name saved in assets/customers. Leave empty to look up the client's name there.
            Images attached in chat can't be passed to tools; the dashboard also has an
            "Upload customer logo" button for that.
        partner_name: The partner (consultancy) shown as "Prepared by". Defaults to Shenuka INC.
        partner_logo: The partner's logo, given the same ways as logo. If only partner_name is
            given, its logo is looked up in assets/partners; if none is found, the name is shown.
        prepared_by: Consultant name shown under the partner logo.
    """
    usage = None
    try:
        copilot_export_csv = materialise_export(copilot_export_csv, copilot_export_file)
    except ValueError as err:
        return f"Error: {err}"
    inputs = {"users": users, "meeting_hours_per_week": meeting_hours_per_week,
              "search_actions_per_week": search_actions_per_week,
              "creation_actions_per_week": creation_actions_per_week, "adoption_rate": adoption_rate}
    if copilot_export_csv:
        try:
            usage = load_copilot_export(copilot_export_csv)
        except ValueError as err:
            return f"Error: {err}"
        for key, value in usage["roi_inputs"].items():
            if key in inputs and inputs[key] is None:
                inputs[key] = value
    if inputs["adoption_rate"] is None:
        inputs["adoption_rate"] = 1.0
    missing = [k for k, v in inputs.items() if v is None]
    if missing:
        return ("Error: give copilot_export_csv, or these values: " + ", ".join(missing))

    r, err = _roi_or_error(hourly_cost=hourly_cost, licence_cost_per_user_per_month=licence_cost_per_user_per_month,
                           realisation_rate=realisation_rate, one_off_costs=one_off_costs, **inputs)
    if err:
        return err
    try:
        logo = resolve_logo("customer", logo, client_name)
        if partner_name is None and partner_logo is None:          # default branding
            partner_name = DEFAULT_PARTNER_NAME
            partner_logo = str(DEFAULT_PARTNER_LOGO) if DEFAULT_PARTNER_LOGO.is_file() else None
        else:
            partner_logo = resolve_logo("partner", partner_logo, partner_name)
        html = build_dashboard(r, client_name, currency, logo, prepared_by,
                               partner_name=partner_name, partner_logo=partner_logo, usage=usage,
                               sgd_per_usd=sgd_per_usd, author=AUTHOR)
    except ValueError as err:
        return f"Error: {err}"

    path = output_path(f"roi_dashboard_{client_name}", ".html")
    path.write_text(html, encoding="utf-8")
    source = f"real usage from {usage['source']}" if usage else "estimated activity"
    show = lambda l: Path(l).name if not l.startswith("https://") else l
    logo_note = (f"Customer logo: {show(logo)}." if logo else
                 "No customer logo found; use the dashboard's 'Upload customer logo' button "
                 f"or save one in {LOGO_DIRS['customer']}.")
    logo_note += (f" Partner: {partner_name or 'unnamed'}"
                  + (f" ({show(partner_logo)})." if partner_logo else " (name only, no logo)."))
    return (f"Dashboard {where(path)}\n"
            f"Based on {source}. Year-one net benefit {_both(r.net_benefit, currency, sgd_per_usd)}, ROI {r.roi_pct:,.0f}%, "
            f"3-year ROI {r.roi_3yr_pct:,.0f}%. Open the file in a browser to view it.\n{logo_note}")


TEMPLATES_DIR = ASSETS_DIR / "templates"


def resolve_template(template: str | None) -> str | None:
    """A template can be a file path or a name saved in assets/templates (e.g. "shenuka")."""
    if not template:
        return None
    if Path(template).expanduser().is_file():
        return template
    if TEMPLATES_DIR.is_dir():
        for f in TEMPLATES_DIR.iterdir():
            if f.suffix.lower() in (".pptx", ".potx") and _simple(template) in _simple(f.stem):
                return str(f)
    raise ValueError(f"Template not found: {template}. Give a .pptx/.potx path or save it in {TEMPLATES_DIR}.")


@mcp.tool(annotations=creates_file("Create client deck"))
def create_client_deck(
    client_name: str,
    currency: Currency = "USD",
    sgd_per_usd: float = DEFAULT_SGD_PER_USD,
    logo: str | None = None,
    partner_name: str | None = None,
    partner_logo: str | None = None,
    prepared_by: str | None = None,
    template: str | None = None,
    has_copilot_licences: bool | None = None,
    data_governance_in_place: bool | None = None,
    sharepoint_permissions_reviewed: bool | None = None,
    executive_sponsor: bool | None = None,
    change_management_plan: bool | None = None,
    needs_code: bool | None = None,
    connects_to_business_systems: bool | None = None,
    multi_step_workflow: bool | None = None,
    team_has_developers: bool | None = None,
    industry: Industry | None = None,
    function: Function | None = None,
    hourly_cost: float | None = None,
    licence_cost_per_user_per_month: float | None = None,
    copilot_export_csv: str | None = None,
    users: int | None = None,
    meeting_hours_per_week: float | None = None,
    search_actions_per_week: float | None = None,
    creation_actions_per_week: float | None = None,
    adoption_rate: float | None = None,
    realisation_rate: float = 1.0,
    one_off_costs: float = 0.0,
    copilot_export_file: ExportFile = "",
) -> str:
    """Create a client-facing PowerPoint deck (.pptx) from the consultant's results.

    Include whichever sections you have data for; each is added only when its inputs are complete:
    - Readiness + roadmap: all five readiness answers (same as assess_readiness).
    - Recommended approach: the four tier answers (same as recommend_tier) and/or industry + function.
    - Business case + value over time: hourly_cost and licence cost, plus copilot_export_csv or
      users and the three weekly activity numbers (same as estimate_roi).
      Ask the user for hourly cost, licence price and rollout costs; never assume them.
    - Usage and adoption by organisation: copilot_export_csv.
    - Build-Along plan: tier answers + industry + function.
    Charts are native and editable in PowerPoint (Edit Data), the agenda links to each section,
    and every slide has speaker notes. Works in Microsoft PowerPoint and PowerPoint for the web.

    Args:
        client_name: The customer's name.
        currency: "USD" or "SGD", the currency of the money values given.
        sgd_per_usd: Exchange rate, SGD per 1 USD.
        logo: Customer logo: file path, https URL, or a name in assets/customers (PNG/JPG for PowerPoint).
        partner_name: Partner shown as "Prepared by". Defaults to Shenuka INC.
        partner_logo: Partner logo, given the same ways; looked up in assets/partners.
        prepared_by: Consultant name.
        template: Optional widescreen PowerPoint template (.pptx/.potx) path, or a name saved in
            assets/templates. The deck uses its masters, layouts and theme colours.
        has_copilot_licences: Readiness: Copilot licences assigned.
        data_governance_in_place: Readiness: sensitivity labels and DLP in place.
        sharepoint_permissions_reviewed: Readiness: SharePoint oversharing reviewed.
        executive_sponsor: Readiness: executive sponsor identified.
        change_management_plan: Readiness: adoption and change plan in place.
        needs_code: Tier: needs custom code or models.
        connects_to_business_systems: Tier: must call APIs or systems like CRM/ERP.
        multi_step_workflow: Tier: runs a multi-step process.
        team_has_developers: Tier: client team has professional developers.
        industry: Client industry, for use cases and the Build-Along.
        function: Business function, for use cases and the Build-Along.
        hourly_cost: Fully-loaded cost of one employee hour.
        licence_cost_per_user_per_month: Licence cost per user per month.
        copilot_export_csv: Path to a Copilot Dashboard export (Export data > Export by week).
        users: Licensed users (if no export).
        meeting_hours_per_week: Meeting hours summarised per active user per week (if no export).
        search_actions_per_week: Search/summary actions per active user per week (if no export).
        creation_actions_per_week: Creation actions per active user per week (if no export).
        adoption_rate: Share of licensed users active (0-1).
        realisation_rate: Optional conservatism factor (0-1); not part of Microsoft's method.
        one_off_costs: Rollout costs such as training, governance work and partner fees.
    """
    included, skipped = [], []

    readiness_answers = dict(has_copilot_licences=has_copilot_licences,
                             data_governance_in_place=data_governance_in_place,
                             sharepoint_permissions_reviewed=sharepoint_permissions_reviewed,
                             executive_sponsor=executive_sponsor, change_management_plan=change_management_plan)
    readiness = None
    if all(v is not None for v in readiness_answers.values()):
        readiness = score_readiness(**readiness_answers)
    elif any(v is not None for v in readiness_answers.values()):
        skipped.append("readiness (all five answers are needed)")

    tier_answers = (needs_code, connects_to_business_systems, multi_step_workflow, team_has_developers)
    tier = pick_tier(*tier_answers) if all(v is not None for v in tier_answers) else None
    if tier is None and any(v is not None for v in tier_answers):
        skipped.append("tier (all four answers are needed)")

    usage = None
    try:
        copilot_export_csv = materialise_export(copilot_export_csv, copilot_export_file)
        if copilot_export_csv:
            usage = load_copilot_export(copilot_export_csv)
        roi = None
        if hourly_cost is not None and licence_cost_per_user_per_month is not None:
            inputs = {"users": users, "meeting_hours_per_week": meeting_hours_per_week,
                      "search_actions_per_week": search_actions_per_week,
                      "creation_actions_per_week": creation_actions_per_week, "adoption_rate": adoption_rate}
            if usage:
                for key, value in usage["roi_inputs"].items():
                    if key in inputs and inputs[key] is None:
                        inputs[key] = value
            if inputs["adoption_rate"] is None:
                inputs["adoption_rate"] = 1.0
            if all(v is not None for v in inputs.values()):
                roi = calculate_roi(hourly_cost=hourly_cost,
                                    licence_cost_per_user_per_month=licence_cost_per_user_per_month,
                                    realisation_rate=realisation_rate, one_off_costs=one_off_costs, **inputs)
            else:
                skipped.append("business case (give copilot_export_csv, or users and the three activity numbers)")
        elif users or copilot_export_csv:
            skipped.append("business case (hourly_cost and licence cost are needed)")

        logo = resolve_logo("customer", logo, client_name)
        if partner_name is None and partner_logo is None:
            partner_name = DEFAULT_PARTNER_NAME
            partner_logo = str(DEFAULT_PARTNER_LOGO) if DEFAULT_PARTNER_LOGO.is_file() else None
        else:
            partner_logo = resolve_logo("partner", partner_logo, partner_name)
        template = resolve_template(template)

        path = output_path(f"copilot_deck_{client_name}", ".pptx")
        result = build_deck(path, client_name, currency, sgd_per_usd, logo, partner_name, partner_logo,
                            prepared_by, readiness, tier, industry, function, roi, usage, template)
    except ValueError as err:
        return f"Error: {err}"
    except PermissionError:
        return "Error: the deck file is open in PowerPoint. Close it and try again."

    lines = [f"Deck {where(path)}",
             f"{result['count']} slides. Sections: {', '.join(result['slides'])}."]
    if skipped:
        lines.append("Left out: " + "; ".join(skipped) + ".")
    lines += result["warnings"]
    lines.append("Open it in PowerPoint. Select a chart and choose Edit Data to change the numbers.")
    return "\n".join(lines)


@mcp.tool(annotations=READ_ONLY)
def list_logos() -> str:
    """List the partner and customer logos saved in assets/partners and assets/customers."""
    lines = [f"Default partner: {DEFAULT_PARTNER_NAME} ({DEFAULT_PARTNER_LOGO.name})"]
    for kind, folder in LOGO_DIRS.items():
        names = sorted(f.name for f in folder.iterdir() if f.suffix.lower() in LOGO_SUFFIXES) if folder.is_dir() else []
        lines.append(f"{kind.capitalize()} logos in {folder}:")
        lines += [f"- {n}" for n in names] or ["- (none yet)"]
    return "\n".join(lines)


@mcp.tool(annotations=READ_ONLY)
def plan_build_along(tier: Tier, industry: Industry, function: Function) -> str:
    """Create an outline for an Agent Build-Along workshop session."""
    info = TIERS[tier]
    scenario = USE_CASES[function][0]
    steps = "\n".join(f"  {i}. {step}" for i, step in enumerate(info["flow"], 1))
    prereqs = "\n".join(f"  - {p}" for p in info["prerequisites"])
    return (f"Build-Along: {function} agent for {industry}\n"
            f"Platform: {info['name']} ({info['approach']}, {info['duration']})\n"
            f"Scenario: {scenario}\n\n"
            f"Session flow:\n{steps}\n\n"
            f"Prerequisites:\n{prereqs}\n\n"
            f"Facilitator tip: {INDUSTRY_NOTES[industry]}")


# ---------------------------------------------------------------------------
# Resources: read-only reference data the app or user can attach
# ---------------------------------------------------------------------------

@mcp.resource("consultant://tiers")
def tiers_overview() -> str:
    """Overview of the three Copilot build tiers."""
    return "\n\n".join(
        f"{tier}: {t['name']}\n  Audience: {t['audience']}\n"
        f"  Approach: {t['approach']} | Duration: {t['duration']}\n"
        f"  Flow: {' -> '.join(t['flow'])}"
        for tier, t in TIERS.items()
    )


@mcp.resource("consultant://copilot-export-guide")
def copilot_export_guide() -> str:
    """How to export real Copilot usage data from the Microsoft Copilot Dashboard."""
    return (
        "1. Open the Microsoft Copilot Dashboard in Viva Insights with global access "
        "(e.g. a Microsoft 365 Global Administrator or a delegate).\n"
        "2. Select Export data > Export by week (last 6 months, includes meeting hours).\n"
        "3. Save the CSV and pass its path to summarise_copilot_export or create_roi_dashboard.\n"
        "Requires at least 50 Copilot or Viva Insights licences. Personal identifiers are anonymised.\n"
        "Docs: https://learn.microsoft.com/viva/insights/org-team-insights/export-copilot-metrics"
    )


# ---------------------------------------------------------------------------
# Prompts: reusable templates the user picks
# ---------------------------------------------------------------------------

@mcp.prompt()
def discovery_call(client_name: str, industry: str) -> str:
    """Prepare for a Copilot discovery call with a client."""
    return (f"I have a Copilot discovery call with {client_name}, a {industry} "
            f"organisation. Suggest 8 discovery questions covering business goals, "
            f"data readiness, security and adoption. Then use the find_use_cases "
            f"tool to suggest relevant agent ideas.")


@mcp.custom_route("/files/{name}", methods=["GET"])
async def download(request):
    """Serve a generated dashboard or deck (hosted mode only)."""
    from starlette.responses import FileResponse, PlainTextResponse
    name = request.path_params["name"]
    path = OUTPUT_DIR / name
    if "/" in name or "\\" in name or name.startswith(".") or not path.is_file():
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path, filename=name.split("_", 1)[-1])


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import PlainTextResponse
    return PlainTextResponse("ok")


class ApiKeyMiddleware:
    """If MCP_API_KEY is set, calls to /mcp must send it as an x-api-key header or a Bearer token."""

    def __init__(self, app, key: str):
        self.app, self.key = app, key

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp"):
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            given = headers.get("x-api-key") or headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not secrets.compare_digest(given or "", self.key):
                from starlette.responses import PlainTextResponse
                await PlainTextResponse("Unauthorized", status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def main():
    global HOSTED
    parser = argparse.ArgumentParser(description="Copilot Consultant MCP server")
    parser.add_argument("--http", action="store_true",
                        help="Run as a web service (Streamable HTTP at /mcp) for Microsoft 365")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    if not args.http:
        mcp.run()                     # stdio, for Claude Desktop and other local clients
        return

    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings
    HOSTED = True
    allowed = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = TransportSecuritySettings(enable_dns_rebinding_protection=bool(allowed),
                                         allowed_hosts=allowed, allowed_origins=[])
    app = mcp.streamable_http_app(stateless_http=True, transport_security=security, host=args.host)
    key = os.environ.get("MCP_API_KEY")
    if key:
        app = ApiKeyMiddleware(app, key)
    print(f"Copilot Consultant MCP on http://{args.host}:{args.port}/mcp"
          f" (API key {'required' if key else 'not set'}; public URL {public_base_url() or 'not set'})")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
