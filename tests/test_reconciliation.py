import pandas as pd
import pytest
import zipfile

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.acs_pums_silver import transform_frame
from src.transform.build_marts import build_gold, build_intersectional
from src.transform.reconcile import (
    read_source, reconcile, reconcile_publication, reconcile_source_to_silver_files,
)


def source_frame():
    rows = []
    for i in range(60):
        row = {"SERIALNO": f"S{i}", "SPORDER": 1, "STATE": 1 if i < 30 else 2, "SEX": 2 if i % 2 else 1,
               "PUMA": 100, "AGEP": 20 + i % 40, "RAC1P": 2, "MAR": 1 if i % 2 else 5,
               "SCHL": 21 if i % 3 else 20, "PINCP": 30000 + i * 100, "ESR": 1, "PWGTP": 100}
        row.update({c: 100 + ((i + j) % 3 - 1) for j, c in enumerate(PERSON_REPLICATE_WEIGHTS)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_full_reconciliation_passes_and_detects_publication_drift():
    source = source_frame()
    silver = transform_frame(source)
    national, states = build_gold(silver)
    intersectional = build_intersectional(silver)
    report = reconcile(
        source, silver, national, states, national.copy(), states.copy(),
        gold_intersectional=intersectional,
        published_intersectional=intersectional.copy(),
    )
    assert report["status"] == "passed"
    drifted = states.copy()
    drifted.loc[0, "married_rate_estimate"] += 0.01
    with pytest.raises(AssertionError, match="Gold-to-published"):
        reconcile(
            source, silver, national, states, national.copy(), drifted,
            gold_intersectional=intersectional,
            published_intersectional=intersectional.copy(),
        )


def test_full_reconciliation_detects_intersectional_drift():
    source = source_frame()
    silver = transform_frame(source)
    national, states = build_gold(silver)
    intersectional = build_intersectional(silver)
    drifted = intersectional.copy()
    drifted.loc[0, "employment_rate_estimate"] += 0.01
    with pytest.raises(AssertionError, match="Gold-to-published intersectional"):
        reconcile(
            source, silver, national, states, national.copy(), states.copy(),
            gold_intersectional=intersectional,
            published_intersectional=drifted,
        )


def test_publication_gate_fails_on_dashboard_drift():
    silver = transform_frame(source_frame())
    national, states = build_gold(silver)
    report = reconcile_publication(national, states, national.copy(), states.copy())
    assert report["checks"] == ["Gold-to-published"]
    drifted = national.copy()
    drifted.loc[0, "black_population_estimate"] += 1
    with pytest.raises(AssertionError, match="Gold-to-published national"):
        reconcile_publication(national, states, drifted, states.copy())


def test_authoritative_bronze_zip_is_read_for_reconciliation(tmp_path):
    source = source_frame()
    csv_path = tmp_path / "persons.csv"
    archive = tmp_path / "source.zip"
    source.to_csv(csv_path, index=False)
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(csv_path, arcname="psam_pusa.csv")
    observed = read_source(archive)
    assert len(observed) == len(source)
    assert set(observed.columns) == set(source.columns)


def test_streaming_source_to_silver_fingerprint_detects_drift(tmp_path):
    source = source_frame()
    silver = transform_frame(source)
    csv_path = tmp_path / "persons.csv"
    archive = tmp_path / "source.zip"
    parquet = tmp_path / "silver.parquet"
    source.to_csv(csv_path, index=False)
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(csv_path, arcname="psam_pusa.csv")
    silver.to_parquet(parquet, index=False)
    result = reconcile_source_to_silver_files(archive, parquet)
    assert result["source_rows"] == 60
    drifted = silver.copy()
    drifted.loc[0, "PWGTP1"] += 1
    drifted.to_parquet(parquet, index=False)
    with pytest.raises(AssertionError, match="fingerprint mismatch"):
        reconcile_source_to_silver_files(archive, parquet)
