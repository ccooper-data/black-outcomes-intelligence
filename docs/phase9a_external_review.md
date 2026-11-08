# Phase 9A — external-review package

Phase 9A prepares the validated 2024 public inference and research-report release for examination by a qualified statistician or survey-methodology reviewer. It does not award or imply independent validation.

The manual workflow performs independent recalculations without importing the production survey estimator, freezes the exact public source hashes, builds the package twice, compares every byte, and retains the resulting artifact for 30 days. It makes no AWS calls, uses no Census person microdata, and publishes nothing automatically.

The automated checks cover the release grain, age-standard weight sum, public suppression/redaction, 95% confidence intervals, state-level Benjamini–Hochberg adjustment, source lineage, and noncausal claims contract. These checks establish review readiness; they are not a substitute for expert judgment about the estimands, survey design, or interpretation.

The reviewer package contains:

- `README.md`: scope and use instructions;
- `validation_results.json`: machine-readable internal checks and frozen source hashes;
- `source_inference.csv` and source manifests: the exact aggregate public evidence under review;
- `review_checklist.md`: the required methodological review areas;
- `reviewer_findings.json`: a blank findings and sign-off record that defaults to not approved; and
- `package_manifest.json`: SHA-256 hashes for every package artifact.

Changing the public status requires a completed findings record, resolution of all blocking findings, verification of the reviewer's relevant qualifications and conflicts, and a separately reviewed repository change. Until then, the only accurate status is **External review pending**.
