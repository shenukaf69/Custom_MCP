"""Read a Microsoft Copilot Dashboard data export (CSV) and apply Microsoft's
"Copilot assisted hours" method to it.

How to get the file: Copilot Dashboard (Viva Insights) > Export data > Export by week.
Docs: https://learn.microsoft.com/viva/insights/org-team-insights/export-copilot-metrics

The export has one row per person per week (or per day) with anonymised IDs.
It does not include "Copilot assisted hours", so we calculate it here from the
same activity metrics Microsoft's dashboard uses:
https://learn.microsoft.com/viva/insights/org-team-insights/copilot-dashboard#impact

Columns are matched by their documented metric names (case, spaces and
punctuation are ignored). Missing columns are skipped and listed in the result,
so always check "missing_metrics" the first time you use a new export.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from roi import MINUTES_PER_ACTION

# Microsoft's three capability groups (Copilot Dashboard, "Copilot assisted hours").
MEETING_HOURS = ["Total meeting hours summarized or recapped by Copilot"]
SEARCH_AND_SUMMARY = [
    "Copilot Chat prompts submitted",
    "Summarize email thread actions taken using Copilot in Outlook",
    "Summarize Word document actions taken using Copilot in Word",
    "Summarize presentation actions taken using Copilot in PowerPoint",
    "Excel analysis actions taken using Copilot",
    "Summarize chat actions taken using Copilot in Teams",
    "Chat (Copilot in Word) prompts submitted",
    "Chat (Copilot in PowerPoint) prompts submitted",
    "Chat (Copilot in Excel) prompts submitted",
]
CREATION = [
    "Email coaching actions taken using Copilot",
    "Generate email draft actions taken using Copilot in Outlook",
    "Suggested reply email actions taken using Copilot",
    "Highlight rewrite email actions taken using Copilot",
    "Draft Word document actions taken using Copilot",
    "Coach Word document actions taken using Copilot",
    "Create presentation actions taken using Copilot",
    "Translate presentation actions taken using Copilot",
    "Rewrite presentation actions taken using Copilot",
    "Suggest presentation actions taken using Copilot",
    "Rewrite text actions taken using Copilot in Word",
    "Create Excel formula actions taken using Copilot",
    "Excel formatting actions taken using Copilot",
    "Excel chat helper actions taken using Copilot",
    "Excel formula by example actions taken using Copilot",
    "Excel clean data actions taken using Copilot",
    "Visualize as table actions taken using Copilot in Word",
    "Add content to presentation actions taken",
]
APPS = {
    "Teams": "Copilot actions taken in Teams",
    "Outlook": "Copilot actions taken in Outlook",
    "Word": "Copilot actions taken in Word",
    "Excel": "Copilot actions taken in Excel",
    "PowerPoint": "Copilot actions taken in PowerPoint",
    "Copilot Chat": "Copilot actions taken in Copilot Chat",
    "Copilot app": "Copilot actions taken in Microsoft Copilot app",
    "OneNote": "Copilot actions taken in OneNote",
    "Edge": "Copilot actions taken in Edge",
}
TOTAL_ACTIONS = "Total Copilot actions taken"
ACTIVE_DAYS = "Total Copilot active days"
ENABLED_DAYS = "Total Copilot enabled days"
UNLICENSED_CHAT = "Copilot Chat prompts submitted (without Copilot license)"
RETURNING_28 = "Returning Microsoft Copilot user (most recent and prior 28 days)"

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y")


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _num(value: str | None) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def _parse_date(value: str) -> date | None:
    text = str(value).strip()[:10]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _find(headers: list[str], *keywords: str) -> str | None:
    """First header whose normalised name contains any keyword."""
    for kw in keywords:
        for h in headers:
            if kw in _norm(h):
                return h
    return None


def load_copilot_export(csv_path: str, recent_weeks: int = 4) -> dict:
    """Summarise a Copilot Dashboard export. Raises ValueError if the file can't be used."""
    path = Path(csv_path).expanduser()
    if not path.is_file():
        raise ValueError(f"Export file not found: {csv_path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    if not rows:
        raise ValueError("The export file has no data rows.")

    by_norm = {_norm(h): h for h in headers}

    def col(metric: str) -> str | None:
        return by_norm.get(_norm(metric))

    wanted = MEETING_HOURS + SEARCH_AND_SUMMARY + CREATION + list(APPS.values()) + [
        TOTAL_ACTIONS, ACTIVE_DAYS, ENABLED_DAYS, UNLICENSED_CHAT, RETURNING_28]
    matched = [m for m in wanted if col(m)]
    missing = [m for m in wanted if not col(m)]
    if not any(col(m) for m in SEARCH_AND_SUMMARY + CREATION + MEETING_HOURS + [TOTAL_ACTIONS]):
        raise ValueError(
            "This doesn't look like a Copilot Dashboard export: none of the expected metric "
            "columns were found. Export it from Copilot Dashboard > Export data > Export by week.")

    person_col = _find(headers, "personid", "anonymizedid", "userid", "userprincipalname", "person")
    org_col = _find(headers, "organization", "organisation")
    fn_col = _find(headers, "functiontype", "jobfunction")
    # The date column is the first column whose first non-empty value parses as a date.
    date_col = next((h for h in headers
                     if _parse_date(next((r[h] for r in rows if r.get(h)), "")) is not None), None)
    if date_col is None:
        raise ValueError("Couldn't find a date column in the export.")

    # 1) Add up each person's metrics per week (day-level exports are rolled up into weeks).
    per_person: dict[tuple, dict] = defaultdict(lambda: defaultdict(float))
    info: dict[tuple, tuple] = {}
    for i, r in enumerate(rows):
        d = _parse_date(r.get(date_col, ""))
        if d is None:
            continue
        week = d - timedelta(days=(d.weekday() + 1) % 7)   # week starting Sunday, like the export
        person = r.get(person_col) if person_col else f"row{i}"
        key = (week, person)
        info[key] = ((r.get(org_col) or "Unknown").strip() or "Unknown",
                     (r.get(fn_col) or "Unknown").strip() or "Unknown")
        acc = per_person[key]
        for m in matched:
            acc[m] += _num(r.get(col(m)))

    has_enabled = col(ENABLED_DAYS) is not None
    has_active = col(ACTIVE_DAYS) is not None
    per_action = MINUTES_PER_ACTION / 60

    # 2) Roll people up to (week, organisation, function) groups for the dashboard filters.
    groups: dict[tuple, dict] = defaultdict(lambda: defaultdict(float))
    for (week, _person), m in per_person.items():
        org, fn = info[(week, _person)]
        g = groups[(week.isoformat(), org, fn)]
        actions = m[TOTAL_ACTIONS] if TOTAL_ACTIONS in matched else sum(m[a] for a in APPS.values())
        licensed = m[ENABLED_DAYS] > 0 if has_enabled else True
        active = (m[ACTIVE_DAYS] > 0) if has_active else actions > 0
        if licensed:
            g["lic"] += 1
            g["act"] += 1 if active else 0
            g["actions"] += actions
            g["meet"] += sum(m[c] for c in MEETING_HOURS)
            g["search"] += sum(m[c] for c in SEARCH_AND_SUMMARY)
            g["create"] += sum(m[c] for c in CREATION)
            g["ret"] += 1 if m[RETURNING_28] > 0 else 0
            for app, c in APPS.items():
                g["app_" + app] += m[c]
        elif m[UNLICENSED_CHAT] > 0:
            g["chatUnlic"] += 1

    out_rows = []
    for (week, org, fn), g in sorted(groups.items()):
        out_rows.append({"w": week, "org": org, "fn": fn,
                         **{k: round(v, 2) for k, v in g.items()}})

    weeks = sorted({r["w"] for r in out_rows})
    recent = set(weeks[-recent_weeks:])
    tot = defaultdict(float)
    for r in out_rows:
        if r["w"] in recent:
            for k in ("lic", "act", "meet", "search", "create"):
                tot[k] += r.get(k, 0)
    last_week_licensed = sum(r.get("lic", 0) for r in out_rows if r["w"] == weeks[-1])
    active = tot["act"] or 1

    return {
        "source": path.name,
        "weeks": weeks,
        "rows": out_rows,
        "organizations": sorted({r["org"] for r in out_rows}),
        "functions": sorted({r["fn"] for r in out_rows}),
        "matched_metrics": len(matched),
        "missing_metrics": missing,
        "has_meeting_hours": col(MEETING_HOURS[0]) is not None,
        "has_person_id": person_col is not None,
        # Averages over the most recent weeks, used to pre-fill the ROI business case.
        "roi_inputs": {
            "users": int(last_week_licensed) or int(tot["lic"] / max(len(recent), 1)),
            "adoption_rate": round(min(max(tot["act"] / tot["lic"], 0.05), 1.0), 2) if tot["lic"] else 1.0,
            "meeting_hours_per_week": round(tot["meet"] / active, 2),
            "search_actions_per_week": round(tot["search"] / active, 1),
            "creation_actions_per_week": round(tot["create"] / active, 1),
            "weeks_used": len(recent),
        },
        "assisted_hours_total": round(sum(r.get("meet", 0) + (r.get("search", 0) + r.get("create", 0)) * per_action
                                          for r in out_rows), 1),
    }
