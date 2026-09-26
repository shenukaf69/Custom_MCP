# What's in this repository

Created by Shenuka Fernando. © 2026 Shenuka Fernando. All rights reserved.

## Documentation

| File | What it's for |
|------|---------------|
| `README.md` | Overview: what the MCP does, its tools, how the ROI is calculated, the dashboard and deck |
| `INSTALL.md` | Installing in Claude Desktop, Claude Code, OpenAI Codex, ChatGPT, Copilot Studio, Copilot Cowork and Microsoft 365 Copilot; setting up the Microsoft Graph usage download |
| `TRY_IT.md` | Prompts and PowerShell commands to try every tool, with screenshots of real results |
| `DEPLOYMENT.md` | Running it as a web service (Dev Tunnels or Azure), step-by-step Microsoft 365 setup, networking and offline use |
| `FILES.md` | This file |
| `COPYRIGHT` | Ownership and copyright notice (all rights reserved), and trademark notes |

## The MCP server (Python code)

| File | What it does |
|------|--------------|
| `server.py` | **Start here.** Defines the MCP server and its 10 tools, 2 resources and 1 prompt; the default partner branding (Shenuka INC); logo and template lookup; and web-service mode (`python server.py --http`) with API key, download links and Cowork file attachments |
| `consulting.py` | Consulting knowledge: the three build tiers, the use-case library by function, industry tips, readiness scoring rules and the tier-recommendation rules. Edit this to change your playbook |
| `roi.py` | The ROI maths: Microsoft's Copilot assisted hours method, value, cost, ROI, payback, break-even, the Forrester benchmark and USD/SGD conversion. Also holds constants such as the default exchange rate (1.28) |
| `copilot_export.py` | Reads a Microsoft Copilot Dashboard data export (CSV), matches Microsoft's metric names, and calculates assisted hours per week, organisation, function and app |
| `graph_usage.py` | Downloads the Microsoft 365 Copilot usage reports (v2) from Microsoft Graph with an Entra ID app registration, and summarises them. Reads the app's ID and secret from environment variables |
| `dashboard.py` | Builds the interactive HTML dashboard (Business case, Usage & adoption, Method & sources tabs; sliders, scenarios, currency switch, logo upload) |
| `deck.py` | Builds the client-facing PowerPoint deck (native charts, clickable agenda, speaker notes, optional template) |
| `demo.py` | Quick test without an AI app: prints results and builds a sample dashboard and deck in `output/` |
| `requirements.txt` | Python libraries to install: `mcp[cli]` (the MCP SDK) and `python-pptx` (PowerPoint) |

## Tools, resources and prompts (defined in `server.py`)

| Name | Type | What it does |
|------|------|--------------|
| `assess_readiness` | Tool | Readiness score out of 100 with gaps |
| `recommend_tier` | Tool | Agent Builder, Copilot Studio or Azure AI Foundry |
| `find_use_cases` | Tool | Agent ideas by industry and function |
| `plan_build_along` | Tool | Build-Along workshop outline |
| `estimate_roi` | Tool | ROI in USD and SGD using Microsoft's assisted hours method |
| `summarise_copilot_export` | Tool | Real adoption and activity from a Copilot Dashboard export |
| `download_copilot_usage` | Tool | Downloads Copilot usage reports from Microsoft Graph to Downloads |
| `create_roi_dashboard` | Tool | Interactive HTML dashboard |
| `create_client_deck` | Tool | PowerPoint client deck |
| `list_logos` | Tool | Saved partner and customer logos |
| `consultant://tiers` | Resource | Tier overview |
| `consultant://copilot-export-guide` | Resource | How to export Copilot Dashboard data |
| `discovery_call` | Prompt | Discovery questions for a client call |

## Branding and templates (`assets/`)

| Path | What goes there |
|------|-----------------|
| `assets/partners/shenuka-inc.png` | The default partner logo, shown as "Prepared by" |
| `assets/partners/` | Other partner logos, named after the partner |
| `assets/customers/` | Customer logos, named after the customer (e.g. `contoso.png`), picked up automatically |
| `assets/templates/` | PowerPoint templates (widescreen `.pptx`/`.potx`) for `create_client_deck` |

## Samples and screenshots

| Path | What it is |
|------|------------|
| `samples/sample_copilot_export_SYNTHETIC.csv` | Made-up Copilot Dashboard export (240 people, 26 weeks) for testing. Not real data |
| `samples/Sample_Copilot_Deck_Contoso.pptx` | Example deck built from the synthetic export |
| `samples/Demo_Client_Copilot_ROI (2).html` | Example dashboard saved from the browser |
| `docs/screenshots/` | Screenshots of real tests in Claude Desktop, used in `TRY_IT.md` and `INSTALL.md` |
| `images/` | Dashboard screenshots used in `README.md` |

## Microsoft 365 and hosting

| Path | What it's for |
|------|---------------|
| `Dockerfile`, `.dockerignore` | Build a container to run the server in Azure Container Apps (see `DEPLOYMENT.md`) |
| `m365/cowork-plugin/build_cowork_plugin.py` | Builds the Copilot Cowork plugin package (.zip) for your server URL |
| `m365/cowork-plugin/skills/copilot-business-case/SKILL.md` | The Cowork skill that teaches Cowork the consulting workflow using these tools |
| `m365/cowork-plugin/color.png`, `outline.png` | Plugin icons (192×192 colour, 32×32 outline) |

## Created when you run it (not in the repository)

| Path | What it is |
|------|------------|
| `.venv/` | Your Python environment, created by `python -m venv .venv` |
| `output/` | Generated dashboards (`.html`) and decks (`.pptx`) |
| `m365/cowork-plugin/dist/`, `manifest.json` | The built Cowork package |
| `__pycache__/` | Python's cache; safe to delete |
