# Black Outcomes Intelligence Platform

Production-oriented cloud analytics portfolio project using 2022–2024 ACS PUMS microdata to study Black American adult marriage, education, income, employment, and related outcomes.

## Architecture
Census ACS PUMS → validated S3 Bronze → curated Parquet/S3 Silver → replicate-weight Python estimator → versioned CSV/S3 Gold → byte-for-byte published snapshot → Streamlit. All workflows are manually dispatched; the public dashboard reads repository snapshots and requires no AWS access.

## Engineering stack
Python, SQL, AWS S3, AWS Glue, Athena, Terraform, Docker, GitHub Actions. Planned: dbt, PySpark, XGBoost/SHAP, Streamlit/Power BI.

## Statistical integrity

Population totals, rates, and means use `PWGTP`. Sampling variances use all 80 ACS person replicate weights (`PWGTP1`–`PWGTP80`) and the Census successive-difference-replication formula `SE = sqrt((4/80) * Σ(estimate_r - estimate)^2)`. Ratios and means recompute both numerator and denominator for every replicate. Published 95% confidence intervals are the point estimate ± `1.959964 × SE`, clipped to `[0, 1]` only for proportions.

Every metric carries `unweighted_n` and `weighted_denominator`. A value is marked `is_suppressed` and excluded from dashboard ranking when any of these transparent rules apply:

- unweighted denominator/sample count is below 30;
- weighted denominator is nonpositive;
- relative standard error (`SE / abs(estimate)`) exceeds 30% or cannot be calculated.

Suppressed point estimates remain only in private Gold for auditability. Public S3 and repository snapshots blank the estimate, standard error, confidence limits, and RSE before the dashboard renders “Suppressed.” These thresholds are a project publication policy, not a Census endorsement. See [docs/statistical_methodology.md](docs/statistical_methodology.md).

## Reconciliation and testing

`src.transform.reconcile` compares every normalized Bronze and Silver row with a streaming SHA-256 fingerprint, rebuilds Gold from Silver, and compares Gold with published output using exact schema/shape checks and `1e-12` numeric tolerance. Streaming keeps the national microdata check within a standard GitHub runner's memory. CI runs this end-to-end on deterministic synthetic records, including deliberate drift-failure tests. The production workflow independently downloads the authoritative Bronze ZIP, Silver Parquet, and Gold CSVs, builds the dashboard candidate, and invokes the full source-to-dashboard reconciliation. Its `publish` input defaults to `false`, allowing the real AWS-backed path to be exercised without writing the published prefix; an explicit `publish=true` run is required to write and byte-verify objects. Raw microdata are never committed.

Gold workflows upload an explicit allowlist of expected artifacts rather than synchronizing S3 prefixes. A missing local artifact fails the job before its upload. Existing non-allowlisted objects are intentionally retained for auditability instead of being deleted implicitly. CI forbids `aws s3 sync` anywhere in the Gold build workflow, so flag ordering or YAML line continuations cannot bypass the guard.

Run `pytest -q` locally. Building and publishing AWS artifacts is manual and uses existing S3 only; this Phase 1 change creates no infrastructure and runs no deployment automatically.

## Phase 2: Black women

Phase 2 adds a reconciled `intersectional.csv` mart and dashboard explorer for Black women by state and age band, with Black men as a descriptive benchmark. Population, marriage, education, employment, and income retain the same replicate-weight uncertainty, denominator, and suppression contract. See [docs/phase2_black_women.md](docs/phase2_black_women.md).

## Phase 3: longitudinal trends

Phase 3 adds 2022–2024 `trends.csv` and direct annual women-minus-men `contrasts.csv`. Each contrast is recomputed from the corresponding 80 replicate estimates; it is not formed by combining published standard errors. Cross-year changes remain descriptive because the pipeline does not have a Census-provided cross-year covariance design. New workflows build, reconcile, optionally publish, byte-verify, and snapshot these aggregates without provisioning infrastructure. See [docs/phase3_longitudinal.md](docs/phase3_longitudinal.md).

## Phase 4: survey-aware population modeling

Phase 4 fits a transparent survey-weighted marriage benchmark on 2022–2023 and evaluates it only on the untouched 2024 release. Brier score, log loss, subgroup diagnostics, and calibration use all 80 holdout replicate weights for sampling standard errors and 95% confidence intervals. Public outputs are aggregate and suppression-safe; person-level predictions are never published. The model is descriptive and predictive, not causal or suitable for individual decisions. See [docs/phase4_modeling.md](docs/phase4_modeling.md).

## Phase 5: nonlinear challenger robustness

Phase 5 evaluates an XGBoost challenger against the Phase 4 logistic model on the same untouched 2024 release. Paired per-record loss differences are recomputed with all 80 replicate weights, and stability is reported overall, by state, sex, age, and sex × age. Aggregate gain importance is descriptive only; SHAP and automatic promotion are deliberately excluded pending real held-out review. See [docs/phase5_model_robustness.md](docs/phase5_model_robustness.md).

## Phase 6: Ask the Data

Phase 6 adds an optional OpenAI Responses API assistant over the validated public aggregate snapshots. The assistant receives only a bounded evidence packet, must cite supplied records, and is blocked from displaying numeric claims that are absent from that evidence. It cannot access AWS, microdata, suppressed estimates, or person-level predictions. The API key stays in server-side configuration, activation requires a separate explicit flag, requests are rate- and size-limited for cost control, and tests use a fake client without paid calls. See [docs/phase6_ask_the_data.md](docs/phase6_ask_the_data.md).

## Phase 7: research inference

Phase 7 adds age-adjusted Black-women-minus-Black-men comparisons for marriage, education, employment, and personal income. A common 2024 national Black-adult age distribution and every adjusted outcome are recomputed through all 80 replicate weights. Direct paired contrasts carry 95% confidence intervals, p-values, and state-level Benjamini–Hochberg false-discovery-rate control. Statistical evidence remains separate from effect magnitude and causal interpretation. See [docs/phase7_research_inference.md](docs/phase7_research_inference.md).

## Phase 8: automated research findings report

Phase 8 generates deterministic Markdown, HTML, a complete aggregate appendix, and a hash manifest from the validated Phase 7 public snapshot. It reports national results, transparent state summary counts, uncertainty, multiplicity control, suppression, provenance, and limitations without generative text or microdata access. The manual workflow rebuilds every artifact twice and compares it byte-for-byte. Publication defaults off; an explicitly authorized release commits the exact reviewed bytes to a versioned repository snapshot, which the dashboard hash-validates before offering downloads. See [docs/phase8_research_report.md](docs/phase8_research_report.md).

## Phase 9A: external-review readiness

Phase 9A creates a deterministic, hash-manifested package for a qualified external statistician or survey-methodology reviewer. Independent recalculations cover release grain, age-standard weights, suppression/redaction, confidence intervals, and multiplicity control. Automated success means only that the package is ready for review: the project must not claim independent validation until a qualified reviewer completes and documents the review and a separate repository change is approved. See [docs/phase9a_external_review.md](docs/phase9a_external_review.md).

The low-cost public deployment path uses Streamlit Community Cloud with `main` and `app.py`. Deployment, project spending controls, secret entry, smoke testing, and final activation are separate gates. See [docs/phase6_community_cloud.md](docs/phase6_community_cloud.md).
