import pandas as pd

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_marts import build_intersectional


def _frame() -> pd.DataFrame:
    rows = []
    for state in (1, 2):
        for sex in (1, 2):
            for i in range(42):
                row = {
                    "SERIALNO": f"{state}-{sex}-{i}", "SPORDER": 1, "STATE": state,
                    "PUMA": 100, "AGEP": 18 + i, "SEX": sex, "RAC1P": 2,
                    "MAR": 1 if i % 2 else 5, "SCHL": 21 if i % 3 else 20,
                    "PINCP": 25000 + i * 1000, "ESR": 1 if i % 4 else 3, "PWGTP": 100,
                }
                row.update({column: 100 + ((i + j) % 3 - 1) for j, column in enumerate(PERSON_REPLICATE_WEIGHTS)})
                rows.append(row)
    return pd.DataFrame(rows)


def test_intersectional_grain_and_statistical_fields():
    result = build_intersectional(_frame())
    assert len(result) == 42  # national + two states, two sexes, seven age groups
    assert set(result["sex"]) == {"Black women", "Black men"}
    assert set(result["age_band"]) == {"All ages", "18–24", "25–34", "35–44", "45–54", "55–64", "65+"}
    required = {
        "employment_rate_estimate", "employment_rate_standard_error",
        "employment_rate_ci95_lower", "employment_rate_ci95_upper",
        "employment_rate_unweighted_n", "employment_rate_weighted_denominator",
        "employment_rate_is_suppressed", "employment_rate_suppression_reason",
    }
    assert required <= set(result.columns)


def test_small_age_cells_are_suppressed_not_zeroed():
    result = build_intersectional(_frame())
    row = result.loc[
        (result["state"] == 1) & (result["sex"] == "Black women") & (result["age_band"] == "18–24")
    ].iloc[0]
    assert bool(row["married_rate_is_suppressed"])
    assert row["married_rate_estimate"] >= 0
    assert "unweighted_n_below_30" in row["married_rate_suppression_reason"]
