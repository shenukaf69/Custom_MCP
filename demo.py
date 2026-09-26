"""Quick test without any AI app: builds a sample dashboard and opens it in your browser.

    python demo.py

It uses the synthetic Copilot Dashboard export in samples/ and SGD pricing, and also
builds a PowerPoint deck in output/.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

import webbrowser
from pathlib import Path

from server import create_client_deck, create_roi_dashboard, estimate_roi, summarise_copilot_export

HERE = Path(__file__).parent
SAMPLE = HERE / "samples" / "sample_copilot_export_SYNTHETIC.csv"

print("1) Summarise the sample Copilot Dashboard export\n")
print(summarise_copilot_export(str(SAMPLE)))

print("\n2) Estimate ROI from typed-in numbers (SGD)\n")
print(estimate_roi(users=200, hourly_cost=92, licence_cost_per_user_per_month=38.4,
                   meeting_hours_per_week=1, search_actions_per_week=10,
                   creation_actions_per_week=5, adoption_rate=0.7,
                   one_off_costs=50000, currency="SGD"))

print("\n3) Build the dashboard from the sample export\n")
result = create_roi_dashboard(client_name="Demo Client", hourly_cost=92,
                              licence_cost_per_user_per_month=38.4,
                              copilot_export_csv=str(SAMPLE), one_off_costs=50000,
                              currency="SGD", prepared_by="Shenuka Fernando")
print(result)

print("\n4) Build the client PowerPoint deck\n")
print(create_client_deck(client_name="Demo Client", currency="SGD", prepared_by="Shenuka Fernando",
                         has_copilot_licences=True, data_governance_in_place=False,
                         sharepoint_permissions_reviewed=False, executive_sponsor=True, change_management_plan=True,
                         needs_code=False, connects_to_business_systems=True, multi_step_workflow=True,
                         team_has_developers=False, industry="Retail", function="Operations",
                         hourly_cost=92, licence_cost_per_user_per_month=38.4,
                         copilot_export_csv=str(SAMPLE), one_off_costs=50000))

path = HERE / "output" / "roi_dashboard_Demo_Client.html"
if path.is_file():
    webbrowser.open(path.resolve().as_uri())
    print("\nOpened the dashboard in your browser.")
