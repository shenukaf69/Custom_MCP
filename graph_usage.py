"""Download Microsoft 365 Copilot usage reports (v2) from Microsoft Graph.

Signs in as an Entra ID app registration (client credentials) with the
Reports.Read.All application permission, then downloads three CSV reports:

    getMicrosoft365CopilotUsageUserDetail   per user: last activity per app, prompts, active days
    getMicrosoft365CopilotUserCountSummary  enabled vs active users per app, total prompts
    getMicrosoft365CopilotUserCountTrend    the same, per day

The app's details come from environment variables, never from the chat or the repository:

    COPILOT_GRAPH_TENANT_ID       the client's tenant ID (or domain, e.g. contoso.onmicrosoft.com)
    COPILOT_GRAPH_CLIENT_ID       the app registration's Application (client) ID
    COPILOT_GRAPH_CLIENT_SECRET   the app registration's client secret value

For several client tenants, add a profile name: COPILOT_GRAPH_TENANT_ID_CONTOSO, and so on.

Docs: https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/admin-settings/reports/copilotreportroot-getmicrosoft365copilotusageuserdetail

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Literal

GRAPH = "https://graph.microsoft.com/v1.0/copilot/reports"
LOGIN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
REPORTS = {
    "user_detail": "getMicrosoft365CopilotUsageUserDetail",
    "summary": "getMicrosoft365CopilotUserCountSummary",
    "trend": "getMicrosoft365CopilotUserCountTrend",
}
Period = Literal["D7", "D28", "D90", "D180"]
PERIOD_DAYS = {"D7": 7, "D28": 28, "D90": 90, "D180": 180}
MINUTES_PER_PROMPT = 6          # Microsoft counts Copilot Chat prompts as search/summary actions

_tokens: dict[str, tuple[str, float]] = {}      # in memory only: tenant+client -> (token, expiry)


class GraphError(Exception):
    """A problem the user can fix (settings, permissions); the message says how."""


def settings(profile: str = "") -> dict:
    """Read the app registration from environment variables. The secret is never logged or returned."""
    suffix = "_" + re.sub(r"[^A-Z0-9]", "_", profile.upper()) if profile else ""
    names = {k: f"COPILOT_GRAPH_{k.upper()}{suffix}" for k in ("tenant_id", "client_id", "client_secret")}
    values = {k: os.environ.get(v, "").strip() for k, v in names.items()}
    missing = [names[k] for k, v in values.items() if not v]
    if missing:
        raise GraphError("Not set up yet: set the environment variable(s) " + ", ".join(missing) +
                         " and restart the app. See INSTALL.md > Automatic Copilot usage download.")
    return values


def _post_form(url: str, form: dict) -> dict:
    data = urllib.parse.urlencode(form).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        try:
            detail = json.load(err).get("error_description", "").splitlines()[0]
        except (ValueError, AttributeError, IndexError):
            detail = ""
        raise GraphError(f"Sign-in failed ({err.code}). Check the tenant ID, client ID and secret "
                         f"(secrets expire). {detail}".strip()) from None
    except urllib.error.URLError as err:
        raise GraphError(f"Can't reach login.microsoftonline.com: {err.reason}") from None


def get_token(cfg: dict) -> str:
    """Client-credentials token for Microsoft Graph, cached in memory until shortly before it expires."""
    key = cfg["tenant_id"] + "|" + cfg["client_id"]
    token, expiry = _tokens.get(key, ("", 0.0))
    if token and time.time() < expiry - 300:
        return token
    body = _post_form(LOGIN.format(tenant=urllib.parse.quote(cfg["tenant_id"])), {
        "grant_type": "client_credentials",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "scope": "https://graph.microsoft.com/.default",
    })
    _tokens[key] = (body["access_token"], time.time() + int(body.get("expires_in", 3600)))
    return body["access_token"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _get(url: str, token: str | None) -> bytes:
    """GET a report. Graph may redirect to a download URL, which must be fetched without the token."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=120) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        if err.code in (301, 302, 303, 307, 308) and err.headers.get("Location"):
            return _get(err.headers["Location"], None)
        if err.code in (401, 403):
            raise GraphError(f"Microsoft Graph refused access ({err.code}). The app needs the Reports.Read.All "
                             "application permission with admin consent in this tenant.") from None
        raise GraphError(f"Microsoft Graph returned {err.code} {err.reason}.") from None
    except urllib.error.URLError as err:
        raise GraphError(f"Can't reach graph.microsoft.com: {err.reason}") from None


def fetch_report(report: str, period: str, token: str) -> str:
    url = f"{GRAPH}/{REPORTS[report]}(period='{period}')"   # v2 is the default version
    return _get(url, token).decode("utf-8-sig")


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _num(value) -> float:
    try:
        return float(str(value).replace(",", "") or 0)
    except ValueError:
        return 0.0


def _col(row: dict, *words: str) -> str | None:
    """The first column whose name contains all the words (case-insensitive)."""
    for name in row:
        if all(w in name.lower() for w in words):
            return name
    return None


def summarise(user_detail: str, summary: str, period: str) -> dict:
    """Headline numbers from the downloaded CSVs."""
    users = _rows(user_detail)
    days = PERIOD_DAYS[period]
    out = {"period_days": days, "licensed_users": len(users), "apps": [],
           "enabled_users": None, "active_users": None, "prompts": None}

    srow = next(iter(_rows(summary)), None)
    if srow:
        for name, value in srow.items():
            m = re.match(r"(.+?) (Enabled|Active) Users$", name.strip())
            if m and m.group(1) != "Any App":
                app = next((a for a in out["apps"] if a["app"] == m.group(1)), None)
                if not app:
                    app = {"app": m.group(1), "enabled": 0, "active": 0}
                    out["apps"].append(app)
                app[m.group(2).lower()] = int(_num(value))
        if (c := _col(srow, "any app", "enabled")):
            out["enabled_users"] = int(_num(srow[c]))
        if (c := _col(srow, "any app", "active")):
            out["active_users"] = int(_num(srow[c]))
        if (c := _col(srow, "total", "prompts")):
            out["prompts"] = _num(srow[c])

    if users:
        first = users[0]
        prompts_col = _col(first, "prompts", "all apps")
        days_col = _col(first, "active usage days")
        last_col = _col(first, "last activity date")      # the first one is "Last Activity Date" (any app)
        if out["active_users"] is None and last_col:
            out["active_users"] = sum(1 for u in users if u.get(last_col))
        if out["enabled_users"] is None:
            out["enabled_users"] = len(users)
        if prompts_col and out["prompts"] is None:
            out["prompts"] = sum(_num(u[prompts_col]) for u in users)
        if days_col:
            active = [_num(u[days_col]) for u in users if _num(u[days_col]) > 0]
            out["avg_active_days"] = sum(active) / len(active) if active else 0.0

    active = out["active_users"] or 0
    prompts = out["prompts"] or 0
    out["adoption_rate"] = active / out["enabled_users"] if out["enabled_users"] else 0.0
    out["prompts_per_active_user_per_week"] = prompts / active / (days / 7) if active else 0.0
    out["prompt_assisted_hours"] = prompts * MINUTES_PER_PROMPT / 60
    return out
