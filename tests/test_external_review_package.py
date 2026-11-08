import hashlib
import json
from pathlib import Path

import numpy as np

from src.transform.build_external_review_package import (
    build_package, independent_bh_log10, independent_sdr_standard_error,
)

ROOT = Path(__file__).parents[1]


def test_independent_sdr_reference_case():
    replicates = np.array([101.0] * 80)
    assert independent_sdr_standard_error(100.0, replicates) == 2.0


def test_independent_bh_is_monotone_and_expected():
    p = np.log10(np.array([0.01, 0.04, 0.03, 0.002]))
    q = np.power(10.0, independent_bh_log10(p))
    assert np.allclose(q, [0.02, 0.04, 0.04, 0.008])


def test_build_review_package_is_deterministic_and_pending(tmp_path):
    args = (
        ROOT / "data/published/inference.csv",
        ROOT / "data/published/inference_manifest.json",
        ROOT / "data/published/research_report/2024/research_findings_manifest.json",
    )
    first, second = tmp_path / "first", tmp_path / "second"
    manifest = build_package(*args, first)
    build_package(*args, second)
    assert manifest["status"] == "external_review_pending"
    assert manifest["independent_validation_claimed"] is False
    assert {p.name: p.read_bytes() for p in first.iterdir()} == {p.name: p.read_bytes() for p in second.iterdir()}
    results = json.loads((first / "validation_results.json").read_text())
    assert results["summary"] == {"failed": 0, "passed": 7, "total": 7}
    assert all(item["passed"] for item in results["checks"])
    package = json.loads((first / "package_manifest.json").read_text())
    for name, expected in package["artifacts"].items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == expected


def test_reviewer_template_cannot_claim_approval(tmp_path):
    build_package(
        ROOT / "data/published/inference.csv",
        ROOT / "data/published/inference_manifest.json",
        ROOT / "data/published/research_report/2024/research_findings_manifest.json",
        tmp_path,
    )
    template = json.loads((tmp_path / "reviewer_findings.json").read_text())
    assert template["review_status"] == "not_started"
    assert template["independent_validation_approved"] is False
