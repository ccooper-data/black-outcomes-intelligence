import zipfile
from pathlib import Path

import pandas as pd
import pytest

from src.ingest.acs_pums import REQUIRED_COLUMNS, sha256_file, validate_archive


def _write_zip(path: Path, columns: list[str], rows: list[dict]) -> None:
    csv_path = path.parent / "psam_pusa.csv"
    pd.DataFrame(rows, columns=columns).to_csv(csv_path, index=False)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(csv_path, arcname="psam_pusa.csv")


def test_validate_archive_accepts_required_schema(tmp_path: Path) -> None:
    archive = tmp_path / "pums.zip"
    row = {column: 1 for column in REQUIRED_COLUMNS}
    _write_zip(archive, sorted(REQUIRED_COLUMNS), [row])

    result = validate_archive(archive)

    assert result["total_rows"] == 1
    assert result["required_columns"] == sorted(REQUIRED_COLUMNS)


def test_validate_archive_rejects_missing_weight(tmp_path: Path) -> None:
    archive = tmp_path / "pums.zip"
    columns = sorted(REQUIRED_COLUMNS - {"PWGTP"})
    row = {column: 1 for column in columns}
    _write_zip(archive, columns, [row])

    with pytest.raises(ValueError, match="PWGTP"):
        validate_archive(archive)


def test_sha256_is_stable(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"black-outcomes-intelligence")
    assert sha256_file(artifact) == sha256_file(artifact)
