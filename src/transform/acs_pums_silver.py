"""Transform ACS PUMS Bronze CSV archive into curated Silver Parquet."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd

DEFAULT_BUCKET = "black-outcomes-intelligence-dev-4623dd8370ffd332f292468c61"
COLUMNS = ["SERIALNO", "SPORDER", "STATE", "PUMA", "AGEP", "RAC1P", "MAR", "SCHL", "PINCP", "ESR", "PWGTP"]
INTEGER_COLUMNS = ["SPORDER", "STATE", "PUMA", "AGEP", "RAC1P", "MAR", "SCHL", "PINCP", "ESR", "PWGTP"]


def transform_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(set(COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"Bronze PUMS data missing required columns: {missing}")
    out = frame[COLUMNS].copy()
    out["SERIALNO"] = out["SERIALNO"].astype("string")
    for column in INTEGER_COLUMNS:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    if out["PWGTP"].isna().any() or (out["PWGTP"] <= 0).any():
        raise ValueError("PWGTP must be present and positive for every person record")
    if out["SERIALNO"].isna().any():
        raise ValueError("SERIALNO must be present for every person record")
    return out


def run(year: int, bucket: str) -> dict[str, object]:
    s3 = boto3.client("s3")
    bronze_key = f"bronze/acs_pums/year={year}/release=1-year/csv_pus.zip"
    silver_prefix = f"silver/acs_pums_person/year={year}"
    parquet_key = f"{silver_prefix}/data/part-00000.parquet"
    manifest_key = f"{silver_prefix}/metadata/manifest.json"

    with tempfile.TemporaryDirectory(prefix="acs-pums-silver-") as directory:
        archive = Path(directory) / "csv_pus.zip"
        s3.download_file(bucket, bronze_key, str(archive))
        frames: list[pd.DataFrame] = []
        with zipfile.ZipFile(archive) as bundle:
            names = [n for n in bundle.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise ValueError("Bronze archive contains no CSV files")
            for name in names:
                with bundle.open(name) as stream:
                    frames.append(transform_frame(pd.read_csv(stream, usecols=COLUMNS, low_memory=False)))
        silver = pd.concat(frames, ignore_index=True)
        if silver.empty:
            raise ValueError("Silver dataset contains zero records")

        parquet = Path(directory) / "part-00000.parquet"
        silver.to_parquet(parquet, index=False, engine="pyarrow", compression="snappy")
        s3.upload_file(str(parquet), bucket, parquet_key, ExtraArgs={"ContentType": "application/octet-stream"})

        manifest = {
            "source_key": bronze_key,
            "silver_key": parquet_key,
            "year": year,
            "rows": int(len(silver)),
            "columns": COLUMNS,
            "weighted_population": int(silver["PWGTP"].sum()),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        s3.put_object(Bucket=bucket, Key=manifest_key, Body=json.dumps(manifest, indent=2).encode(), ContentType="application/json")
        return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    args = parser.parse_args()
    print(json.dumps(run(args.year, args.bucket), indent=2))


if __name__ == "__main__":
    main()
