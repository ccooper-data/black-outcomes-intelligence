"""Build a survey-weighted, year-held-out population modeling benchmark.

This module evaluates aggregate predictive performance. It never emits person-level
predictions and does not claim that model associations are causal.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_longitudinal import YEARS, validate_years
from src.transform.survey import ReplicateEstimate, SuppressionPolicy, flatten_metric, result_from_replicates

TRAIN_YEARS = (2022, 2023)
HOLDOUT_YEAR = 2024
OUTCOME = "married"
NUMERIC_FEATURES = ["AGEP"]
CATEGORICAL_FEATURES = ["SEX", "STATE", "SCHL", "employment_status"]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
EPSILON = 1e-12


def _population(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.loc[(frame["RAC1P"] == 2) & (frame["AGEP"] >= 18)].copy()
    result["employment_status"] = np.select(
        [result["ESR"].isin([1, 2, 4, 5]), result["ESR"].isin([3, 6])],
        ["employed", "unemployed"], default="not_in_labor_force",
    )
    result[OUTCOME] = (result["MAR"] == 1).astype(int)
    return result


def _fit_rows(frames: dict[int, pd.DataFrame]) -> pd.DataFrame:
    train = pd.concat([_population(frames[year]) for year in TRAIN_YEARS], ignore_index=True)
    train["weighted_positive"] = train["PWGTP"] * train[OUTCOME]
    grouped = train.groupby(MODEL_FEATURES, observed=True, dropna=False).agg(
        weight=("PWGTP", "sum"), positive=("weighted_positive", "sum")
    ).reset_index()
    positive = grouped.loc[grouped["positive"] > 0, MODEL_FEATURES].copy()
    positive[OUTCOME] = 1
    positive["fit_weight"] = grouped.loc[grouped["positive"] > 0, "positive"].to_numpy()
    negative_weight = grouped["weight"] - grouped["positive"]
    negative = grouped.loc[negative_weight > 0, MODEL_FEATURES].copy()
    negative[OUTCOME] = 0
    negative["fit_weight"] = negative_weight.loc[negative_weight > 0].to_numpy()
    return pd.concat([positive, negative], ignore_index=True)


def _pipeline() -> Pipeline:
    transform = ColumnTransformer([
        ("age", StandardScaler(), NUMERIC_FEATURES),
        ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([
        ("features", transform),
        ("model", LogisticRegression(C=1.0, solver="lbfgs", max_iter=500, random_state=2024)),
    ])


def _age_band(age: pd.Series) -> pd.Series:
    return pd.cut(
        age, bins=[17, 24, 34, 44, 54, 64, np.inf],
        labels=["18–24", "25–34", "35–44", "45–54", "55–64", "65+"],
    ).astype("string")


def _metric(loss: np.ndarray, frame: pd.DataFrame,
            bounds: tuple[float, float] | None = None) -> dict[str, object]:
    main = frame["PWGTP"].to_numpy(dtype=float)
    reps = frame[list(PERSON_REPLICATE_WEIGHTS)].to_numpy(dtype=float)
    denominator = float(main.sum())
    rep_denominators = reps.sum(axis=0)
    estimate = float(loss @ main / denominator)
    replicate_estimates = np.divide(loss @ reps, rep_denominators)
    return result_from_replicates(
        ReplicateEstimate(estimate, replicate_estimates, len(frame), denominator),
        SuppressionPolicy(), bounds=bounds,
    )


def _evaluation_rows(frame: pd.DataFrame, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    groups: list[tuple[str, str, np.ndarray]] = [("overall", "All Black adults", np.ones(len(frame), dtype=bool))]
    groups.extend(("sex", label, (frame["SEX"] == code).to_numpy()) for code, label in ((2, "Black women"), (1, "Black men")))
    bands = _age_band(frame["AGEP"])
    groups.extend(("age_band", label, (bands == label).fillna(False).to_numpy()) for label in bands.dropna().unique())
    y = frame[OUTCOME].to_numpy(dtype=float)
    rows: list[dict[str, object]] = []
    for model_name, probability in predictions.items():
        probability = np.clip(probability, EPSILON, 1 - EPSILON)
        losses = {
            "brier_score": np.square(y - probability),
            "log_loss": -(y * np.log(probability) + (1 - y) * np.log(1 - probability)),
        }
        for group_type, group, mask in groups:
            subset = frame.loc[mask]
            for metric_name, loss in losses.items():
                row = {
                    "model": model_name, "evaluation_year": HOLDOUT_YEAR,
                    "group_type": group_type, "group": group, "metric": metric_name,
                }
                row.update(flatten_metric("value", _metric(loss[mask], subset)))
                rows.append(row)
    return pd.DataFrame(rows)


def _calibration_rows(frame: pd.DataFrame, probability: np.ndarray) -> pd.DataFrame:
    work = frame.copy()
    work["prediction"] = np.clip(probability, EPSILON, 1 - EPSILON)
    # Survey-weighted deciles keep calibration groups comparable in represented
    # population rather than merely equal in raw PUMS record count.
    ordered = work.sort_values(["prediction", "SERIALNO", "SPORDER"], kind="mergesort")
    cumulative = ordered["PWGTP"].astype(float).cumsum()
    ordered["bin"] = np.minimum(((cumulative - 1) / cumulative.iloc[-1] * 10).astype(int), 9)
    work["bin"] = ordered["bin"].reindex(work.index)
    rows: list[dict[str, object]] = []
    for bin_id, group in work.groupby("bin", sort=True):
        observed = _metric(group[OUTCOME].to_numpy(dtype=float), group, (0.0, 1.0))
        predicted = _metric(group["prediction"].to_numpy(dtype=float), group, (0.0, 1.0))
        row = {"model": "survey_weighted_logistic", "evaluation_year": HOLDOUT_YEAR, "calibration_bin": int(bin_id) + 1}
        row.update(flatten_metric("observed_rate", observed))
        row.update(flatten_metric("mean_prediction", predicted))
        rows.append(row)
    return pd.DataFrame(rows)


def build_model_outputs(frames: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Fit on 2022–2023 and evaluate only on 2024."""
    validate_years(frames)
    fit = _fit_rows(frames)
    model = _pipeline()
    model.fit(fit[MODEL_FEATURES], fit[OUTCOME], model__sample_weight=fit["fit_weight"])
    holdout = _population(frames[HOLDOUT_YEAR])
    probability = model.predict_proba(holdout[MODEL_FEATURES])[:, 1]
    training_prevalence = float(np.average(fit[OUTCOME], weights=fit["fit_weight"]))
    predictions = {
        "weighted_prevalence_baseline": np.full(len(holdout), training_prevalence),
        "survey_weighted_logistic": probability,
    }
    metrics = _evaluation_rows(holdout, predictions)
    calibration = _calibration_rows(holdout, probability)
    coefficients = model.named_steps["model"].coef_[0]
    feature_names = model.named_steps["features"].get_feature_names_out()
    coefficient_summary = sorted(
        ({"feature": str(name), "coefficient": float(value)} for name, value in zip(feature_names, coefficients)),
        key=lambda item: abs(item["coefficient"]), reverse=True,
    )[:20]
    manifest = {
        "phase": 4,
        "purpose": "population-level predictive benchmark; not individual scoring or causal inference",
        "outcome": "MAR == 1 among Black-alone adults age 18+",
        "training_years": list(TRAIN_YEARS),
        "holdout_year": HOLDOUT_YEAR,
        "models": list(predictions),
        "features": MODEL_FEATURES,
        "training_rows": int(sum(len(_population(frames[y])) for y in TRAIN_YEARS)),
        "holdout_rows": int(len(holdout)),
        "performance_uncertainty": "80 ACS person replicate weights with SDR factor 4/80; fitted model held fixed",
        "coefficient_interpretation": "associational, conditional on included features; not causal",
        "largest_absolute_coefficients": coefficient_summary,
        "person_level_predictions_published": False,
    }
    return metrics, calibration, manifest


def _parse(values: list[str]) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        year, separator, path = value.partition("=")
        if not separator:
            raise ValueError("--silver values must use YEAR=PATH")
        parsed[int(year)] = Path(path)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", action="append", required=True, metavar="YEAR=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    frames = {year: pd.read_parquet(path) for year, path in _parse(args.silver).items()}
    metrics, calibration, manifest = build_model_outputs(frames)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / "model_metrics.csv", index=False)
    calibration.to_csv(args.output_dir / "model_calibration.csv", index=False)
    (args.output_dir / "model_card.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
