"""Reconcile Phase 5 source, Silver, challenger Gold, and public artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.transform.build_longitudinal import YEARS
from src.transform.build_robustness import build_robustness_outputs
from src.transform.publish_dashboard import redact_suppressed
from src.transform.reconcile import _assert_frames_equal, reconcile_source_to_silver_files

FILES = (
    ("robustness_metrics.csv", ["model", "evaluation_year", "group_type", "group", "metric"]),
    ("robustness_comparisons.csv", ["reference_model", "challenger_model", "evaluation_year", "group_type", "group", "metric"]),
    ("robustness_calibration.csv", ["model", "evaluation_year", "calibration_bin"]),
    ("robustness_features.csv", ["rank"]),
)


def reconcile_robustness(source_paths: dict[int, Path], silver_paths: dict[int, Path],
                         gold_dir: Path, published_dir: Path) -> dict[str, object]:
    if tuple(sorted(source_paths)) != YEARS or tuple(sorted(silver_paths)) != YEARS:
        raise ValueError(f"Source and Silver inputs must contain exactly {YEARS}")
    lineage = {str(year): reconcile_source_to_silver_files(source_paths[year], silver_paths[year]) for year in YEARS}
    frames = {year: pd.read_parquet(silver_paths[year]) for year in YEARS}
    expected = build_robustness_outputs(frames)
    row_counts: dict[str, int] = {}
    for (name, keys), expected_frame in zip(FILES, expected[:4]):
        gold = pd.read_csv(gold_dir / name)
        public = pd.read_csv(published_dir / name)
        label = name.removesuffix(".csv")
        _assert_frames_equal(expected_frame, gold, keys, f"Silver-to-Gold {label}")
        _assert_frames_equal(redact_suppressed(gold), public, keys, f"Gold-to-published {label}")
        row_counts[label] = len(gold)
    if json.loads((gold_dir / "robustness_card.json").read_text()) != expected[4]:
        raise AssertionError("Silver-to-Gold robustness card mismatch")
    if (gold_dir / "robustness_card.json").read_bytes() != (published_dir / "robustness_card.json").read_bytes():
        raise AssertionError("Gold-to-published robustness card mismatch")
    return {
        "status": "passed", "years": list(YEARS), "lineage": lineage, **row_counts,
        "checks": ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"],
    }


def _parse(values: list[str]) -> dict[int, Path]:
    parsed: dict[int, Path] = {}
    for value in values:
        year, separator, path = value.partition("=")
        if not separator:
            raise ValueError("Inputs must use YEAR=PATH")
        parsed[int(year)] = Path(path)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", required=True, metavar="YEAR=PATH")
    parser.add_argument("--silver", action="append", required=True, metavar="YEAR=PATH")
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--published-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = reconcile_robustness(_parse(args.source), _parse(args.silver), args.gold_dir, args.published_dir)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
