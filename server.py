"""Copilot Consultant MCP server.

A beginner-friendly MCP server with tools a Microsoft Copilot consultant
uses in client conversations: tier recommendation, readiness checks,
use-case ideas, ROI estimates, an HTML ROI dashboard and Build-Along
session plans.

Files: server.py (MCP tools), roi.py (the maths), dashboard.py (the HTML),
copilot_export.py (reads a Copilot Dashboard data export).
No API keys or databases are needed.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

from dashboard import build_dashboard
from copilot_export import load_copilot_export
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

Industry = Literal[
    "Financial Services", "Healthcare", "Retail", "Manufacturing",
    "Public Sector", "Energy", "Professional Services",
]
Function = Literal[
    "Sales", "Marketing", "Finance", "HR", "Operations", "IT", "Customer Service",
]
Tier = Literal["Tier 1", "Tier 2", "Tier 3"]
Currency = Literal["USD", "SGD"]

TIERS = {
    "Tier 1": {
        "name": "Microsoft 365 Copilot Agent Builder",
        "audience": "Business makers, end users, departmental teams",
        "approach": "No-code",
        "duration": "60 min",
        "flow": ["Define", "Ground", "Refine", "Test & Share"],
        "prerequisites": [
            "Microsoft 365 Copilot licence (or Copilot Chat)",
            "Modern browser (Edge / Chrome)",
            "A workplace scenario in mind",
        ],
    },
    "Tier 2": {
        "name": "Copilot Studio",
        "audience": "Citizen developers, power users, ops teams",
        "approach": "Low-code",
        "duration": "90 min",
        "flow": ["Design", "Connect", "Author", "Publish"],
        "prerequisites": [
            "Copilot Studio access or trial environment",
            "Familiarity with Power Platform helpful (not required)",
            "A multi-step workflow or process in mind",
        ],
    },
    "Tier 3": {
        "name": "Azure AI Foundry",
        "audience": "Pro developers, architects, AI engineers",
        "approach": "Code-first",
        "duration": "180+ min",
        "flow": ["Provision", "Build", "Evaluate", "Deploy"],
        "prerequisites": [
            "Azure subscription with Azure AI Foundry access",
            "VS Code, plus Python or .NET familiarity",
            "Sample data or a use case ready to ground on",
        ],
    },
}

USE_CASES = {
    "Sales": [
        "Account research brief before customer meetings",
        "Proposal and RFP first-draft generator",
        "Pipeline summary and next-best-action from CRM data",
    ],
    "Marketing": [
        "Campaign brief and content variant generator",
        "Brand-voice checker grounded on style guides",
        "Campaign performance summariser",
    ],
    "Finance": [
        "Budget variance explainer",
        "Policy and expense Q&A agent",
        "Month-end close checklist assistant",
    ],
    "HR": [
        "Employee policy and benefits Q&A agent",
        "New-starter onboarding companion",
        "Job description and interview question drafter",
    ],
    "Operations": [
        "SOP and process Q&A agent",
        "Incident and shift handover summariser",
        "Supplier and inventory status assistant",
    ],
    "IT": [
        "IT service desk triage agent",
        "Knowledge-base article generator from resolved tickets",
        "Password reset and access request workflow",
    ],
    "Customer Service": [
        "Case summariser and suggested reply drafter",
        "Customer-facing FAQ agent on the website",
        "Escalation and sentiment triage assistant",
    ],
}

INDUSTRY_NOTES = {
    "Financial Services": "Highlight compliance, audit trails and data residency.",
    "Healthcare": "Keep patient data out of scope until governance is agreed.",
    "Retail": "Frontline and store-ops scenarios land well; think mobile and Teams.",
    "Manufacturing": "Ground on SOPs, safety docs and maintenance logs.",
    "Public Sector": "Emphasise accessibility, transparency and records management.",
    "Energy": "Focus on field operations, safety and regulatory reporting.",
    "Professional Services": "Knowledge reuse, proposals and time capture are quick wins.",
}


# ---------------------------------------------------------------------------
# Tools: the AI decides when to call these
# ---------------------------------------------------------------------------

@mcp.tool()
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
    if needs_code and team_has_developers:
        tier = "Tier 3"
        reason = "custom code and a developer team point to a code-first build"
    elif connects_to_business_systems or multi_step_workflow:
        tier = "Tier 2"
        reason = "system integrations or multi-step processes need Copilot Studio"
    else:
        tier = "Tier 1"
        reason = "a knowledge-grounded assistant can be built with no code"

    info = TIERS[tier]
    note = ""
    if needs_code and not team_has_developers:
        note = ("\nNote: the scenario needs code but the team has no developers. "
                "Start in Copilot Studio or bring in a partner for Tier 3.")
    return (f"Recommended: {tier} - {info['name']} ({info['approach']})\n"
            f"Why: {reason}.\n"
            f"Typical audience: {info['audience']}{note}")


@mcp.tool()
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
    checks = {
        "Copilot licences assigned": (has_copilot_licences, 20),
        "Data governance (labels, DLP) in place": (data_governance_in_place, 25),
        "SharePoint oversharing / permissions reviewed": (sharepoint_permissions_reviewed, 25),
        "Executive sponsor identified": (executive_sponsor, 15),
        "Change management / adoption plan": (change_management_plan, 15),
    }
    score = sum(weight for passed, weight in checks.values() if passed)
    gaps = [name for name, (passed, _) in checks.items() if not passed]

    if score >= 80:
        status = "Ready to scale"
    elif score >= 50:
        status = "Ready for a pilot"
    else:
        status = "Foundations needed first"

    lines = [f"Readiness score: {score}/100 - {status}"]
    if gaps:
        lines.append("Gaps to close:")
        lines += [f"  - {gap}" for gap in gaps]
    return "\n".join(lines)


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def summarise_copilot_export(csv_path: str) -> str:
    """Summarise a Microsoft Copilot Dashboard data export (CSV) and calculate Copilot assisted hours.

    The client gets the file from Copilot Dashboard (Viva Insights) > Export data > Export by week.
    Returns real adoption and activity numbers that can be used in estimate_roi or create_roi_dashboard.

    Args:
        csv_path: Full path to the exported CSV file.
    """
    try:
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


@mcp.tool()
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
) -> str:
    """Create an interactive, multi-tab HTML Copilot ROI dashboard and return where it was saved.

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

    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in client_name).strip("_") or "client"
    path = OUTPUT_DIR / f"roi_dashboard_{safe_name}.html"
    path.write_text(html, encoding="utf-8")
    source = f"real usage from {usage['source']}" if usage else "estimated activity"
    show = lambda l: Path(l).name if not l.startswith("https://") else l
    logo_note = (f"Customer logo: {show(logo)}." if logo else
                 "No customer logo found; use the dashboard's 'Upload customer logo' button "
                 f"or save one in {LOGO_DIRS['customer']}.")
    logo_note += (f" Partner: {partner_name or 'unnamed'}"
                  + (f" ({show(partner_logo)})." if partner_logo else " (name only, no logo)."))
    return (f"Dashboard saved to: {path.resolve()}\n"
            f"Based on {source}. Year-one net benefit {_both(r.net_benefit, currency, sgd_per_usd)}, ROI {r.roi_pct:,.0f}%, "
            f"3-year ROI {r.roi_3yr_pct:,.0f}%. Open the file in a browser to view it.\n{logo_note}")


@mcp.tool()
def list_logos() -> str:
    """List the partner and customer logos saved in assets/partners and assets/customers."""
    lines = [f"Default partner: {DEFAULT_PARTNER_NAME} ({DEFAULT_PARTNER_LOGO.name})"]
    for kind, folder in LOGO_DIRS.items():
        names = sorted(f.name for f in folder.iterdir() if f.suffix.lower() in LOGO_SUFFIXES) if folder.is_dir() else []
        lines.append(f"{kind.capitalize()} logos in {folder}:")
        lines += [f"- {n}" for n in names] or ["- (none yet)"]
    return "\n".join(lines)


@mcp.tool()
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


if __name__ == "__main__":
    mcp.run()
