"""Fail-closed reconciliation across ACS source, Silver, Gold, and publication."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from src.transform.acs_pums_silver import COLUMNS, transform_frame
from src.transform.build_marts import build_gold


def read_source(path: Path) -> pd.DataFrame:
    """Read a test Parquet source or the authoritative Census Bronze ZIP."""
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    if path.suffix.lower() != ".zip" or not zipfile.is_zipfile(path):
        raise ValueError("Source must be Parquet or a valid Census PUMS ZIP")
    frames: list[pd.DataFrame] = []
    with zipfile.ZipFile(path) as bundle:
        names = sorted(name for name in bundle.namelist() if name.lower().endswith(".csv"))
        if not names:
            raise ValueError("Census PUMS ZIP contains no CSV files")
        for name in names:
            with bundle.open(name) as stream:
                frames.append(pd.read_csv(stream, usecols=COLUMNS, low_memory=False))
    return pd.concat(frames, ignore_index=True)


def _assert_frames_equal(expected: pd.DataFrame, actual: pd.DataFrame, keys: list[str], label: str) -> None:
    left = expected.sort_values(keys).reset_index(drop=True)
    right = actual.sort_values(keys).reset_index(drop=True)
    if list(left.columns) != list(right.columns) or left.shape != right.shape:
        raise AssertionError(f"{label} schema/shape mismatch: {left.shape} != {right.shape}")
    for column in left.columns:
        if pd.api.types.is_numeric_dtype(left[column]):
            if not np.allclose(left[column], right[column], rtol=1e-12, atol=1e-12, equal_nan=True):
                raise AssertionError(f"{label} numeric mismatch in {column}")
        elif not left[column].fillna("").equals(right[column].fillna("")):
            raise AssertionError(f"{label} value mismatch in {column}")


def reconcile(source: pd.DataFrame, silver: pd.DataFrame, gold_national: pd.DataFrame,
              gold_states: pd.DataFrame, published_national: pd.DataFrame,
              published_states: pd.DataFrame, year: int = 2024) -> dict[str, object]:
    canonical_silver = transform_frame(source)
    _assert_frames_equal(canonical_silver[COLUMNS], silver[COLUMNS], ["SERIALNO", "SPORDER"], "source-to-Silver")
    expected_national, expected_states = build_gold(silver, year)
    _assert_frames_equal(expected_national, gold_national, ["survey_year"], "Silver-to-Gold national")
    _assert_frames_equal(expected_states, gold_states, ["state"], "Silver-to-Gold states")
    _assert_frames_equal(gold_national, published_national, ["survey_year"], "Gold-to-published national")
    _assert_frames_equal(gold_states, published_states, ["state"], "Gold-to-published states")
    return {
        "status": "passed", "year": year, "source_rows": len(source), "silver_rows": len(silver),
        "national_rows": len(gold_national), "state_rows": len(gold_states),
        "checks": ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"],
    }


def reconcile_publication(gold_national: pd.DataFrame, gold_states: pd.DataFrame,
                          published_national: pd.DataFrame,
                          published_states: pd.DataFrame, year: int = 2024) -> dict[str, object]:
    """Gate publication by comparing the dashboard artifacts with approved Gold."""
    _assert_frames_equal(gold_national, published_national, ["survey_year"], "Gold-to-published national")
    _assert_frames_equal(gold_states, published_states, ["state"], "Gold-to-published states")
    return {
        "status": "passed", "year": year, "national_rows": len(gold_national),
        "state_rows": len(gold_states), "checks": ["Gold-to-published"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--silver", type=Path)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--published-dir", type=Path, required=True)
    parser.add_argument("--publication-only", action="store_true")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    gold_national = pd.read_csv(args.gold_dir / "national.csv")
    gold_states = pd.read_csv(args.gold_dir / "states.csv")
    published_national = pd.read_csv(args.published_dir / "national.csv")
    published_states = pd.read_csv(args.published_dir / "states.csv")
    if args.publication_only:
        report = reconcile_publication(
            gold_national, gold_states, published_national, published_states, args.year,
        )
    else:
        if args.source is None or args.silver is None:
            parser.error("--source and --silver are required unless --publication-only is set")
        report = reconcile(
            read_source(args.source), pd.read_parquet(args.silver),
            gold_national, gold_states, published_national, published_states, args.year,
        )
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
