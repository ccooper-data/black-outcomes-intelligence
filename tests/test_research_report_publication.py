import hashlib
import json

import pytest

from src.research_report import load_report_package


def _package(tmp_path):
    artifacts = {
        "research_findings.md": b"# Findings\n",
        "research_findings.html": b"<h1>Findings</h1>\n",
        "research_findings_appendix.csv": b"state,estimate\nNational,1\n",
    }
    for name, payload in artifacts.items():
        (tmp_path / name).write_bytes(payload)
    manifest = {
        "phase": 8,
        "survey_year": 2024,
        "causal_interpretation": False,
        "rows": 208,
        "publishable_rows": 180,
        "suppressed_rows": 28,
        "unstable_contrast_rse_rows": 96,
        "unstable_contrast_rse_fdr_significant_rows": 25,
        "artifacts": {name: hashlib.sha256(payload).hexdigest() for name, payload in artifacts.items()},
    }
    (tmp_path / "research_findings_manifest.json").write_text(json.dumps(manifest))
    return artifacts


def test_public_report_package_hashes_are_verified(tmp_path):
    expected = _package(tmp_path)
    manifest, data = load_report_package(tmp_path)
    assert manifest["rows"] == 208
    assert manifest["unstable_contrast_rse_rows"] == 96
    assert data == expected


def test_public_report_package_rejects_drift(tmp_path):
    _package(tmp_path)
    (tmp_path / "research_findings.html").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_report_package(tmp_path)


def test_missing_report_is_not_an_error(tmp_path):
    assert load_report_package(tmp_path) == ({}, {})
