"""Reconcile Phase 7 source, Silver, Gold, and public inference artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.transform.build_inference import build_inference
from src.transform.publish_dashboard import redact_suppressed
from src.transform.reconcile import _assert_frames_equal, reconcile_source_to_silver_files


def reconcile_inference(source: Path, silver: Path, gold_dir: Path,
                        published_dir: Path, year: int = 2024) -> dict[str, object]:
    lineage = reconcile_source_to_silver_files(source, silver)
    expected, manifest = build_inference(pd.read_parquet(silver), year)
    gold = pd.read_csv(gold_dir / "inference.csv")
    _assert_frames_equal(expected, gold, ["metric", "state"], "Silver-to-Gold inference")
    if json.loads((gold_dir / "inference_manifest.json").read_text()) != manifest:
        raise AssertionError("Silver-to-Gold inference manifest mismatch")
    public = pd.read_csv(published_dir / "inference.csv")
    _assert_frames_equal(redact_suppressed(gold), public, ["metric", "state"], "Gold-to-published inference")
    if (gold_dir / "inference_manifest.json").read_bytes() != (published_dir / "inference_manifest.json").read_bytes():
        raise AssertionError("Gold-to-published inference manifest mismatch")
    return {
        "status": "passed", "year": year, "rows": len(gold), "lineage": lineage,
        "checks": ["source-to-Silver", "Silver-to-Gold", "Gold-to-published"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--silver", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--published-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = reconcile_inference(args.source, args.silver, args.gold_dir, args.published_dir, args.year)
    payload = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
