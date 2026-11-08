"""Build multi-year ACS PUMS trends and direct sex contrasts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.acs_pums import PERSON_REPLICATE_WEIGHTS
from src.transform.build_marts import AGE_BANDS, BASE_REQUIRED, build_intersectional, validate
from src.transform.survey import (
    ReplicateEstimate,
    SuppressionPolicy,
    estimate_mean,
    estimate_ratio,
    estimate_total,
    flatten_metric,
    result_from_replicates,
)

YEARS = (2022, 2023, 2024)
CONTRAST_METRICS = (
    "black_population", "married_rate", "bachelors_plus_rate",
    "employment_rate", "mean_personal_income",
)


def validate_years(frames: dict[int, pd.DataFrame]) -> dict[str, object]:
    """Fail on missing years, missing design fields, or incompatible dtypes."""
    if tuple(sorted(frames)) != YEARS:
        raise ValueError(f"Expected ACS years {YEARS}; received {tuple(sorted(frames))}")
    required = BASE_REQUIRED | set(PERSON_REPLICATE_WEIGHTS)
    schemas: dict[int, dict[str, str]] = {}
    for year, frame in sorted(frames.items()):
        validate(frame)
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{year} is missing required ACS columns: {missing}")
        schemas[year] = {name: str(frame[name].dtype) for name in sorted(required)}
    baseline = schemas[YEARS[0]]
    incompatible = {
        year: {name: (baseline[name], schema[name]) for name in baseline if schema[name] != baseline[name]}
        for year, schema in schemas.items() if schema != baseline
    }
    if incompatible:
        raise ValueError(f"Incompatible Silver schema drift: {incompatible}")
    return {"years": list(YEARS), "required_columns": len(required), "schema_status": "compatible"}


def _estimands(frame: pd.DataFrame) -> dict[str, ReplicateEstimate]:
    employed = frame["ESR"].isin([1, 2, 4, 5])
    labor_force = frame["ESR"].isin([1, 2, 3, 4, 5, 6])
    return {
        "black_population": estimate_total(frame),
        "married_rate": estimate_ratio(frame, frame["MAR"] == 1),
        "bachelors_plus_rate": estimate_ratio(frame, frame["SCHL"] >= 21),
        "employment_rate": estimate_ratio(frame, employed, labor_force),
        "mean_personal_income": estimate_mean(frame, frame["PINCP"]),
    }


def _contrast(women: ReplicateEstimate, men: ReplicateEstimate, metric: str) -> dict[str, object]:
    value = ReplicateEstimate(
        women.estimate - men.estimate,
        women.replicates - men.replicates,
        min(women.unweighted_n, men.unweighted_n),
        min(women.weighted_denominator, men.weighted_denominator),
    )
    bounds = (-1.0, 1.0) if metric.endswith("_rate") else None
    result = result_from_replicates(value, SuppressionPolicy(), bounds)
    result["women_unweighted_n"] = women.unweighted_n
    result["men_unweighted_n"] = men.unweighted_n
    result["women_weighted_denominator"] = women.weighted_denominator
    result["men_weighted_denominator"] = men.weighted_denominator
    return result


def build_contrasts(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    """Women-minus-men estimates using the paired 80 replicate estimates."""
    validate(frame)
    adults = frame.loc[(frame["RAC1P"] == 2) & (frame["AGEP"] >= 18)]
    geographies = [(None, adults), *[(int(s), g) for s, g in adults.groupby("STATE", sort=True)]]
    rows: list[dict[str, object]] = []
    for state, geography in geographies:
        groups = [("All ages", geography)]
        groups.extend(
            (label, geography.loc[(geography["AGEP"] >= low) & ((geography["AGEP"] <= high) if high else True)])
            for label, low, high in AGE_BANDS
        )
        for age_band, group in groups:
            women = _estimands(group.loc[group["SEX"] == 2])
            men = _estimands(group.loc[group["SEX"] == 1])
            row: dict[str, object] = {"state": state, "survey_year": year, "age_band": age_band}
            for metric in CONTRAST_METRICS:
                row.update(flatten_metric(metric, _contrast(women[metric], men[metric], metric)))
            rows.append(row)
    return pd.DataFrame(rows)


def build_longitudinal(frames: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    schema = validate_years(frames)
    trends = pd.concat(
        [build_intersectional(frames[year], year) for year in YEARS], ignore_index=True
    )
    contrasts = pd.concat(
        [build_contrasts(frames[year], year) for year in YEARS], ignore_index=True
    )
    manifest = {
        **schema,
        "source_rows_by_year": {str(year): len(frames[year]) for year in YEARS},
        "trend_rows": len(trends),
        "contrast_rows": len(contrasts),
        "contrast_definition": "Black women minus Black men within year, geography, and age band",
        "cross_year_significance_tested": False,
    }
    return trends, contrasts, manifest


def _parse_silver(values: list[str]) -> dict[int, Path]:
    result: dict[int, Path] = {}
    for value in values:
        year_text, separator, path = value.partition("=")
        if not separator:
            raise ValueError("--silver values must use YEAR=PATH")
        result[int(year_text)] = Path(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 2022-2024 ACS PUMS longitudinal Gold")
    parser.add_argument("--silver", action="append", required=True, metavar="YEAR=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = _parse_silver(args.silver)
    frames = {year: pd.read_parquet(path) for year, path in paths.items()}
    trends, contrasts, manifest = build_longitudinal(frames)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trends.to_csv(args.output_dir / "trends.csv", index=False)
    contrasts.to_csv(args.output_dir / "contrasts.csv", index=False)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
