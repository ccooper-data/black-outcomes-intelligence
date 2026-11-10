"""Build the Phase 9A package for an independent survey-methodology review."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

Z_95 = 1.959963984540054
EXPECTED_ROWS = 208
EXPECTED_METRICS = {
    "married_rate", "bachelors_plus_rate", "employment_rate", "mean_personal_income"
}
REDACTED_FIELDS = (
    "difference_estimate", "difference_standard_error", "difference_ci95_lower",
    "difference_ci95_upper", "difference_relative_standard_error", "difference_p_value",
    "difference_log10_p_value", "difference_q_value", "difference_log10_q_value",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def independent_sdr_standard_error(estimate: float, replicates: np.ndarray) -> float:
    """Independent ACS SDR implementation; deliberately does not import production survey code."""
    values = np.asarray(replicates, dtype=float)
    if values.shape != (80,):
        raise ValueError("ACS person inference requires exactly 80 replicate estimates")
    return math.sqrt((4.0 / 80.0) * float(np.square(values - estimate).sum()))


def independent_bh_log10(values: np.ndarray) -> np.ndarray:
    """Benjamini-Hochberg adjustment in log10 space, independently implemented."""
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    adjusted = ranked + np.log10(len(values) / np.arange(1, len(values) + 1))
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.minimum(adjusted, 0.0)
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


def _check(name: str, passed: bool, evidence: str) -> dict[str, object]:
    return {"check": name, "passed": bool(passed), "evidence": evidence}


def validate_public_release(inference_path: Path, inference_manifest_path: Path,
                            report_manifest_path: Path) -> dict[str, object]:
    frame = pd.read_csv(inference_path)
    inference_manifest = json.loads(inference_manifest_path.read_text())
    report_manifest = json.loads(report_manifest_path.read_text())
    checks: list[dict[str, object]] = []

    checks.append(_check(
        "frozen_source_hashes",
        report_manifest["source_hashes"] == {
            inference_path.name: sha256(inference_path),
            inference_manifest_path.name: sha256(inference_manifest_path),
        },
        "Phase 8 source hashes match the exact Phase 7 public snapshot.",
    ))
    national = frame["state"].isna()
    checks.append(_check(
        "release_grain",
        len(frame) == EXPECTED_ROWS
        and int(national.sum()) == 4
        and int((~national).sum()) == 204
        and set(frame["metric"]) == EXPECTED_METRICS
        and not frame.duplicated(["state", "metric"], keep=False).any(),
        f"rows={len(frame)}; national={int(national.sum())}; state={int((~national).sum())}",
    ))
    age_weight_sum = sum(inference_manifest["age_standard_weights"].values())
    checks.append(_check(
        "age_standard_contract",
        math.isclose(age_weight_sum, 1.0, rel_tol=0.0, abs_tol=1e-12)
        and inference_manifest["age_standard"] == "2024 national Black-adult age distribution",
        f"six published age-standard weights sum to {age_weight_sum:.16g}",
    ))

    suppressed = frame["difference_is_suppressed"].astype(str).str.lower().eq("true")
    redacted = frame.loc[suppressed, list(REDACTED_FIELDS)].isna().all().all()
    counts_match = (
        int((~suppressed).sum()) == report_manifest["publishable_rows"]
        and int(suppressed.sum()) == report_manifest["suppressed_rows"]
    )
    checks.append(_check(
        "suppression_and_redaction",
        redacted and counts_match,
        f"publishable={int((~suppressed).sum())}; suppressed={int(suppressed.sum())}; suppressed statistics redacted={redacted}",
    ))

    visible = frame.loc[~suppressed].copy()
    components_stable = (
        visible[["women_unweighted_n", "men_unweighted_n"]].ge(30).all().all()
        and visible[["women_relative_standard_error", "men_relative_standard_error"]].le(0.30).all().all()
    )
    high_contrast_rse = visible["difference_relative_standard_error"].gt(0.30) | ~np.isfinite(
        visible["difference_relative_standard_error"]
    )
    marker_present = "difference_rse_unstable" in visible
    marker_matches = not marker_present or visible["difference_rse_unstable"].astype(str).str.lower().eq(
        high_contrast_rse.astype(str).str.lower()
    ).all()
    checks.append(_check(
        "component_and_contrast_suppression_policy",
        components_stable and int(high_contrast_rse.sum()) == 96 and marker_matches,
        f"all visible components pass n/RSE rules; {int(high_contrast_rse.sum())} visible signed contrasts exceed 30% RSE or have undefined RSE and remain visible by design; marker present={marker_present}; present markers match={marker_matches}",
    ))
    rate = visible["metric"].str.endswith("_rate")
    expected_low = visible["difference_estimate"] - Z_95 * visible["difference_standard_error"]
    expected_high = visible["difference_estimate"] + Z_95 * visible["difference_standard_error"]
    expected_low.loc[rate] = expected_low.loc[rate].clip(lower=-1.0, upper=1.0)
    expected_high.loc[rate] = expected_high.loc[rate].clip(lower=-1.0, upper=1.0)
    # Public CSV parsing can move large income limits by a few binary ULPs.
    ci_ok = np.allclose(visible["difference_ci95_lower"], expected_low, rtol=0, atol=1e-10) and np.allclose(
        visible["difference_ci95_upper"], expected_high, rtol=0, atol=1e-10
    )
    checks.append(_check(
        "confidence_intervals",
        ci_ok,
        f"independently recomputed {len(visible)} visible 95% intervals with z={Z_95}",
    ))

    bh_ok = True
    bh_rows = 0
    for metric in sorted(EXPECTED_METRICS):
        mask = (~suppressed) & frame["state"].notna() & frame["metric"].eq(metric)
        observed = frame.loc[mask, "difference_log10_q_value"].to_numpy(float)
        expected = independent_bh_log10(frame.loc[mask, "difference_log10_p_value"].to_numpy(float))
        bh_ok &= np.allclose(observed, expected, rtol=0, atol=1e-12)
        bh_rows += int(mask.sum())
    national_ok = np.allclose(
        visible.loc[visible["state"].isna(), "difference_log10_q_value"],
        visible.loc[visible["state"].isna(), "difference_log10_p_value"], rtol=0, atol=1e-12,
    )
    checks.append(_check(
        "multiplicity_control",
        bh_ok and national_ok,
        f"independently recomputed BH-FDR for {bh_rows} visible state comparisons; national q=p",
    ))
    expected_flags = visible["difference_q_value"].le(0.05)
    observed_flags = visible["difference_fdr_significant"].astype(str).str.lower().eq("true")
    state_flags = int(observed_flags[visible["state"].notna()].sum())
    national_flags = int(observed_flags[visible["state"].isna()].sum())
    checks.append(_check(
        "significance_flags",
        observed_flags.equals(expected_flags),
        f"flags agree with q<=0.05: {state_flags} of {int(visible['state'].notna().sum())} visible state contrasts and {national_flags} of 4 national contrasts",
    ))
    checks.append(_check(
        "claims_contract",
        inference_manifest.get("causal_interpretation") is False
        and report_manifest.get("causal_interpretation") is False,
        "Both source manifests explicitly prohibit causal interpretation.",
    ))

    if not all(item["passed"] for item in checks):
        failed = [item["check"] for item in checks if not item["passed"]]
        raise AssertionError(f"Phase 9A validation failed: {failed}")
    return {
        "phase": "9A",
        "status": "external_review_pending",
        "independent_validation_claimed": False,
        "scope": "2024 Phase 7 inference and Phase 8 research-report release",
        "source_hashes": {
            inference_path.name: sha256(inference_path),
            inference_manifest_path.name: sha256(inference_manifest_path),
            report_manifest_path.name: sha256(report_manifest_path),
        },
        "checks": checks,
        "summary": {"passed": len(checks), "failed": 0, "total": len(checks)},
    }


def build_package(inference_path: Path, inference_manifest_path: Path,
                  report_manifest_path: Path, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results = validate_public_release(inference_path, inference_manifest_path, report_manifest_path)
    (output_dir / "source_inference.csv").write_bytes(inference_path.read_bytes())
    (output_dir / "source_inference_manifest.json").write_bytes(inference_manifest_path.read_bytes())
    (output_dir / "source_research_findings_manifest.json").write_bytes(report_manifest_path.read_bytes())
    (output_dir / "validation_results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    (output_dir / "README.md").write_text(
        "# Black Outcomes Intelligence — Phase 9A external-review package\n\n"
        "Status: **external review pending**. Passing automated checks is internal validation and is not independent approval.\n\n"
        "This package includes the exact reviewed public inference snapshot and its manifests, records cryptographic source hashes, and provides independent recalculations of release grain, age-standard weights, suppression/redaction, 95% intervals, and Benjamini–Hochberg correction. It does not contain ACS person microdata. The package is descriptive: because the 2024 release was previously used in Phase 4 and Phase 5 model evaluation, it is not a new predictive holdout.\n\n"
        "A qualified reviewer should use `review_checklist.md`, record findings in `reviewer_findings.json`, and sign only after resolving material issues. Repository maintainers must separately verify reviewer identity and qualifications before changing the public status.\n"
    )
    (output_dir / "review_checklist.md").write_text(
        "# Independent review checklist\n\n"
        "- [ ] Confirm reviewer name, affiliation, relevant survey-methodology qualifications, and conflicts.\n"
        "- [ ] Verify ACS person universe, variables, final weight, and all 80 person replicate weights.\n"
        "- [ ] Reproduce SDR variance, ratio/mean replicate recomputation, and 95% intervals.\n"
        "- [ ] Evaluate direct age standardization and replicate-specific standard weights.\n"
        "- [ ] Reproduce women-minus-men paired replicate contrasts and inferential tests.\n"
        "- [ ] Reproduce within-outcome state Benjamini–Hochberg FDR control using only non-suppressed, tested states in each family.\n"
        "- [ ] Assess component suppression thresholds and confirm that contrast RSE is disclosed but is not itself a suppression rule.\n"
        "- [ ] Review held-out predictive validation and the stated model-refitting limitation.\n"
        "- [ ] Confirm repeated cross-sectional and noncausal language throughout.\n"
        "- [ ] Record every finding, severity, evidence location, and disposition.\n"
        "- [ ] Sign only after all blocking findings are resolved and independently retested.\n"
    )
    findings = {
        "review_status": "not_started",
        "independent_validation_approved": False,
        "reviewer": {"name": "", "affiliation": "", "qualifications": "", "conflicts": ""},
        "scope": results["scope"],
        "package_manifest_sha256": "populate_after_package_download",
        "findings": [],
        "conclusion": "",
        "signed_at": "",
        "signature": "",
    }
    (output_dir / "reviewer_findings.json").write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n")
    artifacts = {
        path.name: sha256(path) for path in sorted(output_dir.iterdir()) if path.name != "package_manifest.json"
    }
    package_manifest = {
        "phase": "9A", "status": "external_review_pending",
        "independent_validation_claimed": False, "artifacts": artifacts,
    }
    (output_dir / "package_manifest.json").write_text(json.dumps(package_manifest, indent=2, sort_keys=True) + "\n")
    return package_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", type=Path, required=True)
    parser.add_argument("--inference-manifest", type=Path, required=True)
    parser.add_argument("--report-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_package(args.inference, args.inference_manifest, args.report_manifest, args.output_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
