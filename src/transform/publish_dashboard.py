"""Create disclosure-safe public dashboard artifacts from private Gold outputs."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PUBLIC_REDACT_FIELDS = (
    "estimate", "standard_error", "ci95_lower", "ci95_upper", "relative_standard_error",
)
PUBLIC_INFERENCE_REDACT_FIELDS = ("p_value", "q_value", "fdr_significant")


def redact_suppressed(frame: pd.DataFrame) -> pd.DataFrame:
    """Blank statistical values for suppressed metrics while retaining audit metadata."""
    result = frame.copy()
    flag_columns = [column for column in result.columns if column.endswith("_is_suppressed")]
    for flag_column in flag_columns:
        prefix = flag_column.removesuffix("_is_suppressed")
        suppressed = result[flag_column].fillna(False).astype(bool)
        if not suppressed.any():
            continue
        for field in (*PUBLIC_REDACT_FIELDS, *PUBLIC_INFERENCE_REDACT_FIELDS):
            column = f"{prefix}_{field}"
            if column in result.columns:
                if field == "fdr_significant":
                    result[column] = result[column].astype(object)
                result.loc[suppressed, column] = pd.NA
    return result


def build_candidates(gold_dir: Path, output_dir: Path,
                     names: tuple[str, ...] = ("national.csv", "states.csv", "intersectional.csv"),
                     metadata_name: str = "manifest.json") -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        redact_suppressed(pd.read_csv(gold_dir / name)).to_csv(output_dir / name, index=False)
    (output_dir / metadata_name).write_bytes((gold_dir / metadata_name).read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--longitudinal", action="store_true")
    parser.add_argument("--modeling", action="store_true")
    parser.add_argument("--robustness", action="store_true")
    parser.add_argument("--inference", action="store_true")
    args = parser.parse_args()
    if args.inference:
        names = ("inference.csv",)
        metadata_name = "inference_manifest.json"
    elif args.robustness:
        names = (
            "robustness_metrics.csv", "robustness_comparisons.csv",
            "robustness_calibration.csv", "robustness_features.csv",
        )
        metadata_name = "robustness_card.json"
    elif args.modeling:
        names = ("model_metrics.csv", "model_calibration.csv")
        metadata_name = "model_card.json"
    elif args.longitudinal:
        names = ("trends.csv", "contrasts.csv")
        metadata_name = "manifest.json"
    else:
        names = ("national.csv", "states.csv", "intersectional.csv")
        metadata_name = "manifest.json"
    build_candidates(args.gold_dir, args.output_dir, names, metadata_name)


if __name__ == "__main__":
    main()
