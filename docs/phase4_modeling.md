# Phase 4: survey-aware population modeling

## Purpose and boundaries

Phase 4 adds a reproducible predictive benchmark for the binary outcome `MAR == 1` among Black-alone adults age 18 or older. It is designed to test whether a small, transparent set of ACS fields improves held-out population prediction over a weighted-prevalence baseline. It is not an individual risk score, eligibility tool, causal analysis, or forecast.

No person-level prediction, identifier, or feature row is written to Gold, the public S3 prefix, or the repository. The only outputs are aggregate performance metrics, aggregate calibration bins, and a model card.

## Design

- Training releases: 2022 and 2023 ACS 1-Year PUMS.
- Untouched evaluation release: 2024 ACS 1-Year PUMS.
- Population: `RAC1P == 2` and `AGEP >= 18`.
- Features: age, sex, state, educational attainment, and employment status.
- Models: a survey-weighted training-prevalence baseline and an L2-regularized survey-weighted logistic regression.
- Training weights: `PWGTP`. Identical feature patterns are collapsed to weighted positive and negative rows before fitting; this preserves the weighted binomial likelihood while reducing memory use.

The model coefficients are conditional associations. Education, employment, geography, age, and sex are not interpreted as causes. Phase 4 intentionally establishes a transparent baseline before adding a more complex tree model or SHAP layer; complexity will be added only if it yields a material, stable held-out improvement and can be explained without causal overstatement.

## Performance uncertainty and subgroup stability

Brier score, log loss, observed calibration rates, and mean predictions are calculated on 2024. For each statistic, the pipeline holds the fitted model and its 2024 predictions fixed, recomputes the statistic using each of the 80 ACS person replicate weights, and applies the ACS SDR variance factor `4/80`. This quantifies sampling uncertainty in held-out performance; it does not include model-refitting uncertainty.

Performance is reported overall, by sex, and by age band. Every metric carries its unweighted sample size and weighted denominator. The existing publication policy suppresses estimates with fewer than 30 unweighted records, nonpositive denominators, or relative standard error above 30%. Suppressed statistics are retained only in private Gold and are blanked in public artifacts.

## Reconciliation and publication

`publish-model-insights.yml` defaults to `publish=false`. It independently downloads the three authoritative Bronze archives and Silver Parquet partitions, fingerprints source-to-Silver rows, rebuilds aggregate model outputs, creates suppression-safe candidates, and checks Silver-to-Gold and Gold-to-published equality. Only an explicit `publish=true` run writes model artifacts; each published object is then re-downloaded and byte-compared with the reconciled candidate.

Every successful run retains the reconciled aggregate candidates, model card, and reconciliation report as a seven-day GitHub Actions review artifact. This makes a dry run numerically auditable without writing Gold or the published S3 prefix. The artifact contains no person-level records or predictions.

`snapshot-model-insights.yml` validates the aggregate-only and suppression contracts before committing the three public artifacts used by Streamlit. Both workflows use the existing S3 bucket and GitHub-hosted runners. They provision no infrastructure and create no always-on AWS cost.

## Known limitations

- ACS PUMS is observational and self-reported; the model cannot establish why a person is or is not married.
- The holdout is a later cross-section, not a longitudinal panel of the same people.
- Replicate-weight intervals condition on the fitted model and do not represent full training-set or hyperparameter-selection uncertainty.
- The model is intended for descriptive research and dashboard diagnostics only.
