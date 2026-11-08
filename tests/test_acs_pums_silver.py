import pandas as pd
import pytest

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.acs_pums_silver import COLUMNS, transform_frame


def _frame(**overrides):
    row = {c: 1 for c in COLUMNS}
    row["SERIALNO"] = "2024TEST"
    for column in PERSON_REPLICATE_WEIGHTS:
        row[column] = 1
    row.update(overrides)
    return pd.DataFrame([row])


def test_transform_preserves_person_weight():
    out = transform_frame(_frame(PWGTP=42))
    assert int(out.loc[0, "PWGTP"]) == 42
    assert list(out.columns) == COLUMNS


def test_transform_preserves_all_person_replicate_weights():
    out = transform_frame(_frame(PWGTP1=37, PWGTP80=44))
    assert int(out.loc[0, "PWGTP1"]) == 37
    assert int(out.loc[0, "PWGTP80"]) == 44


def test_transform_rejects_nonpositive_weight():
    with pytest.raises(ValueError, match="PWGTP"):
        transform_frame(_frame(PWGTP=0))


def test_transform_rejects_missing_required_column():
    with pytest.raises(ValueError, match="STATE"):
        transform_frame(_frame().drop(columns=["STATE"]))
