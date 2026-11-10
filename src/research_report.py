"""Load and verify the public Phase 8 research-report package."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ARTIFACTS = (
    "research_findings.md",
    "research_findings.html",
    "research_findings_appendix.csv",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_report_package(report_dir: Path) -> tuple[dict, dict[str, bytes]]:
    manifest_path = report_dir / "research_findings_manifest.json"
    if not manifest_path.exists():
        return {}, {}
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("phase") != 8
        or manifest.get("survey_year") != 2024
        or manifest.get("causal_interpretation") is not False
        or manifest.get("rows") != 208
        or manifest.get("publishable_rows") + manifest.get("suppressed_rows") != 208
        or manifest.get("unstable_contrast_rse_rows", 0) < 0
        or manifest.get("unstable_contrast_rse_rows", 0) > manifest.get("publishable_rows", 0)
        or manifest.get("unstable_contrast_rse_fdr_significant_rows", 0) < 0
        or manifest.get("unstable_contrast_rse_fdr_significant_rows", 0)
        > manifest.get("unstable_contrast_rse_rows", 0)
    ):
        raise ValueError("Published Phase 8 report manifest failed its release contract.")
    data: dict[str, bytes] = {}
    for name in ARTIFACTS:
        path = report_dir / name
        if not path.exists():
            raise ValueError(f"Published Phase 8 report is missing {name}.")
        payload = path.read_bytes()
        if _sha256(payload) != manifest.get("artifacts", {}).get(name):
            raise ValueError(f"Published Phase 8 report hash mismatch for {name}.")
        data[name] = payload
    return manifest, data
