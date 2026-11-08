"""ACS PUMS estimates using the Census person replicate-weight design."""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS

ACS_REPLICATE_FACTOR = 4.0 / 80.0
Z_95 = 1.959963984540054


@dataclass(frozen=True)
class SuppressionPolicy:
    min_unweighted_n: int = 30
    max_relative_standard_error: float = 0.30


def replicate_standard_error(estimate: float, replicate_estimates: np.ndarray) -> float:
    """ACS SDR standard error: sqrt((4/80) * sum((theta_r-theta)^2))."""
    values = np.asarray(replicate_estimates, dtype=float)
    if values.shape != (80,) or not np.isfinite(values).all() or not np.isfinite(estimate):
        return float("nan")
    return float(sqrt(ACS_REPLICATE_FACTOR * np.square(values - estimate).sum()))


def _weights(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    required = {"PWGTP", *PERSON_REPLICATE_WEIGHTS}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing ACS person weight columns: {missing}")
    main = frame["PWGTP"].to_numpy(dtype=float)
    reps = frame[list(PERSON_REPLICATE_WEIGHTS)].to_numpy(dtype=float)
    if (main <= 0).any() or not np.isfinite(main).all() or not np.isfinite(reps).all():
        raise ValueError("ACS person weights must be finite and PWGTP must be positive")
    return main, reps


def _result(estimate: float, replicate_estimates: np.ndarray, n: int, denominator: float,
            policy: SuppressionPolicy, bounds: tuple[float, float] | None = None) -> dict[str, object]:
    se = replicate_standard_error(estimate, replicate_estimates)
    low, high = estimate - Z_95 * se, estimate + Z_95 * se
    if bounds:
        low, high = max(bounds[0], low), min(bounds[1], high)
    rse = se / abs(estimate) if estimate != 0 else (0.0 if se == 0 else float("inf"))
    reasons = []
    if n < policy.min_unweighted_n:
        reasons.append("unweighted_n_below_30")
    if denominator <= 0:
        reasons.append("nonpositive_weighted_denominator")
    if not np.isfinite(se) or not np.isfinite(rse) or rse > policy.max_relative_standard_error:
        reasons.append("relative_standard_error_above_30_percent")
    return {
        "estimate": float(estimate), "standard_error": se, "ci95_lower": float(low),
        "ci95_upper": float(high), "relative_standard_error": float(rse),
        "unweighted_n": int(n), "weighted_denominator": float(denominator),
        "is_suppressed": bool(reasons), "suppression_reason": ";".join(reasons),
    }


def weighted_total(frame: pd.DataFrame, selector=None,
                   policy: SuppressionPolicy = SuppressionPolicy()) -> dict[str, object]:
    main, reps = _weights(frame)
    selected = np.ones(len(frame), dtype=float) if selector is None else np.asarray(selector, dtype=bool).astype(float)
    return _result(float(selected @ main), selected @ reps, int(selected.sum()), float(main.sum()), policy, (0, float("inf")))


def weighted_ratio(frame: pd.DataFrame, numerator, denominator=None,
                   policy: SuppressionPolicy = SuppressionPolicy()) -> dict[str, object]:
    main, reps = _weights(frame)
    num = np.asarray(numerator, dtype=bool).astype(float)
    den = np.ones(len(frame), dtype=float) if denominator is None else np.asarray(denominator, dtype=bool).astype(float)
    if np.any(num > den):
        raise ValueError("Ratio numerator must be a subset of its denominator")
    main_den = float(den @ main)
    if main_den <= 0:
        return _result(float("nan"), np.full(80, np.nan), int(den.sum()), main_den, policy, (0, 1))
    rep_den = den @ reps
    rep_estimates = np.divide(num @ reps, rep_den, out=np.full(80, np.nan), where=rep_den != 0)
    return _result(float((num @ main) / main_den), rep_estimates, int(den.sum()), main_den, policy, (0, 1))


def weighted_mean(frame: pd.DataFrame, values: pd.Series, eligible=None,
                  policy: SuppressionPolicy = SuppressionPolicy()) -> dict[str, object]:
    main, reps = _weights(frame)
    x = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(x)
    if eligible is not None:
        valid &= np.asarray(eligible, dtype=bool)
    den = valid.astype(float)
    clean = np.where(valid, x, 0.0)
    main_den = float(den @ main)
    if main_den <= 0:
        return _result(float("nan"), np.full(80, np.nan), int(valid.sum()), main_den, policy)
    rep_den = den @ reps
    rep_estimates = np.divide(clean @ reps, rep_den, out=np.full(80, np.nan), where=rep_den != 0)
    return _result(float((clean @ main) / main_den), rep_estimates, int(valid.sum()), main_den, policy)


def flatten_metric(name: str, result: dict[str, object]) -> dict[str, object]:
    return {f"{name}_{key}": value for key, value in result.items()}
