# ACS PUMS statistical methodology

## Universe and estimands

The analysis universe is people age 18 or older with `RAC1P = 2` (Black or African American alone) in the named ACS 1-year PUMS release. This is not the broader “Black alone or in combination” population. State is the most detailed geography published in Phase 1. PUMS cannot support invented city/place estimates.

The Gold layer publishes: Black adult population total; currently married share (`MAR = 1`); bachelor's degree or higher share (`SCHL >= 21`); and mean personal income (`PINCP`) among records where personal income is present. Each rate's denominator is the full Black-adult universe in that geography. The income denominator is the weighted population with nonmissing `PINCP`.

## Survey design

Point estimates use the final person weight `PWGTP`. Sampling standard errors use the 80 final person replicate weights `PWGTP1` through `PWGTP80`. For estimate `θ` and replicate estimates `θr`, the ACS successive-difference-replication variance is:

`variance(θ) = (4 / 80) × Σ(θr − θ)²`.

The standard error is the square root of that variance. A ratio or mean is independently recomputed with each replicate's weighted numerator and denominator; it is not derived by scaling a point-estimate standard error. A 95% confidence interval is `θ ± 1.95996398454 × SE`. Proportion intervals alone are bounded to `[0, 1]`. These intervals describe sampling uncertainty and do not cover nonsampling error.

Primary reference: the Census Bureau's [ACS PUMS Technical Documentation](https://www.census.gov/programs-surveys/acs/microdata/documentation.html) and [PUMS User Guide](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/2021ACS_PUMS_User_Guide.pdf), which specifies 80 replicate estimates and the `4/80` SDR variance factor.

The Census [2020–2024 PUMS Accuracy documentation](https://www2.census.gov/programs-surveys/acs/tech_docs/pums/accuracy/2020_2024AccuracyPUMS.pdf) notes that replicate weights may be positive, zero, or negative. Negative replicate weights are preserved and used only for variance estimation; the full-sample `PWGTP` remains strictly positive.

## Publication suppression

Each metric includes its point estimate, standard error, 95% limits, relative standard error, unweighted sample count, weighted denominator, suppression flag, and machine-readable reason. The public view suppresses a metric if unweighted n is below 30, its denominator is nonpositive, or RSE exceeds 30%/is undefined. Rules are evaluated per metric because income and universe denominators can differ. Suppression never substitutes a zero and never fabricates an estimate.

Complete suppressed statistics are retained in private Gold for auditability. The publication transform replaces their point estimate, standard error, confidence limits, and RSE with null values before writing public S3 objects or repository snapshots. Reconciliation derives this redacted projection independently and fails if a suppressed statistic leaks into a public candidate.

## Lineage and reproducibility

Bronze validation requires the final and all 80 replicate weights. Silver preserves those columns as integers and records the replicate method in its manifest. Gold is built by the tested Python estimator rather than point-estimate-only Athena SQL. Reconciliation verifies source-to-Silver records, rebuilds Silver-to-Gold outputs, and checks Gold-to-published artifacts. The production publish job performs byte comparisons after copying; the deterministic integration test exercises the complete logical chain without external data or AWS cost.

## Limitations

No significance tests, multiple-comparison adjustments, causal claims, model-based estimates, or disclosure-avoidance corrections are added in Phase 1. Existing checked-in point-estimate-only snapshots are historical and must not be treated as Phase 1 output; the dashboard now rejects snapshots without uncertainty and suppression fields. A real 2024 refresh requires the official Census archive and authorized manual AWS workflows.
