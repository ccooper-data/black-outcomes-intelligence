import pandas as pd

from src.transform.publish_dashboard import PUBLIC_REDACT_FIELDS, redact_suppressed


def test_suppressed_statistics_are_redacted_before_publication():
    frame = pd.DataFrame({
        "metric_estimate": [0.4, 0.5],
        "metric_standard_error": [0.1, 0.01],
        "metric_ci95_lower": [0.2, 0.48],
        "metric_ci95_upper": [0.6, 0.52],
        "metric_relative_standard_error": [0.25, 0.02],
        "metric_unweighted_n": [12, 120],
        "metric_weighted_denominator": [1000, 10000],
        "metric_is_suppressed": [True, False],
        "metric_suppression_reason": ["unweighted_n_below_30", ""],
    })
    public = redact_suppressed(frame)
    for field in PUBLIC_REDACT_FIELDS:
        assert pd.isna(public.loc[0, f"metric_{field}"])
        assert public.loc[1, f"metric_{field}"] == frame.loc[1, f"metric_{field}"]
    assert public.loc[0, "metric_unweighted_n"] == 12
    assert public.loc[0, "metric_weighted_denominator"] == 1000
    assert public.loc[0, "metric_suppression_reason"] == "unweighted_n_below_30"


def test_redaction_handles_multiple_metrics_independently():
    frame = pd.DataFrame({
        "a_estimate": [1.0], "a_is_suppressed": [True],
        "b_estimate": [2.0], "b_is_suppressed": [False],
    })
    public = redact_suppressed(frame)
    assert pd.isna(public.loc[0, "a_estimate"])
    assert public.loc[0, "b_estimate"] == 2.0


def test_suppressed_inference_blanks_tests_and_decisions():
    frame = pd.DataFrame({
        "difference_estimate": [0.1], "difference_p_value": [0.01],
        "difference_q_value": [0.02], "difference_fdr_significant": [True],
        "difference_is_suppressed": [True],
    })
    public = redact_suppressed(frame)
    assert pd.isna(public.loc[0, "difference_estimate"])
    assert pd.isna(public.loc[0, "difference_p_value"])
    assert pd.isna(public.loc[0, "difference_q_value"])
    assert pd.isna(public.loc[0, "difference_fdr_significant"])
