"""Build the Copilot Cowork plugin package (.zip) for this MCP server.

    python m365/cowork-plugin/build_cowork_plugin.py --url https://<your-app>/mcp \
        --privacy-url https://<site>/privacy --terms-url https://<site>/terms

Then upload dist/copilot-consultant-cowork.zip in the Microsoft 365 admin center
(Manage apps > Upload custom app). See DEPLOYMENT.md.

Uses the Microsoft 365 app manifest v1.28 layout from
https://learn.microsoft.com/microsoft-365/copilot/cowork/cowork-plugin-development

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import argparse
import json
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).parent


def manifest(url: str, auth: str, reference_id: str | None, website: str, privacy: str, terms: str,
             version: str) -> dict:
    authorization = {"type": "None"} if auth == "none" else {"type": "OAuthPluginVault", "referenceId": reference_id}
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.28/MicrosoftTeams.schema.json",
        "manifestVersion": "1.28",
        "version": version,
        # Stable id: the same URL always produces the same id, so updates replace the old package.
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "copilot-consultant:" + url)),
        "developer": {
            "name": "Shenuka INC",
            "websiteUrl": website,
            "privacyUrl": privacy,
            "termsOfUseUrl": terms,
        },
        "name": {"short": "Copilot Consultant", "full": "Copilot Consultant by Shenuka INC"},
        "description": {
            "short": "Copilot readiness, ROI business cases and client decks",
            "full": ("Assess Microsoft 365 Copilot readiness, recommend a build tier, analyse Copilot Dashboard "
                     "exports, calculate ROI with Microsoft's Copilot assisted hours method, and create "
                     "PowerPoint decks and interactive ROI dashboards. Created by Shenuka Fernando."),
        },
        "icons": {"color": "color.png", "outline": "outline.png"},
        "accentColor": "#0D2A52",
        "agentSkills": [{"folder": "./skills/copilot-business-case"}],
        "agentConnectors": [{
            "id": "copilot-consultant-mcp",
            "displayName": "Copilot Consultant",
            "description": "Readiness, tier, use cases, ROI, Copilot Dashboard analysis, decks and dashboards",
            "toolSource": {"remoteMcpServer": {"mcpServerUrl": url, "authorization": authorization}},
        }],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="Public HTTPS MCP endpoint, ending in /mcp")
    p.add_argument("--auth", choices=["none", "oauth"], default="none",
                   help="none (server without MCP_API_KEY) or oauth (needs --reference-id)")
    p.add_argument("--reference-id", help="OAuth client registration ID from Agents Toolkit / Teams Developer Portal")
    p.add_argument("--website-url", default="https://github.com/shenukaf69/Custom_MCP")
    p.add_argument("--privacy-url", required=True)
    p.add_argument("--terms-url", required=True)
    p.add_argument("--version", default="1.0.0")
    a = p.parse_args()
    if not a.url.startswith("https://"):
        p.error("--url must be an https:// address (Cowork requires HTTPS)")
    if a.auth == "oauth" and not a.reference_id:
        p.error("--auth oauth needs --reference-id")

    data = manifest(a.url, a.auth, a.reference_id, a.website_url, a.privacy_url, a.terms_url, a.version)
    (HERE / "manifest.json").write_text(json.dumps(data, indent=2))
    dist = HERE / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / "copilot-consultant-cowork.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(HERE / "manifest.json", "manifest.json")
        z.write(HERE / "color.png", "color.png")
        z.write(HERE / "outline.png", "outline.png")
        for f in sorted((HERE / "skills").rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(HERE).as_posix())
    print(f"Package: {out}\nUpload it in the Microsoft 365 admin center > Manage apps > Upload custom app.")


if __name__ == "__main__":
    main()
