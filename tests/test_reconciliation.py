import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.acs_pums_silver import transform_frame
from src.transform.build_marts import build_gold
from src.transform.reconcile import reconcile, reconcile_publication


def source_frame():
    rows = []
    for i in range(60):
        row = {"SERIALNO": f"S{i}", "SPORDER": 1, "STATE": 1 if i < 30 else 2,
               "PUMA": 100, "AGEP": 20 + i % 40, "RAC1P": 2, "MAR": 1 if i % 2 else 5,
               "SCHL": 21 if i % 3 else 20, "PINCP": 30000 + i * 100, "ESR": 1, "PWGTP": 100}
        row.update({c: 100 + ((i + j) % 3 - 1) for j, c in enumerate(PERSON_REPLICATE_WEIGHTS)})
        rows.append(row)
    return pd.DataFrame(rows)


def test_full_reconciliation_passes_and_detects_publication_drift():
    source = source_frame()
    silver = transform_frame(source)
    national, states = build_gold(silver)
    report = reconcile(source, silver, national, states, national.copy(), states.copy())
    assert report["status"] == "passed"
    drifted = states.copy()
    drifted.loc[0, "married_rate_estimate"] += 0.01
    with pytest.raises(AssertionError, match="Gold-to-published"):
        reconcile(source, silver, national, states, national.copy(), drifted)


def test_publication_gate_fails_on_dashboard_drift():
    silver = transform_frame(source_frame())
    national, states = build_gold(silver)
    report = reconcile_publication(national, states, national.copy(), states.copy())
    assert report["checks"] == ["Gold-to-published"]
    drifted = national.copy()
    drifted.loc[0, "black_population_estimate"] += 1
    with pytest.raises(AssertionError, match="Gold-to-published national"):
        reconcile_publication(national, states, drifted, states.copy())
