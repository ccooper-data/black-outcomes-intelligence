"""Reconcile Phase 4 inputs, aggregate model outputs, and public artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.transform.build_longitudinal import YEARS
from src.transform.build_models import build_model_outputs
from src.transform.publish_dashboard import redact_suppressed
from src.transform.reconcile import _assert_frames_equal, reconcile_source_to_silver_files


def reconcile_models(source_paths: dict[int, Path], silver_paths: dict[int, Path],
                     gold_dir: Path, published_dir: Path) -> dict[str, object]:
    if tuple(sorted(source_paths)) != YEARS or tuple(sorted(silver_paths)) != YEARS:
        raise ValueError(f"Source and Silver inputs must contain exactly {YEARS}")
    lineage = {
        str(year): reconcile_source_to_silver_files(source_paths[year], silver_paths[year])
        for year in YEARS
    }
    frames = {year: pd.read_parquet(silver_paths[year]) for year in YEARS}
    expected_metrics, expected_calibration, expected_card = build_model_outputs(frames)
    gold_metrics = pd.read_csv(gold_dir / "model_metrics.csv")
    gold_calibration = pd.read_csv(gold_dir / "model_calibration.csv")
    metric_keys = ["model", "evaluation_year", "group_type", "group", "metric"]
    calibration_keys = ["model", "evaluation_year", "calibration_bin"]
    _assert_frames_equal(expected_metrics, gold_metrics, metric_keys, "Silver-to-Gold model metrics")
    _assert_frames_equal(expected_calibration, gold_calibration, calibration_keys, "Silver-to-Gold calibration")
    if json.loads((gold_dir / "model_card.json").read_text()) != expected_card:
        raise AssertionError("Silver-to-Gold model card mismatch")
    published_metrics = pd.read_csv(published_dir / "model_metrics.csv")
    published_calibration = pd.read_csv(published_dir / "model_calibration.csv")
    _assert_frames_equal(redact_suppressed(gold_metrics), published_metrics, metric_keys, "Gold-to-published model metrics")
    _assert_frames_equal(redact_suppressed(gold_calibration), published_calibration, calibration_keys, "Gold-to-published calibration")
    if (gold_dir / "model_card.json").read_bytes() != (published_dir / "model_card.json").read_bytes():
        raise AssertionError("Gold-to-published model card mismatch")
    return {
        "status": "passed", "years": list(YEARS), "lineage": lineage,
        "metric_rows": len(gold_metrics), "calibration_rows": len(gold_calibration),
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
    report = reconcile_models(_parse(args.source), _parse(args.silver), args.gold_dir, args.published_dir)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
