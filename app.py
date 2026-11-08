"""Interactive dashboard for the Black Outcomes Intelligence Gold analytics."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

YEAR = 2024
DATA_DIR = Path(__file__).parent / "data" / "published"
STATE_NAMES = {
    1:"Alabama",2:"Alaska",4:"Arizona",5:"Arkansas",6:"California",8:"Colorado",9:"Connecticut",10:"Delaware",11:"District of Columbia",12:"Florida",13:"Georgia",15:"Hawaii",16:"Idaho",17:"Illinois",18:"Indiana",19:"Iowa",20:"Kansas",21:"Kentucky",22:"Louisiana",23:"Maine",24:"Maryland",25:"Massachusetts",26:"Michigan",27:"Minnesota",28:"Mississippi",29:"Missouri",30:"Montana",31:"Nebraska",32:"Nevada",33:"New Hampshire",34:"New Jersey",35:"New Mexico",36:"New York",37:"North Carolina",38:"North Dakota",39:"Ohio",40:"Oklahoma",41:"Oregon",42:"Pennsylvania",44:"Rhode Island",45:"South Carolina",46:"South Dakota",47:"Tennessee",48:"Texas",49:"Utah",50:"Vermont",51:"Virginia",53:"Washington",54:"West Virginia",55:"Wisconsin",56:"Wyoming"
}

@st.cache_data
def load_data():
    national_path = DATA_DIR / "national.csv"
    states_path = DATA_DIR / "states.csv"
    if not national_path.exists() or not states_path.exists():
        raise FileNotFoundError("Run the Snapshot Dashboard Data workflow before deploying the app.")
    national = pd.read_csv(national_path)
    states = pd.read_csv(states_path)
    if len(national) != 1 or len(states) != 51:
        raise ValueError("Published dashboard snapshot failed row-count validation.")
    required = {
        "black_population_estimate", "black_population_standard_error", "black_population_ci95_lower",
        "black_population_ci95_upper", "black_population_unweighted_n", "black_population_weighted_denominator",
        "black_population_is_suppressed", "married_rate_estimate", "married_rate_is_suppressed",
        "bachelors_plus_rate_estimate", "bachelors_plus_rate_is_suppressed",
        "mean_personal_income_estimate", "mean_personal_income_is_suppressed",
    }
    for name, frame in (("national", national), ("states", states)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"Published {name} snapshot lacks Phase 1 statistical fields: {missing}")
    return national, states


def format_value(value, value_type):
    if value_type == "percent":
        return f"{float(value):.1%}"
    if value_type == "currency":
        return f"${float(value):,.0f}"
    return f"{int(value):,}"


st.set_page_config(page_title="Black Outcomes Intelligence", page_icon="📊", layout="wide")
st.title("Black Outcomes Intelligence")
st.caption("2024 American Community Survey PUMS · weighted estimates for Black adults age 18+")

try:
    national, states = load_data()
except Exception as exc:
    st.error("The validated dashboard snapshot is unavailable.")
    st.exception(exc)
    st.stop()

states["state_name"] = states["state"].map(STATE_NAMES)
n = national.iloc[0]

def metric_text(row, prefix, kind):
    if bool(row[f"{prefix}_is_suppressed"]):
        return "Suppressed"
    value = row[f"{prefix}_estimate"]
    low, high = row[f"{prefix}_ci95_lower"], row[f"{prefix}_ci95_upper"]
    return f"{format_value(value, kind)} (95% CI {format_value(low, kind)}–{format_value(high, kind)})"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Black adult population", metric_text(n, "black_population", "compact"))
c2.metric("Married", metric_text(n, "married_rate", "percent"))
c3.metric("Bachelor's+", metric_text(n, "bachelors_plus_rate", "percent"))
c4.metric("Mean personal income", metric_text(n, "mean_personal_income", "currency"))

st.subheader("Explore outcomes")
state_options = ["Top 10 States"] + sorted(states.state_name.dropna().tolist())
selected = st.selectbox("Geography", state_options, index=0)
metric = st.selectbox("Measure", ["Black population", "Marriage rate", "Bachelor's+ rate", "Mean personal income"])
metric_config = {
    "Black population": ("black_population", "Black adult population", "compact"),
    "Marriage rate": ("married_rate", "Marriage rate", "percent"),
    "Bachelor's+ rate": ("bachelors_plus_rate", "Bachelor's+ rate", "percent"),
    "Mean personal income": ("mean_personal_income", "Mean personal income", "currency"),
}
prefix, axis_title, value_type = metric_config[metric]
column = f"{prefix}_estimate"

if selected == "Top 10 States":
    eligible_states = states.loc[~states[f"{prefix}_is_suppressed"].astype(bool)]
    ranked = eligible_states.dropna(subset=["state_name", column]).nlargest(10, column).sort_values(column, ascending=True).copy()
    st.markdown(f"#### Top 10 states — {metric}")
    st.bar_chart(
        ranked[["state_name", column]].set_index("state_name"),
        horizontal=True,
        x_label=axis_title,
        y_label="State",
        height=430,
    )

    top10 = ranked.sort_values(column, ascending=False)[["state_name", column]].reset_index(drop=True)
    top10.index = top10.index + 1
    top10.index.name = "Rank"
    display = top10.copy()
    display[column] = display[column].map(lambda x: format_value(x, value_type))
    display = display.rename(columns={"state_name": "State", column: axis_title})
    st.dataframe(display, use_container_width=True)
else:
    r = states.loc[states.state_name == selected].iloc[0]
    st.markdown(f"#### {selected} — {metric}")

    # The visualization now follows the selected geography instead of leaving the national Top 10 on screen.
    selected_chart = pd.DataFrame({axis_title: [r[column]]}, index=[selected])
    st.bar_chart(
        selected_chart,
        horizontal=True,
        x_label=axis_title,
        y_label="State",
        height=220,
    )
    st.caption(f"{selected} {axis_title.lower()}: **{metric_text(r, prefix, value_type)}**")

    st.markdown(f"#### {selected} profile")
    a, b, c, d = st.columns(4)
    a.metric("Black adult population", metric_text(r, "black_population", "compact"))
    b.metric("Married", metric_text(r, "married_rate", "percent"))
    c.metric("Bachelor's+", metric_text(r, "bachelors_plus_rate", "percent"))
    d.metric("Mean personal income", metric_text(r, "mean_personal_income", "currency"))

    st.info(
        f"The chart is now filtered to {selected}. Top-10 city/place rankings will be added as a separate geography layer. "
        "The current PUMS Gold mart supports state geography, so the dashboard will not invent city-level values."
    )

st.caption("Dashboard data are a versioned snapshot of aggregated Gold outputs; the public application requires no AWS credentials and has no access to Census microdata.")
with st.expander("Methodology"):
    st.markdown("Estimates use 2024 ACS 1-Year PUMS person records, restricted to RAC1P=2 (Black alone) and age 18+. Point estimates use PWGTP. Standard errors use all 80 PWGTP replicate weights and the Census ACS SDR factor 4/80; intervals are estimate ± 1.96 SE (bounded to [0,1] for rates). Every metric publishes its unweighted sample size and weighted denominator. Estimates are suppressed when unweighted n < 30, the denominator is nonpositive, or relative standard error exceeds 30%. These are descriptive survey estimates, not causal claims.")
