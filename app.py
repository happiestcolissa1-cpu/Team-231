import json
import copy
import datetime
from decimal import Decimal, ROUND_HALF_UP
import math
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Career Venture Lab | Team 23 (NUR-4)",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# CONSTANTS & HANDBOOK DEFAULTS (NUR-4 / AP Statistics)
# ---------------------------------------------------------
TEAM_ID = "Team 23"
COURSE = "AP Statistics"
PATHWAY_ID = "NUR-4"
BUSINESS_NAME = "Nurse-Led Health Education Simulation"

DEFAULT_STATE = {
    "team_id": TEAM_ID,
    "course": COURSE,
    "pathway_id": PATHWAY_ID,
    "snapshot_id": "SNAP-001",
    "state_version": 1,
    "simulation_date": "2027-01-31",
    "base_period": "monthly",
    "working_days": 20,
    "currency": "USD",
    "level_by_skill": {
        "AP Statistics - Study Design & Inference": "Advanced"
    },
    "assumptions": [
        "Fictional educational health workshops only; zero diagnosis, clinical care, or real patient data.",
        "Payment collected and per-seat variable costs incurred ONLY for attended seats.",
        "No backlog by default; unserved demand is lost demand.",
        "Borrowing, interest, refunds, depreciation, and sales tax are disabled (0) at baseline."
    ],
    "sources": [
        "Career Venture Lab Student Handbook (November 2026) - Pathway NUR-4 & AP Statistics Adapter"
    ],
    "offerings": [
        {
            "offering_id": "OFF-01",
            "name": "General wellness education workshop",
            "unit": "workshop_seat",
            "price": 25.00,
            "demand_rule": "D0=80 baseline monthly requests",
            "capacity_rule": "min(floor(staff_hours / hours_per_unit), venue_seats)"
        },
        {
            "offering_id": "OFF-02",
            "name": "Caregiver information session (Secondary - future allocation)",
            "unit": "workshop_seat",
            "price": 25.00,
            "demand_rule": "Separate allocation required",
            "capacity_rule": "Separate allocation required"
        },
        {
            "offering_id": "OFF-03",
            "name": "First-aid awareness demonstration (Secondary - future allocation)",
            "unit": "workshop_seat",
            "price": 25.00,
            "demand_rule": "Separate allocation required",
            "capacity_rule": "Separate allocation required"
        }
    ],
    "funding": {
        "owner_contribution": 6000.00,
        "equipment_assets": 1500.00,
        "pre_opening_expense": 500.00,
        "opening_inventory": 0.00,
        "opening_cash": 4000.00,
        "opening_retained_earnings": -500.00,
        "loan_principal": 0.00,
        "interest_rate": 0.00
    },
    "inputs": {
        "base_price": 25.00,
        "D0": 80,
        "staff_hours": 30.0,
        "hours_per_unit": 0.5,
        "venue_seats": 60,
        "no_show_rate": 0.00,
        "satisfaction_mean": 4.0,
        "random_seed": 2027,
        "refund_amount": 0.00,
        "loan_principal_new": 0.00,
        "interest_expense": 0.00,
        "additional_capex": 0.00
    },
    "cost_lines": {
        "variable_per_unit": {
            "educator_delivery": 2.00,
            "materials": 2.00,
            "cleaning_consumables": 1.00
        },
        "fixed_monthly": {
            "venue": 250.00,
            "scheduling_software": 100.00,
            "accessibility_support": 200.00,
            "admin_insurance_assumption": 150.00
        },
        "marketing_monthly": 0.00
    },
    "capacity": {},
    "ledger": [],
    "processed_run_ids": [],
    "campaigns": [],
    "decisions": []
}

MONTHLY_FIXTURE_ROWS = [
    {"month": "2027-01", "requested": 80, "capacity_override": 60, "ad_cost": 0.00},
    {"month": "2027-02", "requested": 88, "capacity_override": 60, "ad_cost": 100.00},
    {"month": "2027-03", "requested": 72, "capacity_override": 45, "ad_cost": 0.00}
]


def to_money(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_nur_month(
    requested: int,
    price: float,
    staff_hours: float,
    hours_per_unit: float,
    venue_seats: int,
    no_show_rate: float,
    var_cost_unit: float,
    fixed_cost_total: float,
    ad_cost: float,
    opening_cash: float,
    capacity_override: int | None = None,
    refund_amount: float = 0.0,
    interest_expense: float = 0.0,
    principal_repayment: float = 0.0,
    additional_capex: float = 0.0,
    new_owner_cash: float = 0.0,
    loan_cash: float = 0.0
) -> dict:
    """Deterministic NUR monthly simulation engine (Handbook pp. 83-85)."""
    if requested < 0 or price < 0 or staff_hours < 0 or hours_per_unit <= 0 or venue_seats < 0:
        raise ValueError("Invalid negative or zero input parameter.")
    if not (0.0 <= no_show_rate <= 1.0):
        raise ValueError("no_show_rate must be between 0 and 1.")

    staff_cap = math.floor(staff_hours / hours_per_unit)
    derived_capacity = min(staff_cap, int(venue_seats))
    effective_capacity = int(capacity_override) if capacity_override is not None else derived_capacity

    booked = min(int(requested), effective_capacity)
    unserved_demand = max(0, int(requested) - booked)
    attended = math.floor(booked * (1.0 - float(no_show_rate)))
    no_shows = booked - attended
    sold = attended

    d_price = to_money(price)
    d_var_unit = to_money(var_cost_unit)
    d_fixed = to_money(fixed_cost_total)
    d_ad = to_money(ad_cost)
    d_open_cash = to_money(opening_cash)
    d_refund = to_money(refund_amount)
    d_interest = to_money(interest_expense)
    d_principal = to_money(principal_repayment)
    d_capex = to_money(additional_capex)
    d_new_owner = to_money(new_owner_cash)
    d_loan_cash = to_money(loan_cash)

    revenue = (d_price * Decimal(sold)) - d_refund
    variable_expense = d_var_unit * Decimal(sold)
    total_operating_expense = variable_expense + d_fixed + d_ad
    operating_profit = revenue - total_operating_expense
    net_profit = operating_profit - d_interest

    ending_cash = (
        d_open_cash
        + revenue
        - variable_expense
        - d_fixed
        - d_ad
        - d_interest
        - d_principal
        - d_capex
        + d_new_owner
        + d_loan_cash
    )

    educator_utilization = (booked * hours_per_unit / staff_hours * 100.0) if staff_hours > 0 else 0.0
    venue_utilization = (booked / venue_seats * 100.0) if venue_seats > 0 else 0.0

    return {
        "staff_capacity": staff_cap,
        "venue_capacity": int(venue_seats),
        "derived_capacity": derived_capacity,
        "effective_capacity": effective_capacity,
        "requested": int(requested),
        "booked": booked,
        "unserved_demand": unserved_demand,
        "no_shows": no_shows,
        "attended": attended,
        "sold": sold,
        "revenue": float(revenue),
        "variable_expense": float(variable_expense),
        "fixed_expense": float(d_fixed),
        "marketing_expense": float(d_ad),
        "total_expense": float(total_operating_expense),
        "operating_profit": float(operating_profit),
        "net_profit": float(net_profit),
        "opening_cash": float(d_open_cash),
        "ending_cash": float(ending_cash),
        "educator_utilization_pct": round(educator_utilization, 2),
        "venue_utilization_pct": round(venue_utilization, 2)
    }


def generate_shared_experiment(seed: int = 2027) -> pd.DataFrame:
    """Handbook p. 72 shared synthetic experiment generator."""
    rng = np.random.default_rng(seed)
    group = np.array(["A"] * 40 + ["B"] * 40)
    success = np.r_[
        rng.permutation([1] * 12 + [0] * 28),
        rng.permutation([1] * 20 + [0] * 20)
    ]
    experiment = pd.DataFrame({
        "prospect_id": [f"P{i:03}" for i in range(1, 81)],
        "message": group,
        "converted": success
    })
    experiment = experiment.iloc[rng.permutation(80)].reset_index(drop=True)
    return experiment


def compute_ap_stats_metrics(df: pd.DataFrame) -> dict:
    """Exact AP Statistics two-proportion calculations (Handbook p. 71)."""
    grp_a = df[df["message"] == "A"]["converted"]
    grp_b = df[df["message"] == "B"]["converted"]
    n_a, n_b = len(grp_a), len(grp_b)
    x_a, x_b = int(grp_a.sum()), int(grp_b.sum())
    p_a = x_a / n_a
    p_b = x_b / n_b
    diff = p_b - p_a

    se_unpooled = math.sqrt((p_a * (1 - p_a) / n_a) + (p_b * (1 - p_b) / n_b))
    z_crit = 1.959963984540054
    ci_low = diff - z_crit * se_unpooled
    ci_high = diff + z_crit * se_unpooled

    p_pool = (x_a + x_b) / (n_a + n_b)
    se_pooled = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))
    z_stat = diff / se_pooled if se_pooled > 0 else 0.0
    # Two-sided normal p-value using math.erfc
    p_val = math.erfc(abs(z_stat) / math.sqrt(2.0))

    return {
        "n_a": n_a, "x_a": x_a, "p_a": round(p_a, 6),
        "n_b": n_b, "x_b": x_b, "p_b": round(p_b, 6),
        "diff": round(diff, 6),
        "se_unpooled": round(se_unpooled, 6),
        "ci_95": (round(ci_low, 4), round(ci_high, 4)),
        "p_pool": round(p_pool, 6),
        "se_pooled": round(se_pooled, 6),
        "z_stat": round(z_stat, 5),
        "p_val": round(p_val, 5)
    }


def validate_snapshot_import(raw_json: str, expected_team: str, current_version: int) -> tuple[bool, str, dict | None]:
    """Validate imported snapshot JSON per Data Contract (Handbook p. 58)."""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON syntax: {exc}", None

    required_keys = [
        "team_id", "course", "pathway_id", "snapshot_id", "state_version",
        "simulation_date", "funding", "inputs", "cost_lines", "ledger"
    ]
    missing = [k for k in required_keys if k not in data]
    if missing:
        return False, f"Rejected: Missing required fields: {', '.join(missing)}", None

    if data.get("team_id") != expected_team:
        return False, f"Rejected: Wrong team_id '{data.get('team_id')}'. Expected '{expected_team}'.", None

    imported_ver = data.get("state_version")
    if not isinstance(imported_ver, int) or imported_ver < current_version:
        return (
            False,
            f"Rejected: Stale state_version ({imported_ver}). Current simulation is at v{current_version}.",
            None
        )

    # Check nonnegative inputs
    inp = data.get("inputs", {})
    if inp.get("base_price", 0) <= 0 or inp.get("D0", 0) < 0 or inp.get("staff_hours", 0) < 0 or inp.get("venue_seats", 0) < 0:
        return False, "Rejected: Numeric inputs failed nonnegativity/positivity rules.", None

    # Validate unique transaction IDs in ledger
    tx_ids = [row.get("transaction_id") for row in data.get("ledger", [])]
    if len(tx_ids) != len(set(tx_ids)):
        return False, "Rejected: Duplicate transaction_id detected in ledger.", None

    return True, f"Valid snapshot '{data.get('snapshot_id')}' (v{imported_ver}) ready for approval.", data


def record_ledger_step(state: dict, run_id: str, sim_date: str, result: dict, mode_label: str) -> tuple[bool, str]:
    """Append dated ledger entries with duplicate run_id protection."""
    if run_id in state["processed_run_ids"]:
        return False, f"Duplicate run_id '{run_id}' blocked. No new transactions created."

    v_next = state["state_version"] + 1
    tx_base = len(state["ledger"]) + 1

    entries = [
        {
            "transaction_id": f"TX-{tx_base:04d}",
            "run_id": run_id,
            "date": sim_date,
            "event_type": "SALE_ATTENDED",
            "category": "Revenue",
            "amount": result["revenue"],
            "quantity": result["sold"],
            "unit_price": state["inputs"]["base_price"],
            "offering_id": "OFF-01",
            "campaign_id": None,
            "financing_type": "Operating",
            "mode": mode_label,
            "state_version": v_next
        },
        {
            "transaction_id": f"TX-{tx_base+1:04d}",
            "run_id": run_id,
            "date": sim_date,
            "event_type": "VARIABLE_COST",
            "category": "Variable Expense",
            "amount": -result["variable_expense"],
            "quantity": result["sold"],
            "unit_price": round(result["variable_expense"] / result["sold"], 2) if result["sold"] > 0 else 0.0,
            "offering_id": "OFF-01",
            "campaign_id": None,
            "financing_type": "Operating",
            "mode": mode_label,
            "state_version": v_next
        },
        {
            "transaction_id": f"TX-{tx_base+2:04d}",
            "run_id": run_id,
            "date": sim_date,
            "event_type": "FIXED_COST",
            "category": "Fixed Expense",
            "amount": -result["fixed_expense"],
            "quantity": 1,
            "unit_price": result["fixed_expense"],
            "offering_id": None,
            "campaign_id": None,
            "financing_type": "Operating",
            "mode": mode_label,
            "state_version": v_next
        }
    ]
    if result["marketing_expense"] > 0:
        entries.append({
            "transaction_id": f"TX-{tx_base+3:04d}",
            "run_id": run_id,
            "date": sim_date,
            "event_type": "CAMPAIGN_EXPENSE",
            "category": "Marketing Expense",
            "amount": -result["marketing_expense"],
            "quantity": 1,
            "unit_price": result["marketing_expense"],
            "offering_id": None,
            "campaign_id": f"CMP-{run_id}",
            "financing_type": "Operating",
            "mode": mode_label,
            "state_version": v_next
        })

    state["ledger"].extend(entries)
    state["processed_run_ids"].append(run_id)
    state["state_version"] = v_next
    state["simulation_date"] = sim_date
    state["capacity"] = {
        "staff_capacity": result["staff_capacity"],
        "venue_capacity": result["venue_capacity"],
        "effective_capacity": result["effective_capacity"]
    }
    return True, f"Recorded run '{run_id}' -> Advanced to state_version v{v_next}."


# ---------------------------------------------------------
# INITIALIZE SESSION STATE
# ---------------------------------------------------------
if "sim_state" not in st.session_state:
    st.session_state.sim_state = copy.deepcopy(DEFAULT_STATE)

state = st.session_state.sim_state

# ---------------------------------------------------------
# SIDEBAR: STAGE STATUS, SAVE/LOAD & LEVEL CONTROLS
# ---------------------------------------------------------
with st.sidebar:
    st.title("Career Venture Lab")
    st.caption(f"**{state['team_id']}** | **{state['pathway_id']}** | **{state['course']}**")
    st.info(
        f"**Build Phase:** Stage 1 (Core Engine)\n\n"
        f"**State Version:** `v{state['state_version']}` | **Date:** `{state['simulation_date']}`\n\n"
        f"**Challenge Level:** `{state['level_by_skill']['AP Statistics - Study Design & Inference']}`"
    )

    st.subheader("Stage Implementation Status")
    st.markdown(
        "- **Stage 1 (Active):** Inputs, Deterministic Math, Dated Ledger, JSON/CSV Save & Load, Fixture & Unit Tests\n"
        "- **Stage 2 (Not Implemented):** Departmental AI Tabs, Full Report Center PDFs, Costed Marketing Studio\n"
        "- **Stage 3 (Not Implemented):** Snapshot Practice/Graded Assessments, Cross-Course Artifacts\n"
        "- **Stage 4 (Optional - Not Implemented):** Fictional Demonstration Storefront"
    )

    st.divider()
    st.subheader("Save / Restore Snapshot")
    snapshot_json_str = json.dumps(state, indent=2)
    st.download_button(
        label="Download Snapshot JSON",
        data=snapshot_json_str,
        file_name=f"team23_nur4_v{state['state_version']}.json",
        mime="application/json"
    )

    uploaded_file = st.file_uploader("Import Snapshot JSON", type=["json"])
    if uploaded_file is not None:
        raw_text = uploaded_file.read().decode("utf-8")
        ok, msg, parsed = validate_snapshot_import(raw_text, TEAM_ID, state["state_version"])
        if not ok:
            st.error(msg)
        else:
            st.warning(msg)
            if st.button("Approve & Restore Imported Snapshot"):
                st.session_state.sim_state = parsed
                st.success("Snapshot restored.")
                st.rerun()

    if st.button("Reset to Handbook Baseline (v1)"):
        st.session_state.sim_state = copy.deepcopy(DEFAULT_STATE)
        st.success("Reset to NUR-4 baseline.")
        st.rerun()

# ---------------------------------------------------------
# MAIN NAVIGATION TABS
# ---------------------------------------------------------
tab_overview, tab_inputs, tab_math, tab_ledger, tab_tests, tab_future = st.tabs([
    "1. Overview & System Map",
    "2. Inputs & Funding",
    "3. Math Skills (AP Statistics)",
    "4. Operations, Finance & Ledger",
    "5. Stage 1 Acceptance Tests",
    "6. Stages 2-4 Roadmap"
])

# ---------------------------------------------------------
# TAB 1: OVERVIEW & SYSTEM MAP
# ---------------------------------------------------------
with tab_overview:
    st.header("Nurse-Led Health Education Simulation (NUR-4)")
    st.caption(
        "Fictional nonclinical health education studio. No medical diagnosis, treatment, or real patient data."
    )

    # Calculate current cash from funding + ledger
    ledger_net_cash = sum(item["amount"] for item in state["ledger"])
    current_cash = state["funding"]["opening_cash"] + ledger_net_cash
    total_revenue = sum(item["amount"] for item in state["ledger"] if item["category"] == "Revenue")
    total_expenses = sum(-item["amount"] for item in state["ledger"] if item["category"] != "Revenue")
    net_operating_profit = total_revenue - total_expenses

    var_per_unit = sum(state["cost_lines"]["variable_per_unit"].values())
    fixed_monthly = sum(state["cost_lines"]["fixed_monthly"].values())
    staff_cap = math.floor(state["inputs"]["staff_hours"] / state["inputs"]["hours_per_unit"])
    derived_cap = min(staff_cap, state["inputs"]["venue_seats"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Spendable Cash", f"${current_cash:,.2f}", f"Start: ${state['funding']['opening_cash']:,.2f}")
    c2.metric("Derived Monthly Capacity", f"{derived_cap} seats", f"Staff: {staff_cap} | Venue: {state['inputs']['venue_seats']}")
    c3.metric("Ledger Operating Profit", f"${net_operating_profit:,.2f}", f"Rev: ${total_revenue:,.2f}")
    c4.metric("Baseline Unit / Fixed Cost", f"${var_per_unit:.2f} / seat", f"Fixed: ${fixed_monthly:.2f}/mo")

    st.subheader("System Map & Human-in-the-Loop Workflow")
    st.markdown(
        """
        1. **Inputs & Funding (Student-Managed):** Configure starting capital ($6,000 owner contribution -> $1,500 equipment, $500 pre-opening expense, $4,000 spendable cash), workshop seat price ($25), educator hours (30 hrs @ 0.5 hrs/seat), and venue capacity (60 seats).
        2. **Deterministic Math & Capacity Engine (Automatic Code):** Computes `booked = min(requested, floor(staff_hours / hours_per_unit), venue_seats)` and `attended = floor(booked * (1 - no_show_rate))`. Revenue and variable costs apply **only** to attended seats.
        3. **Dated Event Ledger (Human-Approved Step):** Recording a simulation run writes unique transaction rows and increments `state_version` (`v1` -> `v2`...). Duplicate `run_id` entries are automatically rejected.
        4. **Departmental AI Assistants (External Gems/Skills - Manual Handoff):** Export the JSON snapshot to Finance, Operations, Market/Marketing, and Independent Reviewer assistants. Students verify all math before approving changes.
        """
    )

# ---------------------------------------------------------
# TAB 2: INPUTS & FUNDING
# ---------------------------------------------------------
with tab_inputs:
    st.header("Startup Funding, Offerings & Operating Inputs")
    st.info("Changes below update scenario previews immediately. Save or record a ledger step to commit to state.")

    col_f, col_o = st.columns(2)
    with col_f:
        st.subheader("Startup Financing & Opening Balances")
        st.write(f"- **Owner Contribution (Equity):** `${state['funding']['owner_contribution']:,.2f}`")
        st.write(f"- **Equipment Assets (Capitalized, not expensed again):** `${state['funding']['equipment_assets']:,.2f}`")
        st.write(f"- **Pre-Opening Expense (Opening Retained Earnings):** `-${state['funding']['pre_opening_expense']:,.2f}`")
        st.write(f"- **Post-Startup Spendable Cash:** `${state['funding']['opening_cash']:,.2f}`")
        st.caption("Accounting rule: Owner contributions and loan proceeds increase cash, never sales revenue.")

        st.subheader("Editable Variable Costs (Per Attended Seat)")
        for k, v in state["cost_lines"]["variable_per_unit"].items():
            state["cost_lines"]["variable_per_unit"][k] = st.number_input(
                f"{k} ($/attended seat)", min_value=0.0, value=float(v), step=0.50, key=f"var_{k}"
            )
        st.write(f"**Total Variable Cost per Attended Seat:** `${sum(state['cost_lines']['variable_per_unit'].values()):.2f}`")

    with col_o:
        st.subheader("Workshop Capacity & Demand Parameters")
        state["inputs"]["base_price"] = st.number_input(
            "Workshop Seat Price ($)", min_value=0.01, value=float(state["inputs"]["base_price"]), step=1.0
        )
        state["inputs"]["D0"] = st.number_input(
            "Baseline Requested Seats / Month (D0)", min_value=0, value=int(state["inputs"]["D0"]), step=5
        )
        state["inputs"]["staff_hours"] = st.number_input(
            "Educator Productive Hours / Month", min_value=0.0, value=float(state["inputs"]["staff_hours"]), step=1.0
        )
        state["inputs"]["hours_per_unit"] = st.number_input(
            "Educator Hours per Seat", min_value=0.05, value=float(state["inputs"]["hours_per_unit"]), step=0.05
        )
        state["inputs"]["venue_seats"] = st.number_input(
            "Venue Seat Limit / Month", min_value=0, value=int(state["inputs"]["venue_seats"]), step=5
        )
        state["inputs"]["no_show_rate"] = st.slider(
            "No-Show Rate (0.00 to 1.00)", min_value=0.0, max_value=1.0, value=float(state["inputs"]["no_show_rate"]), step=0.05
        )

        st.subheader("Editable Monthly Fixed Costs ($/Month)")
        for k, v in state["cost_lines"]["fixed_monthly"].items():
            state["cost_lines"]["fixed_monthly"][k] = st.number_input(
                f"{k} ($/month)", min_value=0.0, value=float(v), step=10.0, key=f"fix_{k}"
            )
        st.write(f"**Total Monthly Fixed Cost:** `${sum(state['cost_lines']['fixed_monthly'].values()):.2f}`")

# ---------------------------------------------------------
# TAB 3: MATH SKILLS & LEVELS (AP STATISTICS)
# ---------------------------------------------------------
with tab_math:
    st.header("Math Skills & Challenge Level Panel — AP Statistics")
    selected_level = st.selectbox(
        "Challenge Level (Teacher-Approved Default: Advanced)",
        ["Foundation", "Applied", "Advanced"],
        index=["Foundation", "Applied", "Advanced"].index(
            state["level_by_skill"]["AP Statistics - Study Design & Inference"]
        )
    )
    state["level_by_skill"]["AP Statistics - Study Design & Inference"] = selected_level

    st.markdown(
        "**Business Question:** Does Workshop Invitation Message B yield a higher learner conversion rate than Message A, "
        "and how should uncertainty around the conversion lift inform our educator hours and venue budget?"
    )

    exp_df = generate_shared_experiment(seed=int(state["inputs"]["random_seed"]))
    stats_res = compute_ap_stats_metrics(exp_df)

    st.warning(
        "SYNTHETIC EXPERIMENT DATA ONLY (`seed=2027`, n=80 fictional prospects). "
        "This dataset is for statistical reasoning and does NOT automatically alter live workshop demand."
    )

    # Display summary table & bar chart (accessible with explicit data table)
    summary_table = pd.DataFrame({
        "Invitation Group": ["Message A (Control)", "Message B (Variant)"],
        "Sample Size (n)": [stats_res["n_a"], stats_res["n_b"]],
        "Attended / Converted (x)": [stats_res["x_a"], stats_res["x_b"]],
        "Sample Proportion (p_hat)": [stats_res["p_a"], stats_res["p_b"]]
    })

    col_m1, col_m2 = st.columns([1, 1])
    with col_m1:
        st.subheader("Experiment Summary Table")
        st.dataframe(summary_table, use_container_width=True)
        st.download_button(
            "Download experiment.csv",
            data=exp_df.to_csv(index=False),
            file_name="experiment.csv",
            mime="text/csv"
        )
    with col_m2:
        st.subheader("Conversion Rate Comparison (0-to-1 Scale)")
        chart_df = summary_table.set_index("Invitation Group")[["Sample Proportion (p_hat)"]]
        st.bar_chart(chart_df)

    if selected_level == "Foundation":
        st.subheader("Foundation Task: Exploratory Data Analysis & Study Design")
        st.write(f"- **Observed Difference (p_B - p_A):** `{stats_res['diff']:.4f}` (`{stats_res['p_b']*100:.1f}%` vs `{stats_res['p_a']*100:.1f}%`)")
        st.write("- **Required Student Evidence:** Define the population of fictional prospective workshop learners, identify the explanatory variable (Message A vs. B) and binary response variable (attended vs. did not attend), and explain why random assignment supports causal comparison within this simulated group.")

    elif selected_level == "Applied":
        st.subheader("Applied Task: Two-Proportion Z-Interval & Pooled Z-Test")
        st.write(f"- **Point Estimate (p_B - p_A):** `{stats_res['diff']:.4f}`")
        st.write(f"- **Unpooled Standard Error:** `{stats_res['se_unpooled']:.6f}`")
        st.write(f"- **95% Confidence Interval:** `[{stats_res['ci_95'][0]:.4f}, {stats_res['ci_95'][1]:.4f}]`")
        st.write(f"- **Two-Sided Pooled Z-Test (H0: p_B = p_A):** `z = {stats_res['z_stat']:.5f}`, `p-value = {stats_res['p_val']:.5f}` (Pooled SE = `{stats_res['se_pooled']:.6f}`)")
        st.write("- **Condition Checks:** Random assignment (40 per group), 10% independence condition (fictional population >= 800), and Large Counts (`12, 28, 20, 20` all >= 10). Because 0 is inside the 95% CI and `p = 0.06789 > 0.05`, we fail to reject H0 at alpha = 0.05.")

    else:  # Advanced
        st.subheader("Advanced Task: Uncertainty Translation to Capacity & Budget Decisions")
        st.write(f"- **95% CI for Conversion Lift (p_B - p_A):** `[{stats_res['ci_95'][0]:.4f}, {stats_res['ci_95'][1]:.4f}]` (`z = {stats_res['z_stat']:.5f}`, `p = {stats_res['p_val']:.5f}`)")
        st.markdown(
            "**Distinction Check:** A confidence interval estimates the plausible range for the *true difference in conversion proportions*, "
            "whereas a sales forecast band models month-to-month *workshop seat volume*."
        )
        invite_volume = st.slider("Scenario: Monthly Workshop Invitations Sent", 50, 300, 160, step=10)
        low_lift, point_lift, high_lift = stats_res["ci_95"][0], stats_res["diff"], stats_res["ci_95"][1]
        base_rate = stats_res["p_a"]

        scen_df = pd.DataFrame({
            "Confidence Bound Scenario": ["Lower 95% Bound (-1.02% lift)", "Point Estimate (+20.0% lift)", "Upper 95% Bound (+41.02% lift)"],
            "Projected Conversion Rate": [round(base_rate + low_lift, 4), round(base_rate + point_lift, 4), round(base_rate + high_lift, 4)],
            "Projected Requested Seats": [
                math.floor(invite_volume * (base_rate + low_lift)),
                math.floor(invite_volume * (base_rate + point_lift)),
                math.floor(invite_volume * (base_rate + high_lift))
            ],
            "Current Capacity Limit": [derived_cap, derived_cap, derived_cap]
        })
        scen_df["Unserved Overflow"] = (scen_df["Projected Requested Seats"] - scen_df["Current Capacity Limit"]).clip(lower=0)
        st.dataframe(scen_df, use_container_width=True)
        st.write(
            "**Interpretation Prompt:** Even at the point estimate (+20% lift), 160 invitations generate 80 requested seats, "
            "hitting our 60-seat capacity ceiling. Should Team 23 spend budget expanding venue seats/educator hours before confirming whether the lift is statistically significant?"
        )

# ---------------------------------------------------------
# TAB 4: OPERATIONS, FINANCE & LEDGER
# ---------------------------------------------------------
with tab_ledger:
    st.header("Operations & Finance Simulator (Normal Mode vs. Fixture-Test Mode)")

    mode_choice = st.radio(
        "Select Operating Mode (Never mix modes in a single run):",
        ["Normal Mode (Derives capacity from staff hours & venue seats)", "Fixture-Test Mode (Replays monthly_fixture.csv with capacity_override)"]
    )

    if mode_choice.startswith("Normal Mode"):
        col_sim1, col_sim2 = st.columns(2)
        with col_sim1:
            sim_date = st.text_input("Simulation Period End Date (YYYY-MM-DD)", value="2027-01-31")
            run_id = st.text_input("Unique Run ID", value=f"RUN-{state['state_version']:03d}")
            req_units = st.number_input("Requested Workshop Seats", min_value=0, value=int(state["inputs"]["D0"]), step=1)
            ad_spend = st.number_input("Approved Campaign Expense ($)", min_value=0.0, value=0.0, step=10.0)

        preview = compute_nur_month(
            requested=req_units,
            price=state["inputs"]["base_price"],
            staff_hours=state["inputs"]["staff_hours"],
            hours_per_unit=state["inputs"]["hours_per_unit"],
            venue_seats=state["inputs"]["venue_seats"],
            no_show_rate=state["inputs"]["no_show_rate"],
            var_cost_unit=sum(state["cost_lines"]["variable_per_unit"].values()),
            fixed_cost_total=sum(state["cost_lines"]["fixed_monthly"].values()),
            ad_cost=ad_spend,
            opening_cash=current_cash
        )

        with col_sim2:
            st.subheader("Scenario Preview (Not Yet Committed)")
            st.write(f"- **Derived Capacity:** `{preview['derived_capacity']}` seats (Staff cap `{preview['staff_capacity']}`, Venue cap `{preview['venue_capacity']}`)")
            st.write(f"- **Booked:** `{preview['booked']}` | **Attended (Sold):** `{preview['sold']}` | **Unserved Demand:** `{preview['unserved_demand']}`")
            st.write(f"- **Revenue:** `${preview['revenue']:,.2f}` | **Total Expense:** `${preview['total_expense']:,.2f}`")
            st.write(f"- **Operating Profit:** `${preview['operating_profit']:,.2f}` | **Projected Closing Cash:** `${preview['ending_cash']:,.2f}`")

        if st.button("Approve & Commit Run to Dated Ledger"):
            ok, msg = record_ledger_step(state, run_id.strip(), sim_date.strip(), preview, "Normal")
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    else:
        st.warning(
            "FIXTURE-TEST MODE ACTIVE: Uses explicit capacity_override values from sample_data/monthly_fixture.csv. "
            "Reset to Handbook Baseline (v1) before running the 3-month fixture sequence."
        )
        fixture_df = pd.DataFrame(MONTHLY_FIXTURE_ROWS)
        st.dataframe(fixture_df, use_container_width=True)

        if st.button("Replay All 3 Fixture Months (2027-01 to 2027-03)"):
            running_cash = state["funding"]["opening_cash"] + sum(i["amount"] for i in state["ledger"])
            for row in MONTHLY_FIXTURE_ROWS:
                m_res = compute_nur_month(
                    requested=row["requested"],
                    price=25.00,
                    staff_hours=30.0,
                    hours_per_unit=0.5,
                    venue_seats=60,
                    no_show_rate=0.0,
                    var_cost_unit=5.00,
                    fixed_cost_total=700.00,
                    ad_cost=row["ad_cost"],
                    opening_cash=running_cash,
                    capacity_override=row["capacity_override"]
                )
                ok, msg = record_ledger_step(
                    state,
                    run_id=f"FIXTURE-{row['month']}",
                    sim_date=f"{row['month']}-28",
                    result=m_res,
                    mode_label="Fixture-Test"
                )
                if ok:
                    running_cash = m_res["ending_cash"]
            st.success("Fixture replay complete. Inspect ledger below.")
            st.rerun()

    st.divider()
    st.subheader("Dated Event Ledger (Source of Truth)")
    if state["ledger"]:
        ledger_df = pd.DataFrame(state["ledger"])
        st.dataframe(ledger_df, use_container_width=True)
        st.download_button(
            "Export Ledger CSV",
            data=ledger_df.to_csv(index=False),
            file_name=f"team23_nur4_ledger_v{state['state_version']}.csv",
            mime="text/csv"
        )
    else:
        st.info("No transactions recorded yet. Commit a run above or replay the fixture.")

# ---------------------------------------------------------
# TAB 5: STAGE 1 ACCEPTANCE TESTS
# ---------------------------------------------------------
with tab_tests:
    st.header("Stage 1 Automated Verification & Acceptance Checks")
    st.caption("Deterministic verification of NUR-4 formulas, fixture totals, edge cases, and data-contract rules.")

    if st.button("Run All Stage 1 Acceptance Checks"):
        results = []

        # Test 1: 3-Month Fixture Sequence
        cash = 4000.00
        expected_fixture = [
            ("2027-01", 60, 1500.00, 1000.00, 500.00, 4500.00),
            ("2027-02", 60, 1500.00, 1100.00, 400.00, 4900.00),
            ("2027-03", 45, 1125.00, 925.00, 200.00, 5100.00)
        ]
        fixture_pass = True
        for idx, row in enumerate(MONTHLY_FIXTURE_ROWS):
            out = compute_nur_month(
                requested=row["requested"], price=25.0, staff_hours=30.0, hours_per_unit=0.5,
                venue_seats=60, no_show_rate=0.0, var_cost_unit=5.0, fixed_cost_total=700.0,
                ad_cost=row["ad_cost"], opening_cash=cash, capacity_override=row["capacity_override"]
            )
            cash = out["ending_cash"]
            exp = expected_fixture[idx]
            if not (
                out["sold"] == exp[1]
                and abs(out["revenue"] - exp[2]) < 0.01
                and abs(out["total_expense"] - exp[3]) < 0.01
                and abs(out["operating_profit"] - exp[4]) < 0.01
                and abs(out["ending_cash"] - exp[5]) < 0.01
            ):
                fixture_pass = False
        results.append(("3-Month Fixture Replay (2027-01..03)", "PASS" if fixture_pass else "FAIL", "Sold: 60,60,45 | Closing cash: $4,500 -> $4,900 -> $5,100"))

        # Test 2: Business-Specific No-Show Rate = 0.20
        ns_out = compute_nur_month(
            requested=80, price=25.0, staff_hours=30.0, hours_per_unit=0.5,
            venue_seats=60, no_show_rate=0.20, var_cost_unit=5.0, fixed_cost_total=700.0,
            ad_cost=0.0, opening_cash=4000.0
        )
        ns_pass = (
            ns_out["booked"] == 60 and ns_out["attended"] == 48
            and abs(ns_out["revenue"] - 1200.00) < 0.01
            and abs(ns_out["variable_expense"] - 240.00) < 0.01
            and abs(ns_out["operating_profit"] - 260.00) < 0.01
        )
        results.append(("NUR No-Show Test (no_show_rate=0.20)", "PASS" if ns_pass else "FAIL", f"Booked={ns_out['booked']}, Attended={ns_out['attended']}, Profit=${ns_out['operating_profit']:.2f}"))

        # Test 3: Zero Sales Check
        z_out = compute_nur_month(
            requested=0, price=25.0, staff_hours=30.0, hours_per_unit=0.5,
            venue_seats=60, no_show_rate=0.0, var_cost_unit=5.0, fixed_cost_total=700.0,
            ad_cost=0.0, opening_cash=4000.0
        )
        z_pass = (z_out["revenue"] == 0.0 and z_out["variable_expense"] == 0.0 and abs(z_out["operating_profit"] - (-700.00)) < 0.01)
        results.append(("Zero-Sales Edge Case", "PASS" if z_pass else "FAIL", f"Rev=${z_out['revenue']:.2f}, Profit=${z_out['operating_profit']:.2f}"))

        # Test 4: Stale Version & Wrong Team Rejection
        stale_snap = copy.deepcopy(DEFAULT_STATE)
        stale_snap["state_version"] = 1
        ok_stale, msg_stale, _ = validate_snapshot_import(json.dumps(stale_snap), TEAM_ID, current_version=2)

        wrong_team = copy.deepcopy(DEFAULT_STATE)
        wrong_team["team_id"] = "Team 99"
        ok_team, msg_team, _ = validate_snapshot_import(json.dumps(wrong_team), TEAM_ID, current_version=1)

        imp_pass = (not ok_stale) and (not ok_team)
        results.append(("Import Guardrails (Stale Version & Wrong Team)", "PASS" if imp_pass else "FAIL", f"{msg_stale} | {msg_team}"))

        # Test 5: AP Statistics Experiment Generator
        exp_test = compute_ap_stats_metrics(generate_shared_experiment(2027))
        ap_pass = (
            exp_test["n_a"] == 40 and exp_test["n_b"] == 40
            and abs(exp_test["diff"] - 0.20) < 1e-6
            and abs(exp_test["z_stat"] - 1.82574) < 1e-4
        )
        results.append(("AP Statistics Shared Experiment (seed=2027)", "PASS" if ap_pass else "FAIL", f"diff={exp_test['diff']}, z={exp_test['z_stat']}, p={exp_test['p_val']}"))

        test_df = pd.DataFrame(results, columns=["Test Case", "Status", "Evidence"])
        st.dataframe(test_df, use_container_width=True)

# ---------------------------------------------------------
# TAB 6: STAGES 2-4 ROADMAP
# ---------------------------------------------------------
with tab_future:
    st.header("Remaining Build Stages (Not Yet Implemented)")
    st.markdown(
        """
        Per the Career Venture Lab Student Handbook, complete and verify Stage 1 before unlocking subsequent modules:
        - **Stage 2 (Next):** Departmental AI Recommendation Cards (`Finance`, `Operations`, `Market & Marketing`, `Independent Reviewer`), full printable Report Center (Income Statement, Cash Flow, Budget Variance, Balance Sheet), and Costed Marketing Studio with duplicate `campaign_id` protection.
        - **Stage 3:** Frozen-Snapshot Practice & Graded Assessment Panel (with separate teacher key) and Cross-Course Evidence Artifacts (health-education source critique & accessible flyer revision).
        - **Stage 4 (Optional):** Fictional Demonstration Storefront (`DEMONSTRATION BUSINESS - NO REAL PURCHASES`).
        """
    )
