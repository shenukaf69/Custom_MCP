---
name: copilot-business-case
description: |
  Builds a Microsoft 365 Copilot readiness assessment, ROI business case and client deck.
  Use when the user asks to "assess Copilot readiness", "build a Copilot business case",
  "calculate Copilot ROI", "analyse our Copilot Dashboard export", "which tier should we use",
  "make a client deck", or "create a Copilot ROI dashboard".
metadata:
  author: Shenuka Fernando
  version: "1.0"
---

# Copilot business case

Guides a consultant from discovery to a client-ready deck, using the Copilot Consultant tools.

## Workflow

1. **Readiness.** Ask five yes/no questions: Copilot licences assigned, data governance (labels and DLP)
   in place, SharePoint permissions reviewed, executive sponsor, change management plan.
   Call `assess_readiness` and show the score and gaps.
2. **Approach.** Ask whether the solution needs custom code, connects to business systems, runs a
   multi-step workflow, and whether the team has developers. Call `recommend_tier`.
   If the industry and function are known, call `find_use_cases`.
3. **Usage data.** If the user attached a Copilot Dashboard export (CSV from Copilot Dashboard >
   Export data > Export by week), call `summarise_copilot_export` with the attached file.
4. **Business case.** Ask for the hourly cost, licence cost per user per month, one-off rollout
   costs and currency (USD or SGD). With an export, call `estimate_roi` using the export's numbers;
   without one, ask for users, adoption and weekly Copilot activity per active user.
5. **Deliverables.** Offer both:
   - `create_client_deck` for a PowerPoint deck (pass every answer collected above, and the
     attached export if there is one).
   - `create_roi_dashboard` for the interactive HTML dashboard.
   Share the download links the tools return.

## Rules

- Never invent licence prices or activity numbers. Ask, or use the export.
- Say that Copilot assisted hours is Microsoft's directional estimate, not a guaranteed saving.
- Use the client's currency: USD or SGD.
