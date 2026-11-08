import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.transform.build_research_report import (
    _csv_value,
    build_report,
    validate_inference,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_report_is_deterministic_and_complete(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    args = (
        ROOT / "data/published/inference.csv",
        ROOT / "data/published/inference_manifest.json",
    )
    manifest = build_report(*args, first)
    build_report(*args, second)

    assert manifest["rows"] == 208
    assert manifest["publishable_rows"] == 180
    assert manifest["suppressed_rows"] == 28
    assert manifest["causal_interpretation"] is False
    for name in [
        "research_findings.md",
        "research_findings.html",
        "research_findings_appendix.csv",
        "research_findings_manifest.json",
    ]:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    markdown = (first / "research_findings.md").read_text()
    assert "28.1%" in markdown
    assert "37.0%" in markdown
    assert "-8.9%" in markdown
    assert "not causal" in markdown.lower()
    assert "Largest five absolute publishable differences" in markdown
    assert "the other component remains visible only when it independently passes" in markdown

    report_html = (first / "research_findings.html").read_text()
    assert "<strong>Release:</strong>" in report_html
    assert "<code>inference.csv</code>" in report_html
    assert "**Release:**" not in report_html
    assert "`inference.csv`" not in report_html

    appendix = pd.read_csv(first / "research_findings_appendix.csv")
    assert len(appendix) == 208
    assert appendix["state_name"].nunique() == 52
    suppressed = appendix[appendix["difference_is_suppressed"]]
    assert suppressed["difference_estimate"].isna().all()


def test_report_manifest_hashes_match_artifacts(tmp_path):
    build_report(
        ROOT / "data/published/inference.csv",
        ROOT / "data/published/inference_manifest.json",
        tmp_path,
    )
    manifest = json.loads((tmp_path / "research_findings_manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        actual = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
        assert actual == expected


def test_csv_scalar_formatting_is_explicit_and_stable():
    assert _csv_value(5.987260397910911e-55) == "5.98726039791091e-55"
    assert _csv_value(5.9872603979109114e-55) == "5.98726039791091e-55"
    assert _csv_value(4.0220083010041755e-18) == "4.02200830100418e-18"
    assert _csv_value(4.0220083010041763e-18) == "4.02200830100418e-18"
    assert _csv_value(float("nan")) == ""
    assert _csv_value(True) == "True"


def test_validation_rejects_wrong_grain():
    frame = pd.read_csv(ROOT / "data/published/inference.csv")
    manifest = json.loads((ROOT / "data/published/inference_manifest.json").read_text())
    bad = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="208 inference rows"):
        validate_inference(bad, manifest)
