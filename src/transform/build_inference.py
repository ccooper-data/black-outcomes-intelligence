"""Build Phase 7 age-adjusted, survey-aware Black women-minus-men inference."""
from __future__ import annotations

import argparse
import json
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from src.transform.build_marts import AGE_BANDS, validate
from src.transform.survey import (
    ReplicateEstimate,
    estimate_mean,
    estimate_ratio,
    flatten_metric,
    replicate_standard_error,
    result_from_replicates,
    Z_95,
)

YEAR = 2024
METRICS = ("married_rate", "bachelors_plus_rate", "employment_rate", "mean_personal_income")
REFERENCE_NAME = "2024 national Black-adult age distribution"


def _age_mask(frame: pd.DataFrame, low: int, high: int | None) -> pd.Series:
    return (frame["AGEP"] >= low) & ((frame["AGEP"] <= high) if high is not None else True)


def _estimand(frame: pd.DataFrame, metric: str) -> ReplicateEstimate:
    if metric == "married_rate":
        return estimate_ratio(frame, frame["MAR"] == 1)
    if metric == "bachelors_plus_rate":
        return estimate_ratio(frame, frame["SCHL"] >= 21)
    if metric == "employment_rate":
        employed = frame["ESR"].isin([1, 2, 4, 5])
        labor_force = frame["ESR"].isin([1, 2, 3, 4, 5, 6])
        return estimate_ratio(frame, employed, labor_force)
    if metric == "mean_personal_income":
        return estimate_mean(frame, frame["PINCP"])
    raise ValueError(f"Unsupported inference metric: {metric}")


def _standard_distribution(adults: pd.DataFrame) -> tuple[ReplicateEstimate, ...]:
    return tuple(
        estimate_ratio(adults, _age_mask(adults, low, high))
        for _, low, high in AGE_BANDS
    )


def _standardized(group: pd.DataFrame, metric: str,
                  standard: tuple[ReplicateEstimate, ...]) -> ReplicateEstimate:
    strata = [
        _estimand(group.loc[_age_mask(group, low, high)], metric)
        for _, low, high in AGE_BANDS
    ]
    estimate = float(sum(weight.estimate * value.estimate for weight, value in zip(standard, strata)))
    replicates = np.sum(
        np.stack([weight.replicates * value.replicates for weight, value in zip(standard, strata)]),
        axis=0,
    )
    return ReplicateEstimate(
        estimate,
        replicates,
        sum(value.unweighted_n for value in strata),
        sum(value.weighted_denominator for value in strata),
    )


def _difference(women: ReplicateEstimate, men: ReplicateEstimate,
                women_suppressed: bool, men_suppressed: bool,
                bounds: tuple[float, float] | None = None) -> dict[str, object]:
    estimate = women.estimate - men.estimate
    replicates = women.replicates - men.replicates
    se = replicate_standard_error(estimate, replicates)
    reasons: list[str] = []
    if women_suppressed or men_suppressed:
        reasons.append("component_estimate_suppressed")
    if min(women.unweighted_n, men.unweighted_n) < 30:
        reasons.append("component_unweighted_n_below_30")
    if min(women.weighted_denominator, men.weighted_denominator) <= 0:
        reasons.append("nonpositive_component_weighted_denominator")
    if not np.isfinite(estimate) or not np.isfinite(se):
        reasons.append("nonfinite_difference_or_standard_error")
    low = estimate - Z_95 * se if np.isfinite(se) else float("nan")
    high = estimate + Z_95 * se if np.isfinite(se) else float("nan")
    if bounds and np.isfinite(se):
        low, high = max(bounds[0], low), min(bounds[1], high)
    if np.isfinite(se) and se > 0:
        p_value = erfc(abs(estimate / se) / sqrt(2.0))
    elif np.isfinite(estimate) and estimate == 0:
        p_value = 1.0
    else:
        p_value = 0.0
    return {
        "estimate": float(estimate),
        "standard_error": float(se),
        "ci95_lower": float(low),
        "ci95_upper": float(high),
        "relative_standard_error": (
            float(se / abs(estimate)) if estimate != 0 else float("inf")
        ),
        "unweighted_n": min(women.unweighted_n, men.unweighted_n),
        "weighted_denominator": min(women.weighted_denominator, men.weighted_denominator),
        "p_value": float(p_value),
        "q_value": float("nan"),
        "fdr_significant": False,
        "is_suppressed": bool(reasons),
        "suppression_reason": ";".join(reasons),
    }


def _benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    """Return monotone Benjamini-Hochberg adjusted p-values."""
    if p_values.empty:
        return p_values.astype(float)
    ordered = p_values.sort_values(kind="mergesort")
    m = len(ordered)
    adjusted = ordered.to_numpy(dtype=float) * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    return pd.Series(np.minimum(adjusted, 1.0), index=ordered.index).reindex(p_values.index)


def build_inference(frame: pd.DataFrame, year: int = YEAR) -> tuple[pd.DataFrame, dict[str, object]]:
    """Build national and state age-standardized contrasts with FDR control."""
    validate(frame)
    adults = frame.loc[(frame["RAC1P"] == 2) & (frame["AGEP"] >= 18)].copy()
    standard = _standard_distribution(adults)
    geographies = [(None, adults), *[(int(state), group) for state, group in adults.groupby("STATE", sort=True)]]
    rows: list[dict[str, object]] = []
    for state, geography in geographies:
        women_frame = geography.loc[geography["SEX"] == 2]
        men_frame = geography.loc[geography["SEX"] == 1]
        for metric in METRICS:
            women = _standardized(women_frame, metric, standard)
            men = _standardized(men_frame, metric, standard)
            bounds = (0.0, 1.0) if metric.endswith("_rate") else None
            women_result = result_from_replicates(women, bounds=bounds)
            men_result = result_from_replicates(men, bounds=bounds)
            difference = _difference(
                women, men,
                bool(women_result["is_suppressed"]), bool(men_result["is_suppressed"]),
                (-1.0, 1.0) if metric.endswith("_rate") else None,
            )
            row: dict[str, object] = {
                "state": state,
                "survey_year": year,
                "metric": metric,
                "comparison": "Black women minus Black men",
                "method": "direct age standardization with paired ACS replicate differences",
            }
            row.update(flatten_metric("women", women_result))
            row.update(flatten_metric("men", men_result))
            row.update(flatten_metric("difference", difference))
            rows.append(row)
    result = pd.DataFrame(rows)
    for metric in METRICS:
        national = (result["metric"] == metric) & result["state"].isna() & ~result["difference_is_suppressed"]
        result.loc[national, "difference_q_value"] = result.loc[national, "difference_p_value"]
        states = (result["metric"] == metric) & result["state"].notna() & ~result["difference_is_suppressed"]
        result.loc[states, "difference_q_value"] = _benjamini_hochberg(
            result.loc[states, "difference_p_value"]
        )
    result["difference_fdr_significant"] = (
        result["difference_q_value"].le(0.05) & ~result["difference_is_suppressed"]
    )
    manifest = {
        "phase": 7,
        "year": year,
        "population": "Black-alone adults age 18+ (RAC1P = 2)",
        "comparison": "Black women minus Black men",
        "metrics": list(METRICS),
        "age_bands": [label for label, _, _ in AGE_BANDS],
        "age_standard": REFERENCE_NAME,
        "age_standard_weights": {
            label: weight.estimate for (label, _, _), weight in zip(AGE_BANDS, standard)
        },
        "variance": "80 ACS person replicate weights; SDR factor 4/80",
        "testing": "two-sided normal test from the direct replicate-weight contrast standard error",
        "multiplicity": "Benjamini-Hochberg FDR within each metric across 51 state comparisons; national q=p",
        "causal_interpretation": False,
        "rows": len(result),
    }
    return result, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, default=YEAR)
    args = parser.parse_args()
    frame = pd.read_parquet(args.silver)
    inference, manifest = build_inference(frame, args.year)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    inference.to_csv(args.output_dir / "inference.csv", index=False)
    (args.output_dir / "inference_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
