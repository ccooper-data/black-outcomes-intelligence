"""Reconcile every Phase 3 year from Census source through public extracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.transform.build_longitudinal import YEARS, build_longitudinal
from src.transform.publish_dashboard import redact_suppressed
from src.transform.reconcile import _assert_frames_equal, reconcile_source_to_silver_files


def reconcile_longitudinal(source_paths: dict[int, Path], silver_paths: dict[int, Path],
                           gold_dir: Path, published_dir: Path) -> dict[str, object]:
    if tuple(sorted(source_paths)) != YEARS or tuple(sorted(silver_paths)) != YEARS:
        raise ValueError(f"Source and Silver inputs must contain exactly {YEARS}")
    lineage = {
        str(year): reconcile_source_to_silver_files(source_paths[year], silver_paths[year])
        for year in YEARS
    }
    frames = {year: pd.read_parquet(silver_paths[year]) for year in YEARS}
    expected_trends, expected_contrasts, expected_manifest = build_longitudinal(frames)
    gold_trends = pd.read_csv(gold_dir / "trends.csv")
    gold_contrasts = pd.read_csv(gold_dir / "contrasts.csv")
    _assert_frames_equal(expected_trends, gold_trends, ["survey_year", "state", "sex", "age_band"], "Silver-to-Gold trends")
    _assert_frames_equal(expected_contrasts, gold_contrasts, ["survey_year", "state", "age_band"], "Silver-to-Gold contrasts")
    with (gold_dir / "manifest.json").open() as handle:
        if json.load(handle) != expected_manifest:
            raise AssertionError("Silver-to-Gold longitudinal manifest mismatch")
    published_trends = pd.read_csv(published_dir / "trends.csv")
    published_contrasts = pd.read_csv(published_dir / "contrasts.csv")
    _assert_frames_equal(redact_suppressed(gold_trends), published_trends, ["survey_year", "state", "sex", "age_band"], "Gold-to-published trends")
    _assert_frames_equal(redact_suppressed(gold_contrasts), published_contrasts, ["survey_year", "state", "age_band"], "Gold-to-published contrasts")
    if (gold_dir / "manifest.json").read_bytes() != (published_dir / "manifest.json").read_bytes():
        raise AssertionError("Gold-to-published longitudinal manifest mismatch")
    return {
        "status": "passed", "years": list(YEARS), "lineage": lineage,
        "trend_rows": len(gold_trends), "contrast_rows": len(gold_contrasts),
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
    report = reconcile_longitudinal(_parse(args.source), _parse(args.silver), args.gold_dir, args.published_dir)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
