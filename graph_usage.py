"""Download Microsoft 365 Copilot usage reports (v2) from Microsoft Graph.

Downloads three CSV reports:

    getMicrosoft365CopilotUsageUserDetail   per user: last activity per app, prompts, active days
    getMicrosoft365CopilotUserCountSummary  enabled vs active users per app, total prompts
    getMicrosoft365CopilotUserCountTrend    the same, per day

Two ways to sign in, both using an Entra ID app registration in the client's tenant:

    signin  (default on your PC)  An admin signs in in the browser with their own account and MFA.
            Needs the delegated Reports.Read.All permission and an admin role such as Reports Reader.
            No secret is stored anywhere. The token is kept in memory only.
    secret  (default when hosted)  The server signs in as the app with a client secret, unattended.
            Needs the application Reports.Read.All permission.

Settings come from environment variables, never from the chat or the repository:

    COPILOT_GRAPH_TENANT_ID       the client's tenant ID (or domain, e.g. contoso.onmicrosoft.com)
    COPILOT_GRAPH_CLIENT_ID       the app registration's Application (client) ID
    COPILOT_GRAPH_SIGNIN          optional: "session" (sign in once per session, default) or "every-time"
    COPILOT_GRAPH_AUTH            optional: "signin" or "secret"
    COPILOT_GRAPH_CLIENT_SECRET   the client secret, only for "secret"

For several client tenants, add a profile name: COPILOT_GRAPH_TENANT_ID_CONTOSO, and so on.

Docs: https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/admin-settings/reports/copilotreportroot-getmicrosoft365copilotusageuserdetail

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import csv
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Literal

GRAPH = "https://graph.microsoft.com/v1.0/copilot/reports"
AUTHORITY = "https://login.microsoftonline.com/{tenant}"
LOGIN = AUTHORITY + "/oauth2/v2.0/token"
DELEGATED_SCOPES = ["https://graph.microsoft.com/Reports.Read.All"]
REPORTS = {
    "user_detail": "getMicrosoft365CopilotUsageUserDetail",
    "summary": "getMicrosoft365CopilotUserCountSummary",
    "trend": "getMicrosoft365CopilotUserCountTrend",
}
Period = Literal["D7", "D28", "D90", "D180"]
PERIOD_DAYS = {"D7": 7, "D28": 28, "D90": 90, "D180": 180}
MINUTES_PER_PROMPT = 6          # Microsoft counts Copilot Chat prompts as search/summary actions
ADMIN_ROLES = ("Reports Reader (least privilege), AI Administrator, Global Administrator, Exchange, SharePoint "
               "or Teams Administrator")
SIGNIN_WAIT = 40                # seconds a tool call waits for the browser sign-in before returning
SIGNIN_TIMEOUT = 300            # seconds the browser sign-in stays open

_tokens: dict[str, tuple[str, float]] = {}      # in memory only: tenant+client -> (token, expiry)


class GraphError(Exception):
    """A problem the user can fix (settings, permissions); the message says how."""


class SignInPending(Exception):
    """The browser sign-in is still open; ask the user to finish it and run the tool again."""


def _env(base: str, suffix: str, fallback: bool = False) -> str:
    value = os.environ.get(base + suffix, "").strip()
    if not value and fallback and suffix:
        value = os.environ.get(base, "").strip()
    return value


def settings(profile: str = "", hosted: bool = False) -> dict:
    """Read the tenant, app and sign-in method from environment variables."""
    suffix = "_" + re.sub(r"[^A-Z0-9]", "_", profile.upper()) if profile else ""
    cfg = {
        "tenant_id": _env("COPILOT_GRAPH_TENANT_ID", suffix),
        "client_id": _env("COPILOT_GRAPH_CLIENT_ID", suffix),
        "auth": (_env("COPILOT_GRAPH_AUTH", suffix, True) or ("secret" if hosted else "signin")).lower(),
        "every_time": _env("COPILOT_GRAPH_SIGNIN", suffix, True).lower() in ("every-time", "every_time", "always"),
    }
    needed = {"tenant_id": f"COPILOT_GRAPH_TENANT_ID{suffix}", "client_id": f"COPILOT_GRAPH_CLIENT_ID{suffix}"}
    if cfg["auth"] not in ("signin", "secret"):
        raise GraphError('COPILOT_GRAPH_AUTH must be "signin" or "secret".')
    if cfg["auth"] == "secret":
        cfg["client_secret"] = _env("COPILOT_GRAPH_CLIENT_SECRET", suffix)
        needed["client_secret"] = f"COPILOT_GRAPH_CLIENT_SECRET{suffix}"
    elif hosted:
        raise GraphError("Browser sign-in only works when the MCP runs on your PC. On a hosted server, set "
                         "COPILOT_GRAPH_AUTH=secret and the client secret (see INSTALL.md section H).")
    missing = [name for key, name in needed.items() if not cfg.get(key)]
    if missing:
        raise GraphError("Not set up yet: set the environment variable(s) " + ", ".join(missing) +
                         " and restart the app. See INSTALL.md section H.")
    return cfg


def get_token(cfg: dict) -> str:
    return _signin_token(cfg) if cfg["auth"] == "signin" else _secret_token(cfg)


# --- Admin sign-in in the browser (delegated permission, no secret) ---------

class _SignIn:
    """One tenant's sign-in state: the MSAL app with its in-memory token cache, and any open browser sign-in."""

    def __init__(self, cfg: dict):
        try:
            import msal
        except ImportError:
            raise GraphError("The sign-in library is missing. Run: pip install -r requirements.txt") from None
        try:
            self.app = msal.PublicClientApplication(cfg["client_id"],
                                                    authority=AUTHORITY.format(tenant=cfg["tenant_id"]))
        except Exception as err:                # offline, or a tenant that doesn't exist
            raise GraphError(f"Can't start the Microsoft sign-in for tenant {cfg['tenant_id']}: {err}") from None
        self.thread: threading.Thread | None = None
        self.result: dict | None = None
        self.lock = threading.Lock()

    def start(self, every_time: bool):
        def run():
            try:
                result = self.app.acquire_token_interactive(
                    DELEGATED_SCOPES, prompt="login" if every_time else "select_account",
                    timeout=SIGNIN_TIMEOUT)
            except Exception as err:            # browser couldn't open, port in use, timeout...
                result = {"error": type(err).__name__, "error_description": str(err)}
            with self.lock:
                self.result = result or {"error": "cancelled", "error_description": "The sign-in was cancelled."}
        self.result = None
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def take_result(self) -> dict | None:
        with self.lock:
            result, self.result = self.result, None
        if result is not None:
            self.thread = None
        return result


_signins: dict[str, _SignIn] = {}


def _signin_token(cfg: dict) -> str:
    key = cfg["tenant_id"] + "|" + cfg["client_id"]
    state = _signins.get(key)
    if state is None:
        state = _signins[key] = _SignIn(cfg)

    if not cfg["every_time"]:
        for account in state.app.get_accounts():
            result = state.app.acquire_token_silent(DELEGATED_SCOPES, account=account)
            if result and "access_token" in result:
                state.take_result()             # a finished browser sign-in is no longer needed
                return result["access_token"]

    if state.thread is None and state.result is None:
        state.start(cfg["every_time"])
    if state.thread is not None:
        state.thread.join(SIGNIN_WAIT)
    result = state.take_result()
    if result is None:
        raise SignInPending("A Microsoft sign-in page is open in your browser. Sign in with an admin account "
                            f"({ADMIN_ROLES}), then run download_copilot_usage again.")
    if "access_token" not in result:
        detail = (result.get("error_description") or result.get("error") or "").splitlines()[0]
        raise GraphError(f"Sign-in didn't complete: {detail}")
    if cfg["every_time"]:                        # forget the sign-in straight after this download
        for account in state.app.get_accounts():
            state.app.remove_account(account)
    return result["access_token"]


# --- App-only sign-in with a client secret (hosted or unattended) ------------

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


def _secret_token(cfg: dict) -> str:
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


# --- Reports ------------------------------------------------------------------

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
            raise GraphError(
                f"Microsoft Graph refused access ({err.code}). Check that the app has the Reports.Read.All "
                "permission with admin consent (delegated for sign-in, application for a secret), and, for "
                f"sign-in, that your account has an admin role: {ADMIN_ROLES}.") from None
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
