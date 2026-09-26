# Using the Copilot Consultant MCP in Microsoft 365

Created by Shenuka Fernando. © 2026 Shenuka Fernando. All rights reserved.

On your PC, Claude Desktop starts the MCP server itself. Microsoft 365 can't reach your PC, so every
Microsoft 365 surface needs the server running as a **web service** with a public **HTTPS** address,
using the **Streamable HTTP** transport. This guide covers that first, then each surface.

| Where | Custom MCP supported? | How | Authentication options |
|-------|----------------------|-----|------------------------|
| Copilot Studio, standard harness ("classic") | Yes | Tools > Add a tool > New tool > Model Context Protocol | None, API key, OAuth 2.0 |
| Copilot Studio, GitHub Copilot harness | Yes (preview) | Build tab > Tools > Add > Model Context Protocol (MCP) | Per the add-server page |
| Copilot Cowork | Yes, as a plugin | Upload a plugin package in the Microsoft 365 admin center | None, OAuth (API keys aren't supported in Cowork yet) |
| Agent Builder in Microsoft 365 Copilot | **No** (no way to add an MCP server) | Use a declarative agent from Agents Toolkit, or a Copilot Studio agent published to Microsoft 365 Copilot | None, OAuth, Entra SSO |
| ChatGPT (web and desktop app) | Yes, in Developer mode | See [INSTALL.md](INSTALL.md#d-chatgpt-web-and-desktop-app) | None, OAuth (no API keys) |

To install in Claude Desktop, Claude Code or the OpenAI Codex app (which run the server on your PC), see
[INSTALL.md](INSTALL.md).

Microsoft's docs are linked in each section; features marked preview can change.

---

## Step 1: Run the server as a web service

```powershell
pip install -r requirements.txt
python server.py --http
```

This serves MCP at `http://localhost:8000/mcp` (Streamable HTTP, stateless) and a health check at `/health`.

| Setting (environment variable) | What it does |
|--------------------------------|--------------|
| `MCP_API_KEY` | If set, calls to `/mcp` must send it as an `x-api-key` header or `Authorization: Bearer <key>`. Use for Copilot Studio. **Leave unset for Cowork and declarative agents**, which don't support API keys. |
| `PUBLIC_BASE_URL` | The public `https://` address, used for download links to generated decks and dashboards. Set automatically on Azure Container Apps. |
| `ALLOWED_HOSTS` | Optional comma-separated host names to accept (DNS-rebinding protection). |
| `PORT` | Port to listen on (default 8000). |

Generated files are served at `/files/<random-name>`. The random prefix makes links unguessable, but anyone
with a link can download it, so share links only with the right people.

## Step 2: Give it a public HTTPS address

### Option A: quick test with Dev Tunnels (your PC stays on)

Window 1, the server (listening only on your laptop):
```powershell
cd C:\Users\<you>\Custom_MCP
.venv\Scripts\Activate.ps1
$env:MCP_API_KEY = "a-long-random-key"     # for Copilot Studio; leave out for Cowork and ChatGPT
python server.py --http --host 127.0.0.1
```

Window 2, the tunnel:
```powershell
winget install Microsoft.devtunnel
devtunnel user login
devtunnel host -p 8000 --allow-anonymous
```

It prints an address like `https://abc123-8000.asse.devtunnels.ms`. **Your MCP URL is that address plus `/mcp`.**
Set it for download links, then restart the server in window 1:
```powershell
$env:PUBLIC_BASE_URL = "https://abc123-8000.asse.devtunnels.ms"
```

The URL only works while your laptop is on and both windows are running. `--allow-anonymous` is needed because
Microsoft's and OpenAI's clouds can't sign in to your tunnel, so anyone with the address can reach it: use
`MCP_API_KEY` where the app supports it, and only sample data otherwise. Good for demos, not production.
([Dev tunnels](https://learn.microsoft.com/azure/developer/dev-tunnels/overview))

### Option B: Azure Container Apps (recommended)

Needs an Azure subscription and the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli).
From the `Custom_MCP` folder (it contains the `Dockerfile`):

```powershell
az login
az containerapp up --name copilot-consultant --source . --ingress external --target-port 8000 --env-vars MCP_API_KEY=<make-up-a-long-random-key>
```

The command creates a resource group, container registry and environment, builds the image and prints the
app's address. Your MCP endpoint is `https://<that address>/mcp`. Download links work automatically
(the server reads `CONTAINER_APP_NAME` and `CONTAINER_APP_ENV_DNS_SUFFIX`).

To redeploy after changes, run the same command with `--resource-group` and `--environment` from the first run.
To change a setting: `az containerapp update -n copilot-consultant -g <resource-group> --set-env-vars NAME=value`.
([containerapp up](https://learn.microsoft.com/azure/container-apps/containerapp-up))

Notes:
- Generated files live in the container and disappear when it restarts. Download them straight away.
- Uploaded Copilot Dashboard exports are client data (anonymised). Agree with the client before uploading,
  and prefer OAuth (Step 7) for production.

---

## Step 3: Copilot Studio, standard harness ("classic")

Requires generative orchestration. Copilot Studio supports MCP **tools and resources** (not prompts), over
Streamable HTTP.

1. In [Copilot Studio](https://copilotstudio.microsoft.com), create or open an agent and turn on
   **Generative orchestration** in the agent's settings.
2. Go to **Tools** > **Add a tool** > **New tool** > **Model Context Protocol**.
3. Fill in:
   - **Server name**: `Copilot Consultant`
   - **Server description**: `Copilot readiness, build tier, use cases, ROI with Microsoft's assisted hours method, Copilot Dashboard analysis, PowerPoint decks and ROI dashboards.`
   - **Server URL**: `https://<your address>/mcp`
   - **Authentication**: **API key** > Type **Header** > Header name `x-api-key` (or **None** if you didn't set `MCP_API_KEY`).
4. Select **Create**, then **Create a new connection** (enter the API key) and **Add to agent**.
5. In the agent's **Instructions**, add something like: *"Use the Copilot Consultant tools for Copilot readiness,
   tier recommendations, use cases, ROI and client decks. Always share the download links the tools return."*
6. Test in the test pane: *"Assess readiness: licences yes, DLP no, SharePoint reviewed no, sponsor yes, change plan yes."*

If the MCP option is greyed out, your admin's Power Platform data policy is blocking it: MCP servers are
governed by data policies like connectors.
([Connect an existing MCP server](https://learn.microsoft.com/microsoft-copilot-studio/mcp-add-existing-server-to-agent),
[MCP in Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio/agent-extend-action-mcp))

## Step 4: Copilot Studio, GitHub Copilot harness (preview)

This harness reasons through multi-step tasks and creates Word, Excel and PowerPoint files itself.

1. Open the agent in Copilot Studio and select the **Build** tab.
2. In the components panel, select **Tools** > **Add** > **Model Context Protocol (MCP)**.
3. Enter the same **Name**, **Description**, **Server URL** and **Authentication** as in Step 3, then **Add**.
4. Check that the 10 tools are listed with clear descriptions, then **Save**.
5. Test on the **Preview** tab and open the activity trace to see which tool ran.

([Add an MCP server (GitHub Copilot harness)](https://learn.microsoft.com/microsoft-copilot-studio/agents-experience/tools-add-mcp-server),
[Harnesses](https://learn.microsoft.com/microsoft-copilot-studio/harnesses-overview))

## Step 5: Put the Copilot Studio agent in Teams and Microsoft 365 Copilot

1. Select **Publish**.
2. **Channels** > **Teams and Microsoft 365 Copilot** > **Add channel**.
3. Share the agent with the right users or groups.

Users then find it in the agent list in Microsoft 365 Copilot and Teams.
([Publish to Teams and Microsoft 365](https://learn.microsoft.com/microsoft-copilot-studio/publication-add-bot-to-microsoft-teams))

## Step 6: Copilot Cowork

Cowork uses plugins: a package with the MCP connector plus a skill (`skills/copilot-business-case`) that
teaches Cowork the consulting workflow. The skill and icons are in `m365/cowork-plugin/`.

1. Run the server **without** `MCP_API_KEY` (Cowork doesn't support API keys yet), or set up OAuth (Step 7).
2. Build the package:
   ```powershell
   python m365/cowork-plugin/build_cowork_plugin.py --url https://<your address>/mcp --privacy-url https://<your site>/privacy --terms-url https://<your site>/terms
   ```
   It creates `m365/cowork-plugin/dist/copilot-consultant-cowork.zip`.
3. In the **Microsoft 365 admin center** > **Manage apps** > **Upload custom app**, select **…** > **Add agent**
   and upload the zip (needs an admin role).
4. In **Cowork** > **Sources & Skills** > **Plugins**, find **Copilot Consultant** under **Discover** and add it.
5. Attach a Copilot Dashboard export in Cowork and ask: *"Build a Copilot business case and client deck for
   Contoso in SGD: S$92 an hour, S$38.40 per licence, S$50,000 rollout costs."* Cowork passes the attached
   file to the tools automatically.

For a personal test without an admin, you can sideload with the Agents Toolkit CLI:
`npm install -g @microsoft/m365agentstoolkit-cli`, `atk auth login`, then
`atk install --file-path <zip> --scope Personal`.
([Build plugins for Copilot Cowork](https://learn.microsoft.com/microsoft-365/copilot/cowork/cowork-plugin-development))

## Step 7: Declarative agents (the alternative to Agent Builder)

Agent Builder in Microsoft 365 Copilot can't add an MCP server. To get an agent in the same Microsoft 365
Copilot agent list that uses your tools, use either:

- **A Copilot Studio agent** published to Microsoft 365 Copilot (Steps 3 to 5), or
- **A declarative agent built with Microsoft 365 Agents Toolkit** (VS Code, Agents Toolkit 6.12 or later):
  1. Agents Toolkit > **Create a New Agent/App** > **Declarative Agent** > **Add an Action** > **Start with an MCP Server**.
  2. Enter `https://<your address>/mcp` and choose the authentication (**None** for a server without
     `MCP_API_KEY`; OAuth or Entra SSO for production).
  3. Provision and test it in Microsoft 365 Copilot at `https://m365.cloud.microsoft/chat`.
  ([Build a declarative agent plugin from an MCP server](https://learn.microsoft.com/microsoft-365/copilot/extensibility/build-mcp-plugins))

Admins can also register the server once in the Microsoft 365 admin center's tool registry
("bring your own MCP server"), so makers pick it from a list in Copilot Studio.
([Manage tools for agents](https://learn.microsoft.com/microsoft-365/admin/manage/manage-tools-for-agent))

### Production sign-in (OAuth)

For client data, protect the server with Microsoft Entra ID instead of an API key: register an app in Entra ID,
enable [built-in authentication on Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication),
and choose **OAuth 2.0** in Copilot Studio (or `--auth oauth --reference-id <id>` for the Cowork package).
This needs your Azure and Microsoft 365 admins; test it in a development tenant first.

---

## Networking and offline use

### Where the server is reachable

| How you run it | URL | Who can reach it |
|----------------|-----|------------------|
| Claude Desktop, Claude Code, Codex (STDIO) | None: the app starts `server.py` itself | Only that app |
| `python server.py --http --host 127.0.0.1` | `http://localhost:8000/mcp` | Only apps on your laptop |
| Dev Tunnel | `https://<tunnel>.devtunnels.ms/mcp` | Anyone with the address (use an API key or sample data) |
| Azure Container Apps | `https://<app>.<region>.azurecontainerapps.io/mcp` | Anyone with the address; protect with an API key or OAuth |

Copilot Studio, Copilot Cowork and ChatGPT run in the cloud, so they can't use `localhost`.

### Networks to allow

**Your laptop (with a Dev Tunnel)** needs **no inbound ports**. The tunnel only makes outbound HTTPS (443)
connections, and `--host 127.0.0.1` keeps the server off your network. If outbound traffic is restricted, allow
([Dev Tunnels security](https://learn.microsoft.com/azure/developer/dev-tunnels/security)):

| Purpose | Domains (HTTPS 443) |
|---------|---------------------|
| Sign in to Dev Tunnels | `login.microsoftonline.com` (Microsoft account) or `github.com` |
| Dev Tunnels service | `global.rel.tunnels.api.visualstudio.com`, `*.rel.tunnels.api.visualstudio.com`, `*.devtunnels.ms` |
| Setup and updates | `github.com` (git), `pypi.org` and `files.pythonhosted.org` (pip) |
| `download_copilot_usage` (optional) | `login.microsoftonline.com`, `graph.microsoft.com` |

**Traffic arriving at your server:**

| Caller | Comes from | Can you restrict it by IP? |
|--------|------------|----------------------------|
| Copilot Studio | Microsoft's cloud, through Power Platform connectors | Yes: allow the Power Platform connector outbound addresses for your region (Azure service tag `AzureConnectors`). See [connector IP addresses](https://learn.microsoft.com/power-automate/ip-address-configuration#connectors) |
| Copilot Cowork | Microsoft's cloud | Not reliably: no fixed IP list is published. Cowork identifies itself as `copilot-cowork`, but that can be faked, so rely on authentication |
| ChatGPT | OpenAI's cloud | Use authentication, or OpenAI's Secure MCP Tunnel |

### What works offline

The MCP needs no internet, except for `download_copilot_usage`. Everything below runs on your PC:

| Tool or resource | Offline? | Uses |
|------------------|----------|------|
| `assess_readiness`, `recommend_tier`, `find_use_cases`, `plan_build_along` | Yes | Rules and data in `consulting.py` |
| `estimate_roi` | Yes | Built-in maths and constants in `roi.py` |
| `summarise_copilot_export` | Yes | The CSV file on your disk |
| `download_copilot_usage` | **No** | Microsoft Graph (`login.microsoftonline.com`, `graph.microsoft.com`) with the app registration in [GRAPH_SETUP.md](GRAPH_SETUP.md) |
| `create_roi_dashboard`, `create_client_deck` | Yes | Logos and templates from files or `assets/`; only an `https://` logo link needs internet, to download it |
| `list_logos`, both resources, the `discovery_call` prompt | Yes | Files and text in the repository |
| Generated dashboards and decks | Yes | Everything is built into the file; only the source links on the Method tab and slide need internet when clicked |

These need internet:

| What | Why |
|------|-----|
| Your AI app (Claude, ChatGPT, Copilot) | The AI runs in the cloud. **Whatever a tool returns is sent to it**, for example an export summary |
| Copilot Studio, Cowork, ChatGPT | Cloud services that reach your server over a tunnel or Azure |
| Getting the Copilot Dashboard export | Downloading it from Viva Insights. Analysing it afterwards is offline |
| `download_copilot_usage` | Signs in to Microsoft Entra ID and downloads reports from Microsoft Graph |
| `https://` logos | Downloaded once, when the dashboard or deck is created |
| Setup and updates | `git clone`/`git pull`, `pip install` |

**Fixed values that don't update themselves:** the exchange rate (1.28 SGD per USD), Microsoft's assisted-hours
factors, the Forrester benchmark and the use-case library are in the code. The MCP never looks them up online, so
update `roi.py` and `consulting.py` when they change.

## What works where

| Feature | Claude Desktop (local) | Microsoft 365 (hosted) |
|---------|------------------------|------------------------|
| Consulting tools (readiness, tier, use cases, ROI) | Yes | Yes |
| Copilot Dashboard export | File path | File path on the server, or attached in Cowork |
| Decks and dashboards | Saved to `output/` | Download link |
| Customer logo | Path, URL, `assets/customers` | URL or `assets/customers` (deploy the logo with the app) |
| PowerPoint template | Path or `assets/templates` | `assets/templates` (deploy the template with the app) |
