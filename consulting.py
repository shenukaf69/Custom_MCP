"""Consulting logic shared by the MCP tools and the PowerPoint deck.

Reference data (tiers, use cases, industry notes) plus the readiness and tier
rules. Edit the data here to match your own consulting playbook.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

from typing import Literal

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
# Readiness
# ---------------------------------------------------------------------------

# name, weight, what to do when it's missing (shown in the deck's roadmap)
READINESS_CRITERIA = [
    ("has_copilot_licences", "Copilot licences assigned", 20,
     "Assign licences to a pilot group", "Start with 20-50 users in teams with well-understood content."),
    ("data_governance_in_place", "Data governance (labels, DLP) in place", 25,
     "Put baseline labelling and DLP in place",
     "Publish a small set of Microsoft Purview sensitivity labels and a DLP policy for Copilot."),
    ("sharepoint_permissions_reviewed", "SharePoint oversharing / permissions reviewed", 25,
     "Find and contain oversharing",
     "Use SharePoint Advanced Management data access governance reports; restrict sensitive sites while the clean-up runs."),
    ("executive_sponsor", "Executive sponsor identified", 15,
     "Secure an executive sponsor", "Visible leadership use is the strongest driver of adoption."),
    ("change_management_plan", "Change management / adoption plan", 15,
     "Build the adoption plan", "Champions network, role-based training and a prompt library."),
]


def score_readiness(**answers: bool) -> dict:
    """Score readiness out of 100. answers: one bool per READINESS_CRITERIA key."""
    criteria = []
    for key, label, weight, action, detail in READINESS_CRITERIA:
        passed = bool(answers[key])
        criteria.append({"key": key, "label": label, "weight": weight, "passed": passed,
                         "action": action, "detail": detail})
    score = sum(c["weight"] for c in criteria if c["passed"])
    if score >= 80:
        status = "Ready to scale"
    elif score >= 50:
        status = "Ready for a pilot"
    else:
        status = "Foundations needed first"
    return {"score": score, "status": status, "criteria": criteria,
            "gaps": [c for c in criteria if not c["passed"]]}


# ---------------------------------------------------------------------------
# Tier recommendation
# ---------------------------------------------------------------------------

def pick_tier(needs_code: bool, connects_to_business_systems: bool,
              multi_step_workflow: bool, team_has_developers: bool) -> dict:
    """Return the recommended tier, the reason and an optional caveat."""
    if needs_code and team_has_developers:
        tier, reason = "Tier 3", "custom code and a developer team point to a code-first build"
    elif connects_to_business_systems or multi_step_workflow:
        tier, reason = "Tier 2", "system integrations or multi-step processes need Copilot Studio"
    else:
        tier, reason = "Tier 1", "a knowledge-grounded assistant can be built with no code"
    note = ("The scenario needs code but the team has no developers. "
            "Start in Copilot Studio or bring in a partner for Tier 3."
            if needs_code and not team_has_developers else "")
    return {"tier": tier, "reason": reason, "note": note, **TIERS[tier]}
