import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_robustness import build_robustness_outputs
from src.transform.publish_dashboard import build_candidates
from src.transform.reconcile_robustness import reconcile_robustness


def _frame(year: int) -> pd.DataFrame:
    rows = []
    for state in (1, 2):
        for sex in (1, 2):
            for i in range(72):
                age = 18 + (i % 52)
                weight = 70 + sex * 4 + (i % 5)
                # Nonlinear age pattern gives the tree challenger a real but
                # deterministic signal without asserting it must win.
                married = ((age // 8 + sex + state + year) % 3) != 0
                row = {
                    "SERIALNO": f"{year}-{state}-{sex}-{i}", "SPORDER": 1,
                    "STATE": state, "PUMA": 100, "AGEP": age, "SEX": sex,
                    "RAC1P": 2, "MAR": 1 if married else 5,
                    "SCHL": 16 + (i % 8), "PINCP": 20000 + i * 800,
                    "ESR": (1, 3, 6)[i % 3], "PWGTP": weight,
                }
                row.update({name: weight + ((i + j) % 3 - 1) for j, name in enumerate(PERSON_REPLICATE_WEIGHTS)})
                rows.append(row)
    return pd.DataFrame(rows)


def _frames():
    return {year: _frame(year) for year in (2022, 2023, 2024)}


def test_phase5_outputs_are_aggregate_paired_and_intersectional():
    metrics, comparisons, calibration, importance, card = build_robustness_outputs(_frames())
    assert set(metrics.model) == {
        "weighted_prevalence_baseline", "survey_weighted_logistic", "survey_weighted_xgboost"
    }
    assert {"state", "sex_age"} <= set(metrics.group_type)
    assert set(comparisons.challenger_model) == {"survey_weighted_logistic", "survey_weighted_xgboost"}
    assert comparisons["improvement_standard_error"].notna().all()
    overall = metrics.query("group_type == 'overall'").set_index(["model", "metric"])
    paired = comparisons.query(
        "group_type == 'overall' and reference_model == 'survey_weighted_logistic' and challenger_model == 'survey_weighted_xgboost'"
    ).set_index("metric")
    for metric in ("brier_score", "log_loss"):
        expected = overall.loc[("survey_weighted_logistic", metric), "value_estimate"] - overall.loc[("survey_weighted_xgboost", metric), "value_estimate"]
        assert paired.loc[metric, "improvement_estimate"] == pytest.approx(expected)
    assert set(calibration.model) == {"survey_weighted_logistic", "survey_weighted_xgboost"}
    assert importance.gain_importance.ge(0).all() and len(importance) <= 30
    assert card["automatic_promotion"] is False
    assert card["person_level_predictions_published"] is False


def test_phase5_reconciliation_detects_public_drift(tmp_path):
    frames = _frames()
    sources, silvers = {}, {}
    for year, frame in frames.items():
        csv_path = tmp_path / f"source-{year}.csv"
        source = tmp_path / f"source-{year}.zip"
        silver = tmp_path / f"silver-{year}.parquet"
        frame.to_csv(csv_path, index=False)
        with zipfile.ZipFile(source, "w") as bundle:
            bundle.write(csv_path, arcname="psam_pusa.csv")
        frame.astype({"SERIALNO": "string", **{c: "Int64" for c in frame if c != "SERIALNO"}}).to_parquet(silver, index=False)
        sources[year], silvers[year] = source, silver
    outputs = build_robustness_outputs({year: pd.read_parquet(path) for year, path in silvers.items()})
    gold, public = tmp_path / "gold", tmp_path / "public"
    gold.mkdir()
    names = ("robustness_metrics", "robustness_comparisons", "robustness_calibration", "robustness_features")
    for name, frame in zip(names, outputs[:4]):
        frame.to_csv(gold / f"{name}.csv", index=False)
    (gold / "robustness_card.json").write_text(json.dumps(outputs[4], indent=2) + "\n")
    build_candidates(gold, public, tuple(f"{name}.csv" for name in names), "robustness_card.json")
    report = reconcile_robustness(sources, silvers, gold, public)
    assert report["checks"] == ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"]
    drift = pd.read_csv(public / "robustness_comparisons.csv")
    visible = ~drift["improvement_is_suppressed"].astype(bool)
    drift.loc[visible.idxmax(), "improvement_estimate"] += 0.01
    drift.to_csv(public / "robustness_comparisons.csv", index=False)
    with pytest.raises(AssertionError, match="Gold-to-published robustness_comparisons"):
        reconcile_robustness(sources, silvers, gold, public)
