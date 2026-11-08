# Phase 5: nonlinear challenger robustness

## Decision

Phase 5 asks whether a nonlinear XGBoost challenger provides stable held-out improvement over the transparent Phase 4 logistic model. It does not replace or promote a model automatically. Both models train on the same 2022–2023 Black-adult population and are evaluated on the same untouched 2024 records.

The output remains a population-level research diagnostic. It is not an individual risk score, causal model, eligibility tool, or forecast. No person-level feature row or prediction is written to Gold, public S3, a workflow artifact, or the repository.

## Paired survey-design comparison

For Brier score and log loss, improvement is defined as logistic loss minus XGBoost loss on each 2024 record. The point estimate weights those paired differences with `PWGTP`. Each of the 80 replicate estimates weights the same paired differences with the matching `PWGTP1`–`PWGTP80`; the standard error then uses the ACS SDR factor `4/80`. Positive improvement favors XGBoost.

This pairing is stronger than comparing two separately calculated confidence intervals because it retains the covariance induced by evaluating both models on identical records. The interval still conditions on the fitted models and does not include model-refitting or hyperparameter-selection uncertainty.

## Stability coverage

Model loss and paired improvements are reported overall and by:

- sex;
- age band;
- state/DC;
- sex × age band.

All results retain unweighted sample size and weighted denominator. The existing publication policy suppresses unstable cells, and public artifacts blank suppressed estimates, standard errors, intervals, and RSE values. Calibration uses survey-weighted prediction deciles for both logistic and XGBoost.

## Explainability boundary

The repository publishes aggregate XGBoost gain importance only. Gain can identify features the fitted model used frequently or strongly, but it is not causal evidence and is not an individual explanation. SHAP is deliberately deferred: it will be considered only after the real held-out challenger results pass review, and only as aggregate descriptive evidence with an explicit correlated-feature limitation.

## Promotion gate

The model card records whether both overall paired Brier-score and log-loss improvement 95% confidence intervals are strictly above zero. Passing that gate is necessary but not sufficient for promotion. Review must also consider subgroup reversals, calibration, practical magnitude, feature behavior, and the limitations of a single later-year holdout. `automatic_promotion` is always false.

The XGBoost package is pinned to an exact reviewed version, and the model card records the XGBoost and scikit-learn runtime versions plus all explicitly selected challenger parameters.

## Reconciliation and cost control

`publish-model-robustness.yml` defaults to `publish=false`. It downloads authoritative Bronze and Silver inputs, builds the challenger evidence, independently rebuilds it during reconciliation, creates suppression-safe candidates, and retains an aggregate seven-day review artifact. An explicit later `publish=true` run is required for S3 writes and re-download byte verification.

`snapshot-model-robustness.yml` is separate and manual. Both workflows reuse the existing S3 bucket and GitHub-hosted runners. They provision no infrastructure and create no always-on AWS cost.
