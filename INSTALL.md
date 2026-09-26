# Install the Copilot Consultant MCP in your AI apps

Created by Shenuka Fernando. © 2026 Shenuka Fernando. All rights reserved.

| App | How it connects | What you need first |
|-----|-----------------|---------------------|
| [Claude Desktop](#a-claude-desktop) | Starts the MCP on your PC (STDIO) | [Setup on your PC](#setup-on-your-pc) |
| [Claude Code](#b-claude-code) | Starts the MCP on your PC (STDIO) | Setup on your PC |
| [OpenAI Codex app](#c-openai-codex-app-local) | Starts the MCP on your PC (STDIO) | Setup on your PC |
| [ChatGPT (web and desktop app)](#d-chatgpt-web-and-desktop-app) | Remote HTTPS URL, in Developer mode | A public HTTPS address ([DEPLOYMENT.md](DEPLOYMENT.md)) |
| [Copilot Studio](#e-copilot-studio) | Remote HTTPS URL | A public HTTPS address |
| [Copilot Cowork](#f-copilot-cowork) | Plugin package pointing to a remote HTTPS URL | A public HTTPS address + Microsoft 365 admin |
| [Microsoft 365 Copilot agents](#g-microsoft-365-copilot-agents-and-agent-builder) | Via Copilot Studio or a declarative agent | A public HTTPS address |
| [Automatic Copilot usage download](GRAPH_SETUP.md) | Optional add-on for any of the above | An Entra ID app registration in the client's tenant ([GRAPH_SETUP.md](GRAPH_SETUP.md)) |

**Which URL?** Local apps (Claude Desktop, Claude Code, Codex) don't use a URL: they start `server.py` themselves.
Cloud apps (ChatGPT, Copilot Studio, Cowork) need `https://<public address>/mcp` from a Dev Tunnel or Azure,
because they can't reach `localhost` on your PC. See [DEPLOYMENT.md](DEPLOYMENT.md#step-2-give-it-a-public-https-address).

App menus change often. If a label below doesn't match what you see, follow the linked vendor docs.

---

## Setup on your PC

Windows PowerShell:

```powershell
cd C:\Users\<you>
git clone https://github.com/shenukaf69/Custom_MCP.git
cd Custom_MCP
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python demo.py
```

`demo.py` should print results and open a sample dashboard. If PowerShell says running scripts is disabled, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

To update later: `cd` into the folder, activate `.venv`, `git pull`, `pip install -r requirements.txt`, then
restart your AI app.

---

## A. Claude Desktop

1. In Claude Desktop, go to **Settings > Developer > Edit Config**. This opens the folder with
   `claude_desktop_config.json`. Open that file in Notepad.
2. **Save a backup copy first** (File > Save As, for example `claude_desktop_config.backup.json`), then reopen the
   original.
3. Add the `mcpServers` block **right after the first `{`**, keeping everything else. Use your own path and keep
   the double backslashes:

   ```json
   {
     "mcpServers": {
       "copilot-consultant": {
         "command": "C:\\Users\\<you>\\Custom_MCP\\.venv\\Scripts\\python.exe",
         "args": ["C:\\Users\\<you>\\Custom_MCP\\server.py"]
       }
     },
     "...your existing settings stay here...": "..."
   }
   ```

   Note the comma after the `mcpServers` block's closing `}`. A missing comma makes the file invalid.
4. **Fully quit Claude** (right-click the tray icon > **Quit**) and reopen it.
5. **Settings > Developer** should show **copilot-consultant** as **Running**.
6. In a new chat: *"What tools does copilot-consultant have?"* It should list 10 tools. Click **Allow** when Claude
   first uses a tool.

![Claude Desktop showing copilot-consultant running](docs/screenshots/01-claude-desktop-mcp-running.png)

Troubleshooting: select **View logs** on that Settings page, or open `%APPDATA%\Claude\logs\` (files starting with
`mcp`). `ModuleNotFoundError` means the `command` path isn't the `python.exe` inside `.venv`.

## B. Claude Code

```powershell
claude mcp add copilot-consultant -- C:\Users\<you>\Custom_MCP\.venv\Scripts\python.exe C:\Users\<you>\Custom_MCP\server.py
```

Then start `claude` and ask *"What tools does copilot-consultant have?"*.

## C. OpenAI Codex app (local)

The Codex app can start local (STDIO) MCP servers like Claude Desktop does.

1. Open the **gear menu** > **MCP servers** > **Add server**.
2. Name: `copilot-consultant`. Type: **STDIO**.
3. Command: `C:\Users\<you>\Custom_MCP\.venv\Scripts\python.exe`, with the argument
   `C:\Users\<you>\Custom_MCP\server.py`.
4. Save, then ask Codex to list the copilot-consultant tools.

([Codex: Model Context Protocol](https://developers.openai.com/codex/mcp))

## D. ChatGPT (web and desktop app)

ChatGPT connects to **remote** MCP servers only, through **Developer mode**. It can't start `server.py` on your PC.

**What you need**
- A public HTTPS address for the server ([DEPLOYMENT.md Step 2](DEPLOYMENT.md#step-2-give-it-a-public-https-address)).
- **Run the server without `MCP_API_KEY`.** ChatGPT offers OAuth or no authentication, not API keys. For client
  data, use OAuth (Entra ID) instead; see [DEPLOYMENT.md](DEPLOYMENT.md#production-sign-in-oauth).
- A plan that supports it. According to OpenAI, full MCP support (including tools that create files) is on
  **Business, Enterprise and Edu**; **Pro** is limited to read/fetch tools. Check OpenAI's page for your plan.

**Steps**
1. Business, Enterprise or Edu only: a workspace admin turns on Developer mode in **Workspace settings >
   Permissions & roles** (Developer mode / create custom MCP connectors).
2. In ChatGPT, open **Settings** and turn on **Developer mode** (under Security and login, or Apps > Advanced
   settings, depending on version).
3. Go to **Apps** (or **Plugins**) and select **+ / Create**. Enter:
   - Name: `Copilot Consultant`
   - MCP server URL: `https://<public address>/mcp` (include `/mcp`)
   - Authentication: **No authentication** (or OAuth)
4. Create the app. In a chat, pick it from the composer's **Developer mode** tools and ask:
   *"Assess Copilot readiness: licences yes, DLP no, SharePoint reviewed no, sponsor yes, change plan yes."*
5. Generated decks and dashboards come back as download links.

Only connect servers you trust; developer mode gives the model tools that can act. The same app appears in the
ChatGPT desktop app and on the web because it's saved to your account. OpenAI also offers a **Secure MCP Tunnel**
for servers on private networks.

([Developer mode and MCP apps in ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt),
[ChatGPT Developer mode](https://developers.openai.com/api/docs/guides/developer-mode),
[Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels.md))

## E. Copilot Studio

Needs a public HTTPS address. Set `MCP_API_KEY` on the server for this one.

**Standard harness ("classic"):** turn on generative orchestration, then **Tools > Add a tool > New tool > Model
Context Protocol**. Enter the name, description, `https://<public address>/mcp`, and **API key** authentication
(Header, name `x-api-key`). Create the connection, **Add to agent**, and test.

**GitHub Copilot harness (preview):** **Build** tab > **Tools** > **Add** > **Model Context Protocol (MCP)**, same
details, then **Save** and test on the **Preview** tab.

**Publish to Teams and Microsoft 365 Copilot:** **Publish** > **Channels** > **Teams and Microsoft 365 Copilot**.

Full steps: [DEPLOYMENT.md Steps 3 to 5](DEPLOYMENT.md#step-3-copilot-studio-standard-harness-classic).

## F. Copilot Cowork

Needs a public HTTPS address and a Microsoft 365 admin. Run the server **without** `MCP_API_KEY` (Cowork doesn't
support API keys) or with OAuth.

```powershell
python m365/cowork-plugin/build_cowork_plugin.py --url https://<public address>/mcp --privacy-url https://<site>/privacy --terms-url https://<site>/terms
```

Upload `m365/cowork-plugin/dist/copilot-consultant-cowork.zip` in the **Microsoft 365 admin center > Manage apps >
Upload custom app** (**…** > **Add agent**), then in **Cowork > Sources & Skills > Plugins** add **Copilot
Consultant**. Attach a Copilot Dashboard export in Cowork and the tools read it directly.

Full steps: [DEPLOYMENT.md Step 6](DEPLOYMENT.md#step-6-copilot-cowork).

## G. Microsoft 365 Copilot agents and Agent Builder

Agent Builder can't add MCP servers. Use a **Copilot Studio agent published to Microsoft 365 Copilot** (section E),
or a **declarative agent from Microsoft 365 Agents Toolkit** in VS Code (**Declarative Agent > Add an Action >
Start with an MCP Server**). See [DEPLOYMENT.md Step 7](DEPLOYMENT.md#step-7-declarative-agents-the-alternative-to-agent-builder).

---

## H. Automatic Copilot usage download (Microsoft Graph)

Optional. The `download_copilot_usage` tool downloads a client's Microsoft 365 Copilot usage reports (v2) from
Microsoft Graph into your Downloads folder. An admin signs in in the browser with their own account and MFA, and no
secret is stored.

**Full step-by-step guide: [GRAPH_SETUP.md](GRAPH_SETUP.md).** In short:

1. **The client's admin** creates an app registration in the Microsoft Entra admin center: redirect URI
   `http://localhost` (mobile & desktop), **delegated** `Reports.Read.All` with admin consent, assignment
   required, and the **Reports Reader** role for you. They send you the **tenant ID** and **client ID**.
   ([Details](GRAPH_SETUP.md#step-1-the-clients-admin-sets-up-access), and an
   [email you can send them](GRAPH_SETUP.md#ask-the-clients-admin).)
2. **On your PC**, save the two IDs as user environment variables, run `pip install -r requirements.txt`, and fully
   restart Claude ([details](GRAPH_SETUP.md#step-2-tell-the-mcp-about-the-tenant)):

   ```powershell
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_TENANT_ID", "<tenant-id>", "User")
   [Environment]::SetEnvironmentVariable("COPILOT_GRAPH_CLIENT_ID", "<client-id>", "User")
   ```
3. **Ask Claude:** *"Download Copilot usage for the last 28 days."* Then sign in when the Microsoft page opens.
