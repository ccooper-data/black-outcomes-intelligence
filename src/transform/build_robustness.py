"""Build Phase 5 nonlinear challenger and survey-aware robustness evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from src.transform.build_longitudinal import validate_years
from src.transform.build_models import (
    CATEGORICAL_FEATURES,
    EPSILON,
    HOLDOUT_YEAR,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    OUTCOME,
    TRAIN_YEARS,
    _age_band,
    _fit_rows,
    _metric,
    _pipeline,
    _population,
)
from src.transform.survey import flatten_metric

MODELS = ("weighted_prevalence_baseline", "survey_weighted_logistic", "survey_weighted_xgboost")
METRICS = ("brier_score", "log_loss")


def _groups(frame: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    bands = _age_band(frame["AGEP"])
    groups: list[tuple[str, str, np.ndarray]] = [
        ("overall", "All Black adults", np.ones(len(frame), dtype=bool)),
        ("sex", "Black women", (frame["SEX"] == 2).to_numpy()),
        ("sex", "Black men", (frame["SEX"] == 1).to_numpy()),
    ]
    groups.extend(("age_band", str(label), (bands == label).fillna(False).to_numpy()) for label in bands.dropna().unique())
    groups.extend(
        ("state", str(int(state)), (frame["STATE"] == state).to_numpy())
        for state in sorted(frame["STATE"].dropna().unique())
    )
    for sex, sex_label in ((2, "Black women"), (1, "Black men")):
        groups.extend(
            ("sex_age", f"{sex_label} · {label}", ((frame["SEX"] == sex) & (bands == label).fillna(False)).to_numpy())
            for label in bands.dropna().unique()
        )
    return groups


def _losses(y: np.ndarray, probability: np.ndarray) -> dict[str, np.ndarray]:
    p = np.clip(probability, EPSILON, 1 - EPSILON)
    return {
        "brier_score": np.square(y - p),
        "log_loss": -(y * np.log(p) + (1 - y) * np.log(1 - p)),
    }


def _fit_predictions(frames: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, np.ndarray], XGBClassifier, ColumnTransformer]:
    fit = _fit_rows(frames)
    holdout = _population(frames[HOLDOUT_YEAR])
    logistic = _pipeline()
    logistic.fit(fit[MODEL_FEATURES], fit[OUTCOME], model__sample_weight=fit["fit_weight"])

    transform = ColumnTransformer([
        ("age", StandardScaler(), NUMERIC_FEATURES),
        ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    x_fit = transform.fit_transform(fit[MODEL_FEATURES])
    x_holdout = transform.transform(holdout[MODEL_FEATURES])
    challenger = XGBClassifier(
        n_estimators=150, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=20,
        reg_lambda=1.0, objective="binary:logistic", eval_metric="logloss",
        tree_method="hist", random_state=2024, n_jobs=2,
    )
    challenger.fit(x_fit, fit[OUTCOME], sample_weight=fit["fit_weight"], verbose=False)
    prevalence = float(np.average(fit[OUTCOME], weights=fit["fit_weight"]))
    predictions = {
        "weighted_prevalence_baseline": np.full(len(holdout), prevalence),
        "survey_weighted_logistic": logistic.predict_proba(holdout[MODEL_FEATURES])[:, 1],
        "survey_weighted_xgboost": challenger.predict_proba(x_holdout)[:, 1],
    }
    return holdout, predictions, challenger, transform


def _metric_rows(frame: pd.DataFrame, predictions: dict[str, np.ndarray]) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = frame[OUTCOME].to_numpy(dtype=float)
    losses = {model: _losses(y, prediction) for model, prediction in predictions.items()}
    metrics: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []
    groups = _groups(frame)
    for group_type, group, mask in groups:
        subset = frame.loc[mask]
        for model in MODELS:
            for metric in METRICS:
                row = {"model": model, "evaluation_year": HOLDOUT_YEAR, "group_type": group_type, "group": group, "metric": metric}
                row.update(flatten_metric("value", _metric(losses[model][metric][mask], subset)))
                metrics.append(row)
        for reference, challenger in (
            ("weighted_prevalence_baseline", "survey_weighted_logistic"),
            ("survey_weighted_logistic", "survey_weighted_xgboost"),
        ):
            for metric in METRICS:
                improvement = losses[reference][metric][mask] - losses[challenger][metric][mask]
                row = {
                    "reference_model": reference, "challenger_model": challenger,
                    "evaluation_year": HOLDOUT_YEAR, "group_type": group_type,
                    "group": group, "metric": metric,
                }
                row.update(flatten_metric("improvement", _metric(improvement, subset)))
                comparisons.append(row)
    return pd.DataFrame(metrics), pd.DataFrame(comparisons)


def _calibration(frame: pd.DataFrame, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model in ("survey_weighted_logistic", "survey_weighted_xgboost"):
        work = frame.copy()
        work["prediction"] = np.clip(predictions[model], EPSILON, 1 - EPSILON)
        ordered = work.sort_values(["prediction", "SERIALNO", "SPORDER"], kind="mergesort")
        cumulative = ordered["PWGTP"].astype(float).cumsum()
        ordered["bin"] = np.minimum(((cumulative - 1) / cumulative.iloc[-1] * 10).astype(int), 9)
        work["bin"] = ordered["bin"].reindex(work.index)
        for bin_id, group in work.groupby("bin", sort=True):
            observed = _metric(group[OUTCOME].to_numpy(dtype=float), group, (0.0, 1.0))
            predicted = _metric(group["prediction"].to_numpy(dtype=float), group, (0.0, 1.0))
            row = {"model": model, "evaluation_year": HOLDOUT_YEAR, "calibration_bin": int(bin_id) + 1}
            row.update(flatten_metric("observed_rate", observed))
            row.update(flatten_metric("mean_prediction", predicted))
            rows.append(row)
    return pd.DataFrame(rows)


def build_robustness_outputs(frames: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    validate_years(frames)
    holdout, predictions, challenger, transform = _fit_predictions(frames)
    metrics, comparisons = _metric_rows(holdout, predictions)
    calibration = _calibration(holdout, predictions)
    importance = pd.DataFrame({
        "feature": transform.get_feature_names_out(),
        "gain_importance": challenger.feature_importances_.astype(float),
    }).sort_values(["gain_importance", "feature"], ascending=[False, True]).head(30).reset_index(drop=True)
    importance["rank"] = np.arange(1, len(importance) + 1)
    importance = importance[["rank", "feature", "gain_importance"]]

    overall = comparisons.loc[
        (comparisons["reference_model"] == "survey_weighted_logistic")
        & (comparisons["challenger_model"] == "survey_weighted_xgboost")
        & (comparisons["group_type"] == "overall")
    ]
    promotion_gate = bool(
        len(overall) == 2
        and (~overall["improvement_is_suppressed"].astype(bool)).all()
        and (overall["improvement_ci95_lower"] > 0).all()
    )
    manifest = {
        "phase": 5,
        "purpose": "aggregate nonlinear challenger evaluation; not individual scoring or causal inference",
        "training_years": list(TRAIN_YEARS), "holdout_year": HOLDOUT_YEAR,
        "models": list(MODELS), "metrics": list(METRICS),
        "subgroup_dimensions": ["sex", "age_band", "state", "sex_age"],
        "paired_improvement_definition": "reference loss minus challenger loss on identical records and replicate weights; positive favors challenger",
        "performance_uncertainty": "80 ACS person replicate weights with SDR factor 4/80; fitted predictions held fixed",
        "xgboost_parameters": {
            "n_estimators": 150, "max_depth": 4, "learning_rate": 0.05,
            "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 20,
            "reg_lambda": 1.0, "objective": "binary:logistic", "eval_metric": "logloss",
            "tree_method": "hist", "random_state": 2024, "n_jobs": 2,
        },
        "runtime_versions": {"xgboost": xgboost.__version__, "scikit_learn": sklearn.__version__},
        "feature_importance_interpretation": "model gain importance; associational, not SHAP, causal, or person-level explanation",
        "automatic_promotion": False,
        "promotion_gate_passed": promotion_gate,
        "promotion_rule": "both overall paired Brier and log-loss improvement 95% CIs must be strictly above zero",
        "person_level_predictions_published": False,
    }
    return metrics, comparisons, calibration, importance, manifest


def _parse(values: list[str]) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for value in values:
        year, separator, path = value.partition("=")
        if not separator:
            raise ValueError("--silver values must use YEAR=PATH")
        result[int(year)] = Path(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--silver", action="append", required=True, metavar="YEAR=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    frames = {year: pd.read_parquet(path) for year, path in _parse(args.silver).items()}
    outputs = build_robustness_outputs(frames)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(("robustness_metrics", "robustness_comparisons", "robustness_calibration", "robustness_features"), outputs[:4]):
        frame.to_csv(args.output_dir / f"{name}.csv", index=False)
    (args.output_dir / "robustness_card.json").write_text(json.dumps(outputs[4], indent=2) + "\n")


if __name__ == "__main__":
    main()
