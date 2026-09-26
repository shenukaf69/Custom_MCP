# Set up the automatic Copilot usage download (Microsoft Graph)

Created by Shenuka Fernando. © 2026 Shenuka Fernando. All rights reserved.

The `download_copilot_usage` tool downloads a client's **Microsoft 365 Copilot usage reports (v2)** from Microsoft
Graph into your **Downloads** folder, so nobody has to export them by hand. It's optional: every other tool works
without it.

**What you get:** three CSV files (per-user detail, summary, daily trend) and a summary in the chat. It covers
licensed users, active users per app (Teams, Outlook, Word, Excel, PowerPoint, Copilot Chat, Edge, agents),
prompts submitted and active days, for the last 7, 28, 90 or 180 days.

**What it doesn't include:** meeting hours summarised and creation actions. You need those for Microsoft's full
assisted-hours ROI, so use a Copilot Dashboard export for exact figures or give estimates. Copilot Chat usage by
people without a Copilot licence isn't in Graph either. The tool gives a **lower-bound** figure: prompts × 6 minutes,
which is how Microsoft counts Copilot Chat prompts.

**How it signs in:** an **admin signs in in the browser** with their own work account and MFA. **No secret is
stored anywhere.** Only people with an admin reports role can download, and the client can restrict it further
to named people. (A hosted server uses a client secret instead; see
[Hosted or unattended use](#hosted-or-unattended-use-client-secret).)

**You need a real Microsoft 365 tenant with Copilot licences**, such as a client's tenant or your company's.
"Contoso" in the examples is Microsoft's made-up company name. A developer sandbox has no Copilot licences, so its
reports would be empty.

| Step | Who | Where | How long |
|------|-----|-------|----------|
| [1. Set up access](#step-1-the-clients-admin-sets-up-access) | The client's Global Administrator | Microsoft Entra admin center (browser) | About 10 minutes, once per tenant |
| [2. Tell the MCP about the tenant](#step-2-tell-the-mcp-about-the-tenant) | You | PowerShell on your PC | 2 minutes, once per tenant |
| [3. Download](#step-3-download-the-usage) | You, or the admin during a meeting | Claude | Every time you need data |

---

## Ask the client's admin

Copy this into an email or Teams message:

> Hi <name>,
>
> To build the Copilot adoption and ROI report, could you set up read-only access to the Microsoft 365 Copilot
> usage reports? It takes about 10 minutes in the Microsoft Entra admin center:
>
> 1. **App registration:** name `Copilot Consultant MCP - usage reports`, "Accounts in this organizational
>    directory only", redirect URI **Public client/native (mobile & desktop)** = `http://localhost`.
> 2. **API permission:** Microsoft Graph, **delegated** `Reports.Read.All`, with **admin consent granted**.
> 3. **Enterprise application > Properties:** Assignment required = **Yes**, and add my account under
>    **Users and groups**.
> 4. **Role:** assign my account the **Reports Reader** role.
>
> Then please send me the **Directory (tenant) ID** and the **Application (client) ID** from the app's Overview
> page. No client secret is needed. The permission only reads usage reports: no mail, files, chats or calendars.
> Every download shows under my name in your sign-in logs, and you can remove access at any time.
>
> Thanks!

If you'd rather not have access to their tenant, skip points 3 and 4 for you: the admin signs in themselves when
the sign-in page opens during a meeting with you.

---

## Step 1: The client's admin sets up access

Someone at the client with **Global Administrator** (or Privileged Role Administrator) rights does this in their
browser, once. It lets the MCP read that tenant's Copilot usage reports, and only when an approved admin signs in.

### A. Create the app registration
1. Go to **https://entra.microsoft.com** and sign in as the Global Administrator.
2. In the left menu, open **Entra ID** > **App registrations** > **+ New registration**.
3. Fill in:
   - **Name:** `Copilot Consultant MCP - usage reports`
   - **Supported account types:** *Accounts in this organizational directory only*
   - **Redirect URI:** choose **Public client/native (mobile & desktop)** and type `http://localhost`
4. Select **Register**.

To add the redirect URI later: the app > **Authentication** > **Add a platform** > **Mobile and desktop
applications** > custom redirect URI `http://localhost`.

### B. Copy the two IDs
You land on the app's **Overview** page. Copy:
- **Application (client) ID**, e.g. `3f2a9c1e-7b4d-4e8a-9f10-2c6d8e5b1a77`
- **Directory (tenant) ID**, e.g. `8a1b2c3d-1111-2222-3333-444455556666`

These aren't passwords, so they're safe to send by email.

### C. Give it permission to read usage reports
1. On the app's left menu, open **API permissions** > **+ Add a permission**.
2. Choose **Microsoft Graph** > **Delegated permissions**.
3. Search for `Reports.Read.All`, tick it, and select **Add permissions**.
4. Select **Grant admin consent for <company name>** > **Yes**.
5. The Status column must show a **green tick**.

Don't create a client secret under **Certificates & secrets**. It isn't needed.

### D. Allow only named people (recommended)
1. In the left menu, open **Entra ID** > **Enterprise applications** and select the app.
2. Open **Properties**, set **Assignment required?** to **Yes**, then **Save**.
3. Open **Users and groups** > **+ Add user/group**, add the consultant's account (and anyone else allowed), then
   **Assign**. Assigning groups needs Microsoft Entra ID P1 or P2; assigning individual users doesn't.

### E. Give the consultant a reports role
1. In the left menu, open **Entra ID** > **Roles & admins**, search for **Reports Reader** and select it.
2. Select **+ Add assignments**, add the consultant's account, and save.

Microsoft only returns usage reports to someone signed in with one of these roles: **Reports Reader** (least
privilege), AI Administrator, Global Administrator, Exchange Administrator, SharePoint Administrator, Teams
Administrator or Teams Communications Administrator. Without one, sign-in works but the download is refused.

If the admin will sign in themselves during a meeting, skip D and E for the consultant, because the admin already
has the rights.

### F. Send the IDs
Send the consultant the **tenant ID** and **client ID** from step B. **No secret is created or shared.**

`Reports.Read.All` reads Microsoft 365 **usage reports** only. It can't read anyone's mail, files, chats or
calendars. See [Microsoft's permission reference](https://learn.microsoft.com/graph/permissions-reference#reportsreadall).

---

## Step 2: Tell the MCP about the tenant

The MCP needs to know which tenant and app to sign in to. You store the two IDs as Windows **user environment
variables**. Neither is a secret, and no admin rights are needed on your PC.

1. Open **PowerShell** normally (not "Run as administrator").
2. Paste these two lines, replacing the parts in `< >` with the IDs the admin sent:
   ```powershell
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_TENANT_ID", "<tenant-id>", "User")
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_CLIENT_ID", "<client-id>", "User")
   ```
   For example:
   ```powershell
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_TENANT_ID", "8a1b2c3d-1111-2222-3333-444455556666", "User")
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_CLIENT_ID", "3f2a9c1e-7b4d-4e8a-9f10-2c6d8e5b1a77", "User")
   ```
   The tenant ID can also be the domain, e.g. `fabrikam.onmicrosoft.com`.
3. Check they're saved. Both lines should say `True`:
   ```powershell
   "COPILOT_GRAPH_TENANT_ID", "COPILOT_GRAPH_CLIENT_ID" |
     ForEach-Object { "$_ : " + [bool][Environment]::GetEnvironmentVariable($_, "User") }
   ```
4. Make sure you have the latest code and Microsoft's sign-in library (`msal`):
   ```powershell
   cd C:\Users\<you>\Custom_MCP
   .venv\Scripts\Activate.ps1
   git pull
   pip install -r requirements.txt
   ```
5. **Fully quit Claude** (right-click the tray icon > **Quit**) and reopen it. Claude only reads these settings
   when it starts.

Without PowerShell: search the Start menu for **Edit environment variables for your account**, then under **User
variables** select **New** for each variable.

**Optional: sign in before every download.** By default you sign in once, and it's remembered until Claude closes.
To be asked every time:
```powershell
[Environment]::SetEnvironmentVariable("COPILOT_GRAPH_SIGNIN", "every-time", "User")
```

**More than one client:** add the client's name to the end of each variable, then name the client in the prompt:
```powershell
[Environment]::SetEnvironmentVariable("COPILOT_GRAPH_TENANT_ID_FABRIKAM", "<their-tenant-id>", "User")
[Environment]::SetEnvironmentVariable("COPILOT_GRAPH_CLIENT_ID_FABRIKAM", "<their-client-id>", "User")
```
→ *"Download Fabrikam's Copilot usage for the last 28 days."* Each client's sign-in is kept separately, and the
files are named after the client.

---

## Step 3: Download the usage

In Claude:
```
Download Copilot usage for the last 28 days.
```
A Microsoft sign-in page opens in your browser. Sign in with the admin account and complete MFA. Claude shows the
summary, and the three CSVs land in your Downloads folder.

If sign-in takes more than about 40 seconds, Claude says the sign-in page is still open. Finish signing in, then
type *"Done, try again."*

More prompts:
```
Download Copilot usage for the last 90 days.
```
```
Download Copilot usage for the last 28 days and estimate the ROI in SGD: S$92 an hour, S$38.40 per licence, S$50,000 rollout costs, 1 meeting hour and 3 creation actions per user per week.
```
```
Download Fabrikam's Copilot usage for the last 90 days, then create an ROI dashboard for Fabrikam in SGD using those numbers: S$92 an hour, S$38.40 per licence, S$50,000 rollout costs, 1 meeting hour and 3 creation actions per user per week. Prepared by Shenuka Fernando.
```

Without Claude (PowerShell, in the `Custom_MCP` folder with `.venv` active):
```powershell
python -c "import server; print(server.download_copilot_usage(period='D28'))"
python -c "import server; print(server.download_copilot_usage(period='D90', tenant_profile='fabrikam'))"
```

**If Claude says the Graph connection isn't set up**, the variables aren't visible to Claude. Check step 2.3, make
sure the client's name in the prompt matches the variable suffix (or leave the name out for the default variables),
and fully quit and reopen Claude.

---

## How sign-in works

1. When the tool runs, `graph_usage.py` reads the tenant and app IDs from the environment variables.
2. It opens the **Microsoft sign-in page** in your browser, using Microsoft's own library (MSAL). You sign in on
   Microsoft's page, so the MCP and Claude never see your password or MFA code.
3. Entra checks your account, MFA and the client's Conditional Access policies, and whether you're assigned to
   the app (if step 1D is on). It then returns an **access token** to the MCP through `http://localhost` on
   your PC.
4. The MCP calls `graph.microsoft.com/v1.0/copilot/reports/...` with the token. Graph checks your **admin role**
   before returning the reports. When Graph redirects to the file download, the token isn't sent on.
5. The token is kept **in memory only**. With `session`, it's reused (and quietly renewed) until Claude closes.
   With `every-time`, it's discarded straight after each download.
6. Nothing is written to disk except the three CSVs. The token is never logged or returned to the AI; Claude only
   sees the summary and the file paths.

**Audit trail:** each download shows in the client's Entra **sign-in logs** under **your name** and the app's
name. **Turning it off:** the client's admin disables or deletes the app, or removes you from **Users and
groups**. Delete the app registration when the engagement ends.

**Names in the files:** by default Microsoft 365 hides user names in reports and shows scrambled IDs. The totals are
the same either way. An admin can change this in **Microsoft 365 admin center > Settings > Org settings > Reports**.

**Network:** needs `login.microsoftonline.com` and `graph.microsoft.com` (HTTPS 443). Graph may redirect the file
download to another Microsoft address, so if a proxy blocks it, the error names the address to allow.

## Common errors

| Message | Fix |
|---------|-----|
| Not set up yet: set the environment variable(s) … | Set the variables named in the message, then fully restart Claude |
| The sign-in library is missing | Run `pip install -r requirements.txt` in the `.venv`, then restart Claude |
| AADSTS50011 (redirect URI mismatch) | Add `http://localhost` under **Authentication > Mobile and desktop applications** (step 1A) |
| AADSTS50105 (not assigned to the app) | Assignment is required and your account isn't added under **Users and groups** (step 1D) |
| AADSTS65001 (consent) | Admin consent wasn't granted for the delegated `Reports.Read.All` permission |
| Microsoft Graph refused access (403) | Your account doesn't have an admin reports role (e.g. Reports Reader), or the permission is an application permission instead of delegated |

## Hosted or unattended use (client secret)

A hosted server (Copilot Studio, Cowork) can't open a browser on your PC, so it signs in **as the app** with a
client secret instead. There's no per-person check, so protect the server with an API key or OAuth
([DEPLOYMENT.md](DEPLOYMENT.md)): anyone who can call it can download that tenant's usage reports.

1. In the app registration, add **Application permissions** > **Reports.Read.All** and grant admin consent.
2. **Certificates & secrets** > **New client secret**. Choose a short expiry and copy the **Value** (not the
   Secret ID). It's only shown once, so share it through a password manager, never by email or chat.
3. Store it as a Container Apps secret and switch the tool to secret mode:

```powershell
az containerapp secret set -n copilot-consultant -g rg-copilot-consultant --secrets graph-secret=<secret-value>
az containerapp update -n copilot-consultant -g rg-copilot-consultant --set-env-vars `
  COPILOT_GRAPH_TENANT_ID=<tenant-id> COPILOT_GRAPH_CLIENT_ID=<client-id> `
  COPILOT_GRAPH_AUTH=secret COPILOT_GRAPH_CLIENT_SECRET=secretref:graph-secret
```

Hosted, secret mode is the default, and the files come back as download links. On your PC you can also use secret
mode for unattended runs: set `COPILOT_GRAPH_AUTH` to `secret` and `COPILOT_GRAPH_CLIENT_SECRET` as user
variables (`Read-Host "Client secret" -MaskInput` keeps it out of your PowerShell history). The secret is then
stored as plain text in your Windows profile (`HKEY_CURRENT_USER\Environment`), readable by anything that runs as
you. The MCP sends it only to `login.microsoftonline.com` to get a one-hour token (the OAuth client credentials
flow), and never logs it or returns it to the AI. Set a reminder to renew it before it expires.

([Copilot usage report API](https://learn.microsoft.com/microsoft-365/copilot/extensibility/api/admin-settings/reports/copilotreportroot-getmicrosoft365copilotusageuserdetail),
[MSAL Python interactive sign-in](https://learn.microsoft.com/entra/msal/python/),
[client credentials flow](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-client-creds-grant-flow))
