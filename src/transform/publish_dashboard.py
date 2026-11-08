"""Create disclosure-safe public dashboard artifacts from private Gold outputs."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PUBLIC_REDACT_FIELDS = (
    "estimate", "standard_error", "ci95_lower", "ci95_upper", "relative_standard_error",
)


def redact_suppressed(frame: pd.DataFrame) -> pd.DataFrame:
    """Blank statistical values for suppressed metrics while retaining audit metadata."""
    result = frame.copy()
    flag_columns = [column for column in result.columns if column.endswith("_is_suppressed")]
    for flag_column in flag_columns:
        prefix = flag_column.removesuffix("_is_suppressed")
        suppressed = result[flag_column].fillna(False).astype(bool)
        for field in PUBLIC_REDACT_FIELDS:
            column = f"{prefix}_{field}"
            if column in result.columns:
                result.loc[suppressed, column] = pd.NA
    return result


def build_candidates(gold_dir: Path, output_dir: Path,
                     names: tuple[str, ...] = ("national.csv", "states.csv", "intersectional.csv")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        redact_suppressed(pd.read_csv(gold_dir / name)).to_csv(output_dir / name, index=False)
    (output_dir / "manifest.json").write_bytes((gold_dir / "manifest.json").read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--longitudinal", action="store_true")
    args = parser.parse_args()
    names = ("trends.csv", "contrasts.csv") if args.longitudinal else (
        "national.csv", "states.csv", "intersectional.csv"
    )
    build_candidates(args.gold_dir, args.output_dir, names)


if __name__ == "__main__":
    main()
