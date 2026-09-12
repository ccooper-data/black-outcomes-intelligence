"""Ingest official ACS PUMS person CSV archives into the S3 bronze layer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd

DEFAULT_YEAR = 2024
DEFAULT_BUCKET = "black-outcomes-intelligence-dev-4623dd8370ffd332f292468c61"
DEFAULT_URL_TEMPLATE = "https://www2.census.gov/programs-surveys/acs/data/pums/{year}/1-Year/csv_pus.zip"
# The 2024 FTP person file uses STATE (not the API geography alias ST).
REQUIRED_COLUMNS = {"SERIALNO", "SPORDER", "STATE", "PUMA", "AGEP", "RAC1P", "MAR", "SCHL", "PINCP", "ESR", "PWGTP"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "black-outcomes-intelligence/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def validate_archive(archive: Path) -> dict[str, object]:
    if not zipfile.is_zipfile(archive):
        raise ValueError("Downloaded Census artifact is not a valid ZIP archive")

    with zipfile.ZipFile(archive) as bundle:
        csv_names = [name for name in bundle.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError("Census ZIP contains no CSV files")

        total_rows = 0
        observed_columns: set[str] = set()
        file_summaries = []
        for name in csv_names:
            with bundle.open(name) as stream:
                frame = pd.read_csv(stream, nrows=50)
            columns = set(frame.columns)
            missing = sorted(REQUIRED_COLUMNS - columns)
            if missing:
                raise ValueError(f"{name} is missing required PUMS columns: {missing}")
            observed_columns.update(columns)

            with bundle.open(name) as stream:
                row_count = sum(1 for _ in stream) - 1
            if row_count <= 0:
                raise ValueError(f"{name} contains no person records")
            total_rows += row_count
            file_summaries.append({"name": name, "rows": row_count, "columns": len(columns)})

    return {
        "csv_files": file_summaries,
        "total_rows": total_rows,
        "required_columns": sorted(REQUIRED_COLUMNS),
        "observed_column_count": len(observed_columns),
    }


def upload(year: int, bucket: str, archive: Path, validation: dict[str, object], source_url: str) -> dict[str, object]:
    s3 = boto3.client("s3")
    prefix = f"bronze/acs_pums/year={year}/release=1-year"
    archive_key = f"{prefix}/csv_pus.zip"
    manifest_key = f"{prefix}/manifest.json"
    checksum = sha256_file(archive)
    ingested_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "source": "U.S. Census Bureau ACS PUMS",
        "source_url": source_url,
        "year": str(year),
        "release": "1-year",
        "sha256": checksum,
        "ingested_at_utc": ingested_at,
    }
    s3.upload_file(str(archive), bucket, archive_key, ExtraArgs={"Metadata": metadata})

    manifest = {
        **metadata,
        "bucket": bucket,
        "object_key": archive_key,
        "validation": validation,
    }
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    return manifest


def run(year: int, bucket: str, source_url: str | None = None) -> dict[str, object]:
    url = source_url or DEFAULT_URL_TEMPLATE.format(year=year)
    with tempfile.TemporaryDirectory(prefix="acs-pums-") as directory:
        archive = Path(directory) / "csv_pus.zip"
        download(url, archive)
        validation = validate_archive(archive)
        return upload(year, bucket, archive, validation, url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load ACS PUMS person data to S3 bronze")
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--bucket", default=os.getenv("BOI_S3_BUCKET", DEFAULT_BUCKET))
    parser.add_argument("--source-url", default=None)
    args = parser.parse_args()
    manifest = run(args.year, args.bucket, args.source_url)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
