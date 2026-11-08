import math
import json
import zipfile

import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_longitudinal import build_contrasts, build_longitudinal, validate_years
from src.transform.publish_dashboard import build_candidates
from src.transform.reconcile_longitudinal import reconcile_longitudinal


def _frame(shift: int = 0) -> pd.DataFrame:
    rows = []
    for state in (1, 2):
        for sex in (1, 2):
            for i in range(42):
                weight = 100 + (20 if sex == 2 else 0)
                row = {
                    "SERIALNO": f"{state}-{sex}-{i}", "SPORDER": 1, "STATE": state,
                    "PUMA": 100, "AGEP": 18 + i, "SEX": sex, "RAC1P": 2,
                    "MAR": 1 if (i + shift + sex) % 2 else 5,
                    "SCHL": 21 if (i + shift + sex) % 3 else 20,
                    "PINCP": 25000 + shift * 500 + i * 1000 + sex * 1000,
                    "ESR": 1 if i % 4 else 3, "PWGTP": weight,
                }
                row.update({c: weight + ((i + j) % 3 - 1) for j, c in enumerate(PERSON_REPLICATE_WEIGHTS)})
                rows.append(row)
    return pd.DataFrame(rows)


def test_longitudinal_grain_schema_and_years():
    frames = {2022: _frame(0), 2023: _frame(1), 2024: _frame(2)}
    trends, contrasts, manifest = build_longitudinal(frames)
    assert len(trends) == 126
    assert len(contrasts) == 63
    assert set(trends.survey_year) == {2022, 2023, 2024}
    assert manifest["cross_year_significance_tested"] is False
    assert not trends.duplicated(["survey_year", "state", "sex", "age_band"], keep=False).any()
    assert not contrasts.duplicated(["survey_year", "state", "age_band"], keep=False).any()


def test_direct_contrast_recomputes_paired_replicates():
    row = build_contrasts(_frame(), 2024).query("state != state and age_band == 'All ages'").iloc[0]
    assert row["black_population_estimate"] == 1680
    assert math.isfinite(row["black_population_standard_error"])
    assert row["black_population_women_unweighted_n"] == 84
    assert row["black_population_men_unweighted_n"] == 84


def test_schema_drift_and_missing_years_fail_closed():
    frames = {2022: _frame(), 2023: _frame(), 2024: _frame()}
    frames[2023]["PWGTP"] = frames[2023]["PWGTP"].astype(float)
    with pytest.raises(ValueError, match="schema drift"):
        validate_years(frames)
    with pytest.raises(ValueError, match="Expected ACS years"):
        validate_years({2022: _frame(), 2024: _frame()})


def test_three_year_source_to_publication_reconciliation_detects_drift(tmp_path):
    frames = {year: _frame(year - 2022) for year in (2022, 2023, 2024)}
    source_paths, silver_paths = {}, {}
    for year, frame in frames.items():
        csv_path = tmp_path / f"source-{year}.csv"
        source_path = tmp_path / f"source-{year}.zip"
        silver_path = tmp_path / f"silver-{year}.parquet"
        frame.to_csv(csv_path, index=False)
        with zipfile.ZipFile(source_path, "w") as bundle:
            bundle.write(csv_path, arcname="psam_pusa.csv")
        frame.astype({"SERIALNO": "string", **{c: "Int64" for c in frame.columns if c != "SERIALNO"}}).to_parquet(silver_path, index=False)
        source_paths[year], silver_paths[year] = source_path, silver_path
    trends, contrasts, manifest = build_longitudinal({year: pd.read_parquet(path) for year, path in silver_paths.items()})
    gold_dir, published_dir = tmp_path / "gold", tmp_path / "published"
    gold_dir.mkdir()
    trends.to_csv(gold_dir / "trends.csv", index=False)
    contrasts.to_csv(gold_dir / "contrasts.csv", index=False)
    (gold_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    build_candidates(gold_dir, published_dir, ("trends.csv", "contrasts.csv"))
    report = reconcile_longitudinal(source_paths, silver_paths, gold_dir, published_dir)
    assert report["checks"] == ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"]
    drifted = pd.read_csv(published_dir / "contrasts.csv")
    visible = ~drifted["black_population_is_suppressed"].astype(bool)
    drifted.loc[visible.idxmax(), "black_population_estimate"] += 1
    drifted.to_csv(published_dir / "contrasts.csv", index=False)
    with pytest.raises(AssertionError, match="Gold-to-published contrasts"):
        reconcile_longitudinal(source_paths, silver_paths, gold_dir, published_dir)
