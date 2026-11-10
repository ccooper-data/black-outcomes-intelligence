"""Interactive dashboard for the Black Outcomes Intelligence Gold analytics."""
from __future__ import annotations

from pathlib import Path
import json
import os
import time

import pandas as pd
import streamlit as st

from src.ask_data import UnsafeAnswerError, ask_data, build_evidence_store
from src.research_report import load_report_package

DATA_DIR = Path(__file__).parent / "data" / "published"
REPORT_DIR = DATA_DIR / "research_report" / "2024"
STATE_NAMES = {
    1:"Alabama",2:"Alaska",4:"Arizona",5:"Arkansas",6:"California",8:"Colorado",9:"Connecticut",10:"Delaware",11:"District of Columbia",12:"Florida",13:"Georgia",15:"Hawaii",16:"Idaho",17:"Illinois",18:"Indiana",19:"Iowa",20:"Kansas",21:"Kentucky",22:"Louisiana",23:"Maine",24:"Maryland",25:"Massachusetts",26:"Michigan",27:"Minnesota",28:"Mississippi",29:"Missouri",30:"Montana",31:"Nebraska",32:"Nevada",33:"New Hampshire",34:"New Jersey",35:"New Mexico",36:"New York",37:"North Carolina",38:"North Dakota",39:"Ohio",40:"Oklahoma",41:"Oregon",42:"Pennsylvania",44:"Rhode Island",45:"South Carolina",46:"South Dakota",47:"Tennessee",48:"Texas",49:"Utah",50:"Vermont",51:"Virginia",53:"Washington",54:"West Virginia",55:"Wisconsin",56:"Wyoming"
}

@st.cache_data
def load_data():
    national_path = DATA_DIR / "national.csv"
    states_path = DATA_DIR / "states.csv"
    intersectional_path = DATA_DIR / "intersectional.csv"
    if not national_path.exists() or not states_path.exists() or not intersectional_path.exists():
        raise FileNotFoundError("Run the Snapshot Dashboard Data workflow before deploying the app.")
    national = pd.read_csv(national_path)
    states = pd.read_csv(states_path)
    intersectional = pd.read_csv(intersectional_path)
    if len(national) != 1 or len(states) != 51 or len(intersectional) != 728:
        raise ValueError("Published dashboard snapshot failed row-count validation.")
    required = {
        "black_population_estimate", "black_population_standard_error", "black_population_ci95_lower",
        "black_population_ci95_upper", "black_population_unweighted_n", "black_population_weighted_denominator",
        "black_population_is_suppressed", "married_rate_estimate", "married_rate_is_suppressed",
        "bachelors_plus_rate_estimate", "bachelors_plus_rate_is_suppressed",
        "employment_rate_estimate", "employment_rate_is_suppressed",
        "mean_personal_income_estimate", "mean_personal_income_is_suppressed",
    }
    for name, frame in (("national", national), ("states", states), ("intersectional", intersectional)):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"Published {name} snapshot lacks Phase 1 statistical fields: {missing}")
    trends_path = DATA_DIR / "trends.csv"
    contrasts_path = DATA_DIR / "contrasts.csv"
    trends = pd.read_csv(trends_path) if trends_path.exists() else pd.DataFrame()
    contrasts = pd.read_csv(contrasts_path) if contrasts_path.exists() else pd.DataFrame()
    if not trends.empty:
        if len(trends) != 2184 or set(trends["survey_year"]) != {2022, 2023, 2024}:
            raise ValueError("Published longitudinal trend snapshot failed validation.")
        if len(contrasts) != 1092 or set(contrasts["survey_year"]) != {2022, 2023, 2024}:
            raise ValueError("Published longitudinal contrast snapshot failed validation.")
    model_metrics_path = DATA_DIR / "model_metrics.csv"
    model_calibration_path = DATA_DIR / "model_calibration.csv"
    model_card_path = DATA_DIR / "model_card.json"
    model_metrics = pd.read_csv(model_metrics_path) if model_metrics_path.exists() else pd.DataFrame()
    model_calibration = pd.read_csv(model_calibration_path) if model_calibration_path.exists() else pd.DataFrame()
    model_card = json.loads(model_card_path.read_text()) if model_card_path.exists() else {}
    if not model_metrics.empty:
        if set(model_metrics["evaluation_year"]) != {2024} or set(model_metrics["metric"]) != {"brier_score", "log_loss"}:
            raise ValueError("Published Phase 4 model metrics failed validation.")
        if model_calibration.empty or model_card.get("person_level_predictions_published") is not False:
            raise ValueError("Published Phase 4 aggregate-only contract failed validation.")
    robustness_names = (
        "robustness_metrics.csv", "robustness_comparisons.csv",
        "robustness_calibration.csv", "robustness_features.csv",
    )
    robustness_frames = [
        pd.read_csv(DATA_DIR / name) if (DATA_DIR / name).exists() else pd.DataFrame()
        for name in robustness_names
    ]
    robustness_card_path = DATA_DIR / "robustness_card.json"
    robustness_card = json.loads(robustness_card_path.read_text()) if robustness_card_path.exists() else {}
    robustness_metrics, robustness_comparisons, robustness_calibration, robustness_features = robustness_frames
    if not robustness_metrics.empty:
        if set(robustness_metrics["model"]) != {
            "weighted_prevalence_baseline", "survey_weighted_logistic", "survey_weighted_xgboost"
        } or set(robustness_metrics["evaluation_year"]) != {2024}:
            raise ValueError("Published Phase 5 robustness metrics failed validation.")
        if robustness_comparisons.empty or robustness_calibration.empty or robustness_features.empty:
            raise ValueError("Published Phase 5 evidence package is incomplete.")
        if robustness_card.get("automatic_promotion") is not False or robustness_card.get("person_level_predictions_published") is not False:
            raise ValueError("Published Phase 5 governance contract failed validation.")
    inference_path = DATA_DIR / "inference.csv"
    inference_manifest_path = DATA_DIR / "inference_manifest.json"
    inference = pd.read_csv(inference_path) if inference_path.exists() else pd.DataFrame()
    inference_manifest = json.loads(inference_manifest_path.read_text()) if inference_manifest_path.exists() else {}
    if not inference.empty:
        if len(inference) != 208 or set(inference["survey_year"]) != {2024}:
            raise ValueError("Published Phase 7 inference snapshot failed row-count or year validation.")
        if set(inference["metric"]) != {
            "married_rate", "bachelors_plus_rate", "employment_rate", "mean_personal_income",
        }:
            raise ValueError("Published Phase 7 inference metrics failed validation.")
        required_inference = {
            "women_estimate", "men_estimate", "difference_estimate", "difference_standard_error",
            "difference_ci95_lower", "difference_ci95_upper", "difference_p_value",
            "difference_log10_p_value", "difference_q_value", "difference_log10_q_value",
            "difference_q_value_below_machine_precision", "difference_fdr_significant",
            "difference_is_suppressed",
        }
        if not required_inference <= set(inference) or inference_manifest.get("causal_interpretation") is not False:
            raise ValueError("Published Phase 7 inference contract failed validation.")
    return (
        national, states, intersectional, trends, contrasts,
        model_metrics, model_calibration, model_card,
        robustness_metrics, robustness_comparisons, robustness_calibration,
        robustness_features, robustness_card, inference, inference_manifest,
    )


def format_value(value, value_type):
    if value_type == "percent":
        return f"{float(value):.1%}"
    if value_type == "currency":
        return f"${float(value):,.0f}"
    return f"{int(value):,}"


@st.cache_data
def load_chat_evidence():
    return build_evidence_store(DATA_DIR)


@st.cache_data
def load_research_report():
    return load_report_package(REPORT_DIR)


st.set_page_config(page_title="Black Outcomes Intelligence", page_icon="📊", layout="wide")
st.title("Black Outcomes Intelligence")
st.caption("2022–2024 American Community Survey PUMS · weighted estimates for Black adults age 18+")

try:
    (
        national, states, intersectional, trends, contrasts,
        model_metrics, model_calibration, model_card,
        robustness_metrics, robustness_comparisons, robustness_calibration,
        robustness_features, robustness_card, inference, inference_manifest,
    ) = load_data()
except Exception as exc:
    st.error("The validated dashboard snapshot is unavailable.")
    st.exception(exc)
    st.stop()

states["state_name"] = states["state"].map(STATE_NAMES)
intersectional["state_name"] = intersectional["state"].map(STATE_NAMES).fillna("National")
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

st.subheader("Ask the data")
st.caption(
    "Ask questions about the published aggregate estimates. Answers are AI-generated, source-cited, "
    "and cannot access Census microdata or suppressed values."
)
chat_enabled = os.getenv("ASK_DATA_ENABLED", "false").lower() == "true"
api_key = os.getenv("OPENAI_API_KEY")
if not chat_enabled:
    st.info("Ask the Data is disabled by default. Set ASK_DATA_ENABLED=true in server configuration to activate it.")
elif not api_key:
    st.warning("Ask the Data is enabled but OPENAI_API_KEY is not configured on the server.")
else:
    from openai import OpenAI

    if "ask_data_messages" not in st.session_state:
        st.session_state.ask_data_messages = []
    if "ask_data_request_times" not in st.session_state:
        st.session_state.ask_data_request_times = []
    if "ask_data_request_count" not in st.session_state:
        st.session_state.ask_data_request_count = 0
    for message in st.session_state.ask_data_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if st.button("Clear chat", key="clear_ask_data"):
        st.session_state.ask_data_messages = []
        st.rerun()
    question = st.chat_input("Ask about outcomes, trends, states, uncertainty, or model diagnostics")
    if question:
        history = list(st.session_state.ask_data_messages)
        st.session_state.ask_data_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                now = time.time()
                recent = [timestamp for timestamp in st.session_state.ask_data_request_times if now - timestamp < 60]
                if len(recent) >= 5 or st.session_state.ask_data_request_count >= 25:
                    raise RuntimeError("Ask the Data session rate limit reached.")
                st.session_state.ask_data_request_times = recent + [now]
                st.session_state.ask_data_request_count += 1
                client = OpenAI(api_key=api_key, timeout=30.0, max_retries=1)
                result = ask_data(
                    question,
                    load_chat_evidence(),
                    client,
                    os.getenv("OPENAI_MODEL", "gpt-6-luna"),
                    history,
                )
                st.markdown(result.text)
                with st.expander("Evidence supplied to ChatGPT"):
                    for index, item in enumerate(result.sources, start=1):
                        st.markdown(f"**E{index}** — {item.text}")
                st.session_state.ask_data_messages.append({"role": "assistant", "content": result.text})
                st.session_state.ask_data_messages = st.session_state.ask_data_messages[-8:]
            except UnsafeAnswerError:
                st.error("The generated response failed the evidence-safety check. No answer was displayed.")
            except RuntimeError as exc:
                if "rate limit" in str(exc).lower():
                    st.error("This chat session has reached its request limit. Please wait or start a later session.")
                else:
                    st.error("Ask the Data is temporarily unavailable. The dashboard data remain available below.")
            except Exception:
                st.error("Ask the Data is temporarily unavailable. The dashboard data remain available below.")

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

st.divider()
st.subheader("Black women: intersectional outcomes")
st.caption("Compare Black women with Black men within the same state and age band. Comparisons are descriptive; no untested significance claim is made.")

comparison_geography = st.selectbox(
    "Intersectional geography", ["National"] + sorted(states.state_name.dropna().tolist()),
)
comparison_age = st.selectbox(
    "Age band", ["All ages", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"],
)
comparison_metric = st.selectbox(
    "Intersectional measure",
    ["Population", "Marriage rate", "Bachelor's+ rate", "Employment rate", "Mean personal income"],
)
comparison_config = {
    "Population": ("black_population", "compact"),
    "Marriage rate": ("married_rate", "percent"),
    "Bachelor's+ rate": ("bachelors_plus_rate", "percent"),
    "Employment rate": ("employment_rate", "percent"),
    "Mean personal income": ("mean_personal_income", "currency"),
}
comparison_prefix, comparison_kind = comparison_config[comparison_metric]
comparison_rows = intersectional.loc[
    (intersectional["state_name"] == comparison_geography)
    & (intersectional["age_band"] == comparison_age)
]

if set(comparison_rows["sex"]) == {"Black women", "Black men"}:
    women = comparison_rows.loc[comparison_rows["sex"] == "Black women"].iloc[0]
    men = comparison_rows.loc[comparison_rows["sex"] == "Black men"].iloc[0]
    women_col, men_col = st.columns(2)
    women_col.metric("Black women", metric_text(women, comparison_prefix, comparison_kind))
    men_col.metric("Black men — descriptive benchmark", metric_text(men, comparison_prefix, comparison_kind))
    women_col.caption(
        f"Unweighted n: {int(women[f'{comparison_prefix}_unweighted_n']):,} · "
        f"Weighted denominator: {women[f'{comparison_prefix}_weighted_denominator']:,.0f}"
    )
    men_col.caption(
        f"Unweighted n: {int(men[f'{comparison_prefix}_unweighted_n']):,} · "
        f"Weighted denominator: {men[f'{comparison_prefix}_weighted_denominator']:,.0f}"
    )
    comparison_chart = comparison_rows.loc[
        ~comparison_rows[f"{comparison_prefix}_is_suppressed"].astype(bool),
        ["sex", f"{comparison_prefix}_estimate"],
    ].set_index("sex")
    if not comparison_chart.empty:
        st.bar_chart(comparison_chart, y_label=comparison_metric, height=280)
else:
    st.warning("The selected comparison is unavailable in the validated snapshot.")

st.divider()
st.subheader("Phase 7: age-adjusted differences")
if inference.empty:
    st.info("The Phase 7 research-inference snapshot has not yet been published.")
else:
    st.caption(
        "Black women-minus-Black men comparisons use a common 2024 national Black-adult age distribution. "
        "Confidence intervals and tests use paired ACS replicate estimates. State findings control the false "
        "discovery rate within each outcome; associations are descriptive, not causal."
    )
    inference = inference.copy()
    inference["state_name"] = inference["state"].map(STATE_NAMES).fillna("National")
    inference_geography = st.selectbox(
        "Inference geography", ["National"] + sorted(states.state_name.dropna().tolist())
    )
    inference_measure = st.selectbox(
        "Age-adjusted outcome",
        ["Marriage rate", "Bachelor's+ rate", "Employment rate", "Mean personal income"],
    )
    inference_config = {
        "Marriage rate": ("married_rate", "percent"),
        "Bachelor's+ rate": ("bachelors_plus_rate", "percent"),
        "Employment rate": ("employment_rate", "percent"),
        "Mean personal income": ("mean_personal_income", "currency"),
    }
    inference_metric, inference_kind = inference_config[inference_measure]
    inference_row = inference.loc[
        (inference["state_name"] == inference_geography)
        & (inference["metric"] == inference_metric)
    ]
    if inference_row.empty:
        st.warning("The selected age-adjusted comparison is unavailable.")
    else:
        inference_row = inference_row.iloc[0]
        if bool(inference_row["difference_is_suppressed"]):
            st.warning(
                "This comparison is suppressed under the component sample-size and stability rules. "
                f"Reason: {inference_row['difference_suppression_reason']}"
            )
        else:
            women_col, men_col, difference_col = st.columns(3)
            women_col.metric("Black women — age adjusted", format_value(inference_row["women_estimate"], inference_kind))
            men_col.metric("Black men — age adjusted", format_value(inference_row["men_estimate"], inference_kind))
            difference_col.metric(
                "Women minus men",
                format_value(inference_row["difference_estimate"], inference_kind),
            )
            difference_col.caption(
                "95% CI "
                f"{format_value(inference_row['difference_ci95_lower'], inference_kind)}–"
                f"{format_value(inference_row['difference_ci95_upper'], inference_kind)}"
            )
            if bool(inference_row["difference_fdr_significant"]):
                q_text = (
                    f"q below floating-point precision; log10(q)={inference_row['difference_log10_q_value']:.3f}"
                    if bool(inference_row["difference_q_value_below_machine_precision"])
                    else f"q={inference_row['difference_q_value']:.3g}"
                )
                st.success(
                    f"Statistically distinguishable after multiplicity control ({q_text}). "
                    "The observed difference is not evidence of causation or of individual outcomes."
                )
            else:
                st.info(
                    f"Not statistically distinguishable after multiplicity control (q={inference_row['difference_q_value']:.3g}). "
                    "The data do not establish a nonzero population difference for this comparison."
                )
            st.caption(
                f"Black women unweighted n: {int(inference_row['women_unweighted_n']):,}; "
                f"weighted denominator: {inference_row['women_weighted_denominator']:,.0f}. "
                f"Black men unweighted n: {int(inference_row['men_unweighted_n']):,}; "
                f"weighted denominator: {inference_row['men_weighted_denominator']:,.0f}."
            )

st.divider()
st.subheader("2024 research findings report")
st.caption("Validation status: internally tested · External review pending")
try:
    report_manifest, report_files = load_research_report()
except Exception as exc:
    st.error("The published research report failed integrity validation.")
    st.exception(exc)
    report_manifest, report_files = {}, {}
if not report_files:
    st.info("The reviewed Phase 8 research report has not yet been published.")
else:
    st.caption(
        "Versioned findings generated from validated public aggregates. The report describes associations, "
        "sampling uncertainty, multiplicity control, suppression, provenance, and limitations; it is not causal."
    )
    report_col, appendix_col, methods_col = st.columns(3)
    report_col.download_button(
        "Download HTML report",
        data=report_files["research_findings.html"],
        file_name="black_outcomes_2024_research_findings.html",
        mime="text/html",
    )
    appendix_col.download_button(
        "Download audit appendix",
        data=report_files["research_findings_appendix.csv"],
        file_name="black_outcomes_2024_research_findings_appendix.csv",
        mime="text/csv",
    )
    methods_col.download_button(
        "Download Markdown report",
        data=report_files["research_findings.md"],
        file_name="black_outcomes_2024_research_findings.md",
        mime="text/markdown",
    )
    st.caption(
        f"Release contains {report_manifest['publishable_rows']} publishable and "
        f"{report_manifest['suppressed_rows']} suppressed comparisons. Artifact hashes are verified at load time."
    )

st.divider()
st.subheader("2022–2024 trends and direct comparisons")
if trends.empty or contrasts.empty:
    st.info("The longitudinal snapshot has not yet been published. Run the Phase 3 publish and snapshot workflows after merge.")
else:
    trends["state_name"] = trends["state"].map(STATE_NAMES).fillna("National")
    contrasts["state_name"] = contrasts["state"].map(STATE_NAMES).fillna("National")
    trend_geography = st.selectbox("Trend geography", ["National"] + sorted(states.state_name.dropna().tolist()))
    trend_age = st.selectbox("Trend age band", ["All ages", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"])
    trend_metric = st.selectbox(
        "Trend measure", ["Population", "Marriage rate", "Bachelor's+ rate", "Employment rate", "Mean personal income"]
    )
    trend_prefix, trend_kind = comparison_config[trend_metric]
    selected_trends = trends.loc[
        (trends["state_name"] == trend_geography) & (trends["age_band"] == trend_age)
        & ~trends[f"{trend_prefix}_is_suppressed"].astype(bool)
    ].copy()
    if selected_trends.empty:
        st.warning("All estimates for this selection are suppressed under the published stability rules.")
    else:
        st.line_chart(
            selected_trends.pivot(index="survey_year", columns="sex", values=f"{trend_prefix}_estimate"),
            y_label=trend_metric,
        )
        detail = selected_trends[[
            "survey_year", "sex", f"{trend_prefix}_estimate",
            f"{trend_prefix}_ci95_lower", f"{trend_prefix}_ci95_upper",
            f"{trend_prefix}_unweighted_n", f"{trend_prefix}_weighted_denominator",
        ]]
        st.dataframe(detail, use_container_width=True, hide_index=True)
    contrast = contrasts.loc[
        (contrasts["state_name"] == trend_geography) & (contrasts["age_band"] == trend_age)
    ].sort_values("survey_year")
    st.markdown("#### Black women minus Black men")
    st.caption("Each annual difference and 95% CI is calculated directly from the paired ACS replicate estimates. Cross-year significance is not tested.")
    visible_contrast = contrast.loc[~contrast[f"{trend_prefix}_is_suppressed"].astype(bool)]
    if visible_contrast.empty:
        st.warning("The direct comparison is suppressed for this selection.")
    else:
        st.dataframe(visible_contrast[[
            "survey_year", f"{trend_prefix}_estimate", f"{trend_prefix}_standard_error",
            f"{trend_prefix}_ci95_lower", f"{trend_prefix}_ci95_upper",
            f"{trend_prefix}_women_unweighted_n", f"{trend_prefix}_men_unweighted_n",
        ]], use_container_width=True, hide_index=True)

st.divider()
st.subheader("Phase 4: year-held-out model validation")
if model_metrics.empty:
    st.info("The Phase 4 aggregate model snapshot has not yet been published.")
else:
    st.caption(
        "Models train on 2022–2023 and are evaluated on untouched 2024 records. "
        "These are population-level predictive diagnostics, not individual scores or causal effects."
    )
    overall = model_metrics.loc[
        (model_metrics["group_type"] == "overall")
        & ~model_metrics["value_is_suppressed"].astype(bool)
    ].copy()
    if overall.empty:
        st.warning("Overall model metrics are suppressed under the published stability rules.")
    else:
        comparison = overall.pivot(index="model", columns="metric", values="value_estimate")
        comparison.index = comparison.index.map({
            "weighted_prevalence_baseline": "Weighted prevalence baseline",
            "survey_weighted_logistic": "Survey-weighted logistic",
        })
        st.dataframe(comparison.rename(columns={"brier_score": "Brier score", "log_loss": "Log loss"}), use_container_width=True)
        st.caption("Lower Brier score and log loss indicate better held-out predictive accuracy.")
    visible_calibration = model_calibration.loc[
        ~model_calibration["observed_rate_is_suppressed"].astype(bool)
        & ~model_calibration["mean_prediction_is_suppressed"].astype(bool)
    ].sort_values("calibration_bin")
    if not visible_calibration.empty:
        chart = visible_calibration.set_index("calibration_bin")[[
            "mean_prediction_estimate", "observed_rate_estimate"
        ]].rename(columns={"mean_prediction_estimate": "Mean prediction", "observed_rate_estimate": "Observed married rate"})
        st.markdown("#### 2024 calibration")
        st.line_chart(chart, x_label="Prediction decile", y_label="Rate")
    with st.expander("Model card"):
        st.json(model_card)

st.divider()
st.subheader("Phase 5: nonlinear challenger robustness")
if robustness_metrics.empty:
    st.info("The Phase 5 aggregate robustness snapshot has not yet been published.")
else:
    st.caption(
        "XGBoost is evaluated against the transparent logistic model on the same untouched 2024 records. "
        "Positive paired improvement means lower loss for XGBoost. No model is promoted automatically."
    )
    overall_challenger = robustness_comparisons.loc[
        (robustness_comparisons["reference_model"] == "survey_weighted_logistic")
        & (robustness_comparisons["challenger_model"] == "survey_weighted_xgboost")
        & (robustness_comparisons["group_type"] == "overall")
        & ~robustness_comparisons["improvement_is_suppressed"].astype(bool)
    ].copy()
    if robustness_card.get("promotion_gate_passed"):
        st.success("The preregistered overall paired-improvement gate passed. Promotion still requires human review.")
    else:
        st.warning("The preregistered overall paired-improvement gate did not pass; the challenger remains experimental.")
    if not overall_challenger.empty:
        st.dataframe(overall_challenger[[
            "metric", "improvement_estimate", "improvement_standard_error",
            "improvement_ci95_lower", "improvement_ci95_upper",
            "improvement_unweighted_n", "improvement_weighted_denominator",
        ]], use_container_width=True, hide_index=True)
    dimension = st.selectbox("Robustness subgroup dimension", ["sex", "age_band", "state", "sex_age"])
    available_groups = sorted(robustness_comparisons.loc[robustness_comparisons["group_type"] == dimension, "group"].astype(str).unique())
    selected_group = st.selectbox("Robustness subgroup", available_groups)
    subgroup = robustness_comparisons.loc[
        (robustness_comparisons["group_type"] == dimension)
        & (robustness_comparisons["group"].astype(str) == selected_group)
        & (robustness_comparisons["reference_model"] == "survey_weighted_logistic")
        & (robustness_comparisons["challenger_model"] == "survey_weighted_xgboost")
    ]
    st.dataframe(subgroup[[
        "metric", "improvement_estimate", "improvement_ci95_lower", "improvement_ci95_upper",
        "improvement_unweighted_n", "improvement_weighted_denominator", "improvement_is_suppressed",
    ]], use_container_width=True, hide_index=True)
    visible_features = robustness_features.nlargest(15, "gain_importance").sort_values("gain_importance")
    st.markdown("#### Aggregate model gain importance")
    st.bar_chart(visible_features.set_index("feature")[["gain_importance"]], horizontal=True)
    st.caption("Gain importance describes the fitted model, not causality or an individual explanation. SHAP is not published in this phase.")
    with st.expander("Phase 5 model card"):
        st.json(robustness_card)

st.caption("Dashboard data are a versioned snapshot of aggregated Gold outputs; the public application requires no AWS credentials and has no access to Census microdata.")
with st.expander("Methodology"):
    st.markdown("Estimates use 2022–2024 ACS 1-Year PUMS person records, restricted to RAC1P=2 (Black alone) and age 18+. SEX=2 identifies Black women and SEX=1 identifies the Black men benchmark. Employment includes ESR codes 1, 2, 4, and 5 among records in the ESR labor-force universe. Point estimates use PWGTP. Standard errors use all 80 PWGTP replicate weights and the Census ACS SDR factor 4/80; intervals are estimate ± 1.96 SE (bounded to [0,1] for rates). Direct annual contrasts subtract the two groups' estimates and their corresponding replicate estimates. Phase 4 fits a survey-weighted logistic benchmark on 2022–2023 and evaluates fixed predictions on 2024. Phase 5 evaluates a fixed XGBoost challenger on the same 2024 records and computes paired replicate-weight loss improvements as logistic loss minus challenger loss. Performance intervals condition on the fitted models and do not include model-refitting uncertainty. Every published metric retains its unweighted sample size and weighted denominator. Estimates are suppressed when unweighted n < 30, the denominator is nonpositive, or relative standard error exceeds 30%. Cross-year changes, coefficients, and feature importance are descriptive and are not causal claims. No person-level predictions are published.")
