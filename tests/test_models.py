import json
import zipfile

import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_models import build_model_outputs
from src.transform.publish_dashboard import build_candidates
from src.transform.reconcile_models import reconcile_models


def _frame(year: int) -> pd.DataFrame:
    rows = []
    for state in (1, 2):
        for sex in (1, 2):
            for i in range(50):
                weight = 80 + sex * 5 + (i % 4)
                married = (i + sex + year) % 3 != 0
                row = {
                    "SERIALNO": f"{year}-{state}-{sex}-{i}", "SPORDER": 1,
                    "STATE": state, "PUMA": 100, "AGEP": 18 + (i % 48),
                    "SEX": sex, "RAC1P": 2, "MAR": 1 if married else 5,
                    "SCHL": 21 if i % 3 else 18, "PINCP": 22000 + i * 700,
                    "ESR": 1 if i % 4 else 6, "PWGTP": weight,
                }
                row.update({name: weight + ((i + j) % 3 - 1) for j, name in enumerate(PERSON_REPLICATE_WEIGHTS)})
                rows.append(row)
    return pd.DataFrame(rows)


def _frames():
    return {year: _frame(year) for year in (2022, 2023, 2024)}


def test_model_is_year_held_out_aggregate_and_replicate_weighted():
    metrics, calibration, card = build_model_outputs(_frames())
    assert card["training_years"] == [2022, 2023]
    assert card["holdout_year"] == 2024
    assert card["person_level_predictions_published"] is False
    assert set(metrics["model"]) == {"weighted_prevalence_baseline", "survey_weighted_logistic"}
    assert set(metrics["metric"]) == {"brier_score", "log_loss"}
    assert (metrics["evaluation_year"] == 2024).all()
    assert metrics["value_standard_error"].notna().all()
    assert len(calibration) >= 2
    assert calibration["observed_rate_weighted_denominator"].gt(0).all()


def test_model_outputs_are_deterministic_and_reconciled(tmp_path):
    frames = _frames()
    sources, silvers = {}, {}
    for year, frame in frames.items():
        csv = tmp_path / f"source-{year}.csv"
        source = tmp_path / f"source-{year}.zip"
        silver = tmp_path / f"silver-{year}.parquet"
        frame.to_csv(csv, index=False)
        with zipfile.ZipFile(source, "w") as bundle:
            bundle.write(csv, arcname="psam_pusa.csv")
        frame.astype({"SERIALNO": "string", **{c: "Int64" for c in frame if c != "SERIALNO"}}).to_parquet(silver, index=False)
        sources[year], silvers[year] = source, silver
    metrics, calibration, card = build_model_outputs({year: pd.read_parquet(path) for year, path in silvers.items()})
    gold, public = tmp_path / "gold", tmp_path / "public"
    gold.mkdir()
    metrics.to_csv(gold / "model_metrics.csv", index=False)
    calibration.to_csv(gold / "model_calibration.csv", index=False)
    (gold / "model_card.json").write_text(json.dumps(card, indent=2) + "\n")
    build_candidates(gold, public, ("model_metrics.csv", "model_calibration.csv"), "model_card.json")
    report = reconcile_models(sources, silvers, gold, public)
    assert report["checks"] == ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"]
    drift = pd.read_csv(public / "model_metrics.csv")
    visible = ~drift["value_is_suppressed"].astype(bool)
    drift.loc[visible.idxmax(), "value_estimate"] += 0.01
    drift.to_csv(public / "model_metrics.csv", index=False)
    with pytest.raises(AssertionError, match="Gold-to-published model metrics"):
        reconcile_models(sources, silvers, gold, public)
