import json
import math
import zipfile

import numpy as np
import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_inference import (
    METRICS, ReplicateEstimate, _benjamini_hochberg, _benjamini_hochberg_log10,
    _difference, build_inference,
)
from src.transform.publish_dashboard import build_candidates
from src.transform.reconcile_inference import reconcile_inference


def _frame() -> pd.DataFrame:
    rows = []
    ages = (20, 29, 39, 49, 59, 70)
    for state in (1, 2):
        for sex in (1, 2):
            for band, age in enumerate(ages):
                for i in range(10):
                    married_cutoff = 6 if sex == 2 else 4
                    row = {
                        "SERIALNO": f"{state}-{sex}-{band}-{i}", "SPORDER": 1,
                        "STATE": state, "PUMA": 100, "AGEP": age, "SEX": sex,
                        "RAC1P": 2, "MAR": 1 if i < married_cutoff else 5,
                        "SCHL": 21 if i < (5 if sex == 2 else 3) else 20,
                        "PINCP": 50000 + sex * 5000 + band * 1000 + i * 100,
                        "ESR": 1 if i < (8 if sex == 2 else 7) else 3,
                        "PWGTP": 100 + 5 * band,
                    }
                    row.update({
                        column: row["PWGTP"] + ((i + band + j) % 5 - 2)
                        for j, column in enumerate(PERSON_REPLICATE_WEIGHTS)
                    })
                    rows.append(row)
    return pd.DataFrame(rows)


def test_age_adjusted_inference_grain_and_contract():
    result, manifest = build_inference(_frame())
    assert len(result) == 12  # national + two states, four metrics
    assert set(result["metric"]) == set(METRICS)
    assert not result.duplicated(["state", "metric"], keep=False).any()
    assert math.isclose(sum(manifest["age_standard_weights"].values()), 1.0)
    assert manifest["multiplicity"].startswith("Benjamini-Hochberg")
    required = {
        "women_estimate", "men_estimate", "difference_estimate",
        "difference_standard_error", "difference_ci95_lower", "difference_ci95_upper",
        "difference_p_value", "difference_log10_p_value",
        "difference_p_value_below_machine_precision", "difference_q_value",
        "difference_log10_q_value", "difference_q_value_below_machine_precision",
        "difference_fdr_significant",
        "difference_is_suppressed", "difference_suppression_reason",
    }
    assert required <= set(result.columns)


def test_direct_difference_uses_paired_replicates_and_keeps_precise_nulls():
    reps = np.linspace(0.49, 0.51, 80)
    women = ReplicateEstimate(0.5, reps, 100, 10000)
    men = ReplicateEstimate(0.5, reps, 100, 10000)
    result = _difference(women, men, False, False, (-1.0, 1.0))
    assert result["estimate"] == 0
    assert result["standard_error"] == 0
    assert result["p_value"] == 1
    assert result["is_suppressed"] is False


def test_benjamini_hochberg_is_monotone_and_order_preserving():
    values = pd.Series([0.01, 0.04, 0.03], index=["a", "b", "c"])
    adjusted = _benjamini_hochberg(values)
    assert adjusted.to_dict() == pytest.approx({"a": 0.03, "b": 0.04, "c": 0.04})


def test_extreme_probabilities_remain_positive_and_retain_log_evidence():
    women = ReplicateEstimate(0.9, np.full(80, 0.899), 1000, 100000)
    men = ReplicateEstimate(0.1, np.full(80, 0.101), 1000, 100000)
    difference = _difference(women, men, False, False, (-1.0, 1.0))
    assert difference["p_value"] > 0
    assert difference["p_value_below_machine_precision"] is True
    assert difference["log10_p_value"] < -323
    adjusted = _benjamini_hochberg_log10(pd.Series([-500.0, -10.0]))
    assert (adjusted["q_value"] > 0).all()
    assert bool(adjusted.iloc[0]["underflow"])


def test_inference_reconciliation_detects_public_drift(tmp_path):
    source = _frame()
    csv_path = tmp_path / "source.csv"
    archive = tmp_path / "source.zip"
    silver = tmp_path / "silver.parquet"
    source.to_csv(csv_path, index=False)
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(csv_path, arcname="psam_pusa.csv")
    source.astype({
        "SERIALNO": "string", **{column: "Int64" for column in source.columns if column != "SERIALNO"},
    }).to_parquet(silver, index=False)
    inference, manifest = build_inference(pd.read_parquet(silver))
    gold, public = tmp_path / "gold", tmp_path / "public"
    gold.mkdir()
    inference.to_csv(gold / "inference.csv", index=False)
    (gold / "inference_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    build_candidates(gold, public, ("inference.csv",), "inference_manifest.json")
    report = reconcile_inference(archive, silver, gold, public)
    assert report["checks"] == ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"]
    drifted = pd.read_csv(public / "inference.csv")
    visible = ~drifted["difference_is_suppressed"].astype(bool)
    drifted.loc[visible.idxmax(), "difference_estimate"] += 0.01
    drifted.to_csv(public / "inference.csv", index=False)
    with pytest.raises(AssertionError, match="Gold-to-published inference"):
        reconcile_inference(archive, silver, gold, public)
