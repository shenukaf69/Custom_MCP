"""Copilot ROI maths, following Microsoft's published "Copilot assisted hours" method.

Source: Microsoft Copilot Dashboard (Viva Insights), "Details on the Copilot
assisted hours metric":
https://learn.microsoft.com/viva/insights/org-team-insights/copilot-dashboard#impact

    Copilot assisted hours = meeting hours summarised or recapped
                           + search & summary actions x 6 minutes
                           + creation actions x 6 minutes
    Copilot assisted value = assisted hours x average hourly rate
                             (Microsoft's default is $72, from US BLS data)

The 6-minute factors come from Microsoft's research with 163 and 147 knowledge
workers. Microsoft describes assisted hours as a broad, directional estimate.

On top of that, this module adds the standard business-case steps Microsoft's
dashboard does not do: annualising, licence and rollout costs, ROI and payback.
The optional realisation rate is a consultant's conservatism factor and is NOT
part of Microsoft's method (keep it at 1.0 to match Microsoft exactly).

The maths works in any currency: all money inputs just need to be in the same one.

dashboard.py repeats this maths in JavaScript. Change both together.

Created by Shenuka Fernando. Copyright (c) 2026 Shenuka Fernando. All rights reserved.
"""

from dataclasses import dataclass

WORKING_WEEKS = 46          # 52 weeks minus holidays, bank holidays and sick days
MINUTES_PER_ACTION = 6      # Microsoft's assistance factor for search/summary and creation actions
MICROSOFT_DEFAULT_HOURLY_USD = 72
FTE_HOURS_PER_YEAR = WORKING_WEEKS * 37.5

# Currencies. Dashboards can switch between them; the rate can be edited on the page.
# Default is the mid-market rate in September 2026 (XE 1.2777, Wise 1.282). Update it as rates move.
CURRENCIES = {"USD": "US$", "SGD": "S$"}
DEFAULT_SGD_PER_USD = 1.28


def to_usd(amount: float, currency: str, sgd_per_usd: float = DEFAULT_SGD_PER_USD) -> float:
    return amount / sgd_per_usd if currency == "SGD" else amount


def from_usd(amount: float, currency: str, sgd_per_usd: float = DEFAULT_SGD_PER_USD) -> float:
    return amount * sgd_per_usd if currency == "SGD" else amount

# Forrester "New Technology: Projected Total Economic Impact of Microsoft 365
# Copilot for SMB" (commissioned by Microsoft, October 2024): 3-year projected ROI.
BENCHMARK = {"name": "Forrester projected TEI, Microsoft 365 Copilot for SMB (commissioned by Microsoft)",
             "low": 132, "medium": 243, "high": 353}


@dataclass
class RoiResult:
    # Inputs
    users: int
    hourly_cost: float
    licence_cost_per_user_per_month: float
    meeting_hours_per_week: float
    search_actions_per_week: float
    creation_actions_per_week: float
    adoption_rate: float
    realisation_rate: float
    one_off_costs: float

    # Microsoft's method (per year)
    active_users: float
    assisted_hours_per_user_per_week: float
    hours_meetings: float
    hours_search: float
    hours_creation: float
    assisted_hours: float
    assisted_value: float

    # Business case
    potential_value: float      # if every licensed user were active
    realised_value: float       # assisted value x realisation rate
    licence_cost: float         # yearly
    total_cost: float           # year one: licences + one-off costs
    net_benefit: float          # year one
    roi_pct: float              # year one
    roi_3yr_pct: float
    payback_months: float | None
    break_even_minutes: float   # per active user per week
    fte_equivalent: float


def calculate_roi(
    users: int,
    hourly_cost: float,
    licence_cost_per_user_per_month: float,
    meeting_hours_per_week: float,
    search_actions_per_week: float,
    creation_actions_per_week: float,
    adoption_rate: float = 1.0,
    realisation_rate: float = 1.0,
    one_off_costs: float = 0.0,
) -> RoiResult:
    """Calculate the Copilot business case. Raises ValueError on impossible inputs."""
    if users <= 0 or hourly_cost <= 0:
        raise ValueError("users and hourly_cost must be greater than zero.")
    if not (0 < adoption_rate <= 1 and 0 < realisation_rate <= 1):
        raise ValueError("adoption_rate and realisation_rate must be between 0 and 1, e.g. 0.7 for 70%.")
    if min(meeting_hours_per_week, search_actions_per_week, creation_actions_per_week,
           licence_cost_per_user_per_month, one_off_costs) < 0:
        raise ValueError("activity counts, licence cost and one-off costs cannot be negative.")

    active = users * adoption_rate
    per_action_hours = MINUTES_PER_ACTION / 60
    yearly = active * WORKING_WEEKS
    hours_meetings = meeting_hours_per_week * yearly
    hours_search = search_actions_per_week * per_action_hours * yearly
    hours_creation = creation_actions_per_week * per_action_hours * yearly
    assisted_hours = hours_meetings + hours_search + hours_creation
    assisted_value = assisted_hours * hourly_cost

    realised_value = assisted_value * realisation_rate
    potential_value = assisted_value / adoption_rate
    licence_cost = users * licence_cost_per_user_per_month * 12
    total_cost = licence_cost + one_off_costs
    net_benefit = realised_value - total_cost
    roi_pct = net_benefit / total_cost * 100 if total_cost else float("inf")
    cost_3yr = licence_cost * 3 + one_off_costs
    roi_3yr_pct = (realised_value * 3 - cost_3yr) / cost_3yr * 100 if cost_3yr else float("inf")

    monthly_net = (realised_value - licence_cost) / 12
    payback_months = one_off_costs / monthly_net if monthly_net > 0 else None
    break_even_hours = licence_cost / (active * WORKING_WEEKS * hourly_cost * realisation_rate)

    return RoiResult(
        users=users, hourly_cost=hourly_cost,
        licence_cost_per_user_per_month=licence_cost_per_user_per_month,
        meeting_hours_per_week=meeting_hours_per_week,
        search_actions_per_week=search_actions_per_week,
        creation_actions_per_week=creation_actions_per_week,
        adoption_rate=adoption_rate, realisation_rate=realisation_rate, one_off_costs=one_off_costs,
        active_users=active,
        assisted_hours_per_user_per_week=assisted_hours / yearly,
        hours_meetings=hours_meetings, hours_search=hours_search, hours_creation=hours_creation,
        assisted_hours=assisted_hours, assisted_value=assisted_value,
        potential_value=potential_value, realised_value=realised_value,
        licence_cost=licence_cost, total_cost=total_cost, net_benefit=net_benefit,
        roi_pct=roi_pct, roi_3yr_pct=roi_3yr_pct, payback_months=payback_months,
        break_even_minutes=break_even_hours * 60,
        fte_equivalent=assisted_hours * realisation_rate / FTE_HOURS_PER_YEAR,
    )
