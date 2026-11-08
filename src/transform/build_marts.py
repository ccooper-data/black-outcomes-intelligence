"""Build research-grade ACS PUMS Gold estimates from curated Silver records."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.transform.survey import flatten_metric, weighted_mean, weighted_ratio, weighted_total

BASE_REQUIRED = {"STATE", "AGEP", "SEX", "RAC1P", "MAR", "SCHL", "PINCP", "ESR", "PWGTP"}
AGE_BANDS = (
    ("18–24", 18, 24), ("25–34", 25, 34), ("35–44", 35, 44),
    ("45–54", 45, 54), ("55–64", 55, 64), ("65+", 65, None),
)
SEX_LABELS = {1: "Black men", 2: "Black women"}


def validate(frame: pd.DataFrame) -> None:
    missing = sorted(BASE_REQUIRED - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    if frame.empty or (frame["PWGTP"] <= 0).any():
        raise ValueError("Gold input must contain records with positive PWGTP")


def _row(frame: pd.DataFrame, state: int | None, year: int) -> dict[str, object]:
    eligible = frame.loc[(frame["RAC1P"] == 2) & (frame["AGEP"] >= 18)].copy()
    result: dict[str, object] = {"state": state, "survey_year": year}
    result.update(flatten_metric("black_population", weighted_total(eligible)))
    result.update(flatten_metric("married_rate", weighted_ratio(eligible, eligible["MAR"] == 1)))
    result.update(flatten_metric("bachelors_plus_rate", weighted_ratio(eligible, eligible["SCHL"] >= 21)))
    employed = eligible["ESR"].isin([1, 2, 4, 5])
    employment_denominator = eligible["ESR"].isin([1, 2, 3, 4, 5, 6])
    result.update(flatten_metric(
        "employment_rate", weighted_ratio(eligible, employed, employment_denominator)
    ))
    result.update(flatten_metric("mean_personal_income", weighted_mean(eligible, eligible["PINCP"])))
    return result


def build_gold(frame: pd.DataFrame, year: int = 2024) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate(frame)
    national = pd.DataFrame([_row(frame, None, year)]).drop(columns="state")
    states = pd.DataFrame([_row(group, int(state), year) for state, group in frame.groupby("STATE", sort=True)])
    return national, states


def build_intersectional(frame: pd.DataFrame, year: int = 2024) -> pd.DataFrame:
    """Black adult outcomes by geography, sex, and age band."""
    validate(frame)
    black_adults = frame.loc[(frame["RAC1P"] == 2) & (frame["AGEP"] >= 18)]
    rows: list[dict[str, object]] = []
    geographies = [(None, black_adults), *[(int(state), group) for state, group in black_adults.groupby("STATE", sort=True)]]
    for state, geography in geographies:
        for sex_code, sex_label in SEX_LABELS.items():
            sex_frame = geography.loc[geography["SEX"] == sex_code]
            groups = [("All ages", sex_frame)]
            groups.extend(
                (label, sex_frame.loc[(sex_frame["AGEP"] >= low) & ((sex_frame["AGEP"] <= high) if high else True)])
                for label, low, high in AGE_BANDS
            )
            for age_band, group in groups:
                row = _row(group, state, year)
                row.update({"sex": sex_label, "age_band": age_band})
                rows.append(row)
    columns = ["state", "survey_year", "sex", "age_band"]
    result = pd.DataFrame(rows)
    return result[columns + [column for column in result.columns if column not in columns]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ACS PUMS Gold estimates locally")
    parser.add_argument("--silver", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args()
    source = pd.read_parquet(args.silver)
    national, states = build_gold(source, args.year)
    intersectional = build_intersectional(source, args.year)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    national.to_csv(args.output_dir / "national.csv", index=False)
    states.to_csv(args.output_dir / "states.csv", index=False)
    intersectional.to_csv(args.output_dir / "intersectional.csv", index=False)
    manifest = {
        "year": args.year, "source_rows": len(source), "national_rows": len(national),
        "state_rows": len(states), "intersectional_rows": len(intersectional),
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
