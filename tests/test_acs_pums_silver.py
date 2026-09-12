import pandas as pd
import pytest

from src.transform.acs_pums_silver import COLUMNS, transform_frame


def _frame(**overrides):
    row = {c: 1 for c in COLUMNS}
    row["SERIALNO"] = "2024TEST"
    row.update(overrides)
    return pd.DataFrame([row])


def test_transform_preserves_person_weight():
    out = transform_frame(_frame(PWGTP=42))
    assert int(out.loc[0, "PWGTP"]) == 42
    assert list(out.columns) == COLUMNS


def test_transform_rejects_nonpositive_weight():
    with pytest.raises(ValueError, match="PWGTP"):
        transform_frame(_frame(PWGTP=0))


def test_transform_rejects_missing_required_column():
    with pytest.raises(ValueError, match="STATE"):
        transform_frame(_frame().drop(columns=["STATE"]))
