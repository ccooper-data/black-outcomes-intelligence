import math

import pandas as pd

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.survey import replicate_standard_error, weighted_ratio


def test_acs_sdr_standard_error_formula():
    estimate = 100.0
    replicates = [101.0] * 80
    assert replicate_standard_error(estimate, replicates) == 2.0


def test_ratio_recomputes_each_replicate_denominator_and_ci():
    frame = pd.DataFrame({"PWGTP": [100, 100], **{c: [120, 80] for c in PERSON_REPLICATE_WEIGHTS}})
    result = weighted_ratio(frame, [True, False])
    assert result["estimate"] == 0.5
    assert math.isclose(result["standard_error"], 0.2)
    assert result["ci95_lower"] >= 0
    assert result["ci95_upper"] <= 1


def test_small_sample_is_suppressed_with_reason():
    frame = pd.DataFrame({"PWGTP": [100, 100], **{c: [100, 100] for c in PERSON_REPLICATE_WEIGHTS}})
    result = weighted_ratio(frame, [True, False])
    assert result["is_suppressed"] is True
    assert "unweighted_n_below_30" in result["suppression_reason"]
