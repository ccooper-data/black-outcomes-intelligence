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

c1, c2, c3, c4 = st.columns(4)
c1.metric("Black adult population", f"{int(n.black_adult_population):,}")
c2.metric("Married", f"{float(n.married_rate):.1%}")
c3.metric("Bachelor's+", f"{float(n.bachelors_plus_rate):.1%}")
c4.metric("Mean personal income", f"${float(n.weighted_mean_personal_income):,.0f}")

st.subheader("Explore outcomes")
state_options = ["Top 10 States"] + sorted(states.state_name.dropna().tolist())
selected = st.selectbox("Geography", state_options, index=0)
metric = st.selectbox("Measure", ["Black population", "Marriage rate", "Bachelor's+ rate", "Mean personal income"])
metric_config = {
    "Black population": ("black_population", "Black adult population", "compact"),
    "Marriage rate": ("married_rate", "Marriage rate", "percent"),
    "Bachelor's+ rate": ("bachelors_plus_rate", "Bachelor's+ rate", "percent"),
    "Mean personal income": ("weighted_mean_personal_income", "Mean personal income", "currency"),
}
column, axis_title, value_type = metric_config[metric]

if selected == "Top 10 States":
    ranked = states.dropna(subset=["state_name", column]).nlargest(10, column).sort_values(column, ascending=True).copy()
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
    st.caption(f"{selected} {axis_title.lower()}: **{format_value(r[column], value_type)}**")

    st.markdown(f"#### {selected} profile")
    a, b, c, d = st.columns(4)
    a.metric("Black adult population", f"{int(r.black_population):,}")
    b.metric("Married", f"{float(r.married_rate):.1%}")
    c.metric("Bachelor's+", f"{float(r.bachelors_plus_rate):.1%}")
    d.metric("Mean personal income", f"${float(r.weighted_mean_personal_income):,.0f}")

    st.info(
        f"The chart is now filtered to {selected}. Top-10 city/place rankings will be added as a separate geography layer. "
        "The current PUMS Gold mart supports state geography, so the dashboard will not invent city-level values."
    )

st.caption("Dashboard data are a versioned snapshot of aggregated Gold outputs; the public application requires no AWS credentials and has no access to Census microdata.")
with st.expander("Methodology"):
    st.markdown("Estimates use 2024 ACS 1-Year PUMS person records, restricted to RAC1P=2 (Black alone) and age 18+. Population counts and rates use the Census person weight PWGTP. Income is a PWGTP-weighted mean of PINCP among records with non-null personal income. These are descriptive survey estimates, not causal claims.")
