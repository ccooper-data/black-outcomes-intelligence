# Phase 3: 2022–2024 longitudinal analysis

## Scope

Phase 3 compares the 2022, 2023, and 2024 ACS 1-Year PUMS releases at the same state × sex × age-band grain used in Phase 2. It publishes annual population, marriage, bachelor's-or-higher, employment, and mean-personal-income estimates with each year's replicate-weight standard error and 95% confidence interval.

`trends.csv` contains 2,184 rows: 3 years × 52 geographies (national plus 51 state/DC codes) × 2 sex groups × 7 age groupings. `contrasts.csv` contains 1,092 rows: 3 years × 52 geographies × 7 age groupings. These counts are enforced before AWS upload and during the repository snapshot.

## Direct comparisons

Every contrast is Black women minus Black men within the same survey year, geography, age band, and estimand. The point difference is `θwomen − θmen`; each of the 80 replicate differences is `θwomen,r − θmen,r`. Its standard error is computed directly with the ACS `4/80` SDR formula. Rate-difference intervals are bounded to `[-1, 1]`; totals and income differences are not artificially bounded.

Contrast suppression uses the smaller of the two groups' unweighted sample sizes and weighted denominators, plus the same 30% RSE rule. Both groups' denominators are retained explicitly. The public transform nulls suppressed statistics while retaining flags, reasons, and denominator evidence.

## Cross-year interpretation

Annual estimates and their own confidence intervals are valid under each release's replicate-weight design. Phase 3 does not calculate a significance test for a change between releases because the inputs do not provide a cross-year covariance design. The dashboard therefore labels changes as descriptive and never infers causality from movement or interval overlap.

## Quality and lineage gates

The longitudinal builder requires exactly 2022, 2023, and 2024 and fails closed on missing design columns or incompatible required-field dtypes. The official 2022 CSV geography field `ST` is explicitly canonicalized to the 2023–2024 `STATE` name at the Silver boundary; values are not remapped. The publish gate independently downloads all three Bronze ZIPs, all three Silver Parquet partitions, and longitudinal Gold; fingerprints source-to-Silver rows for every year; rebuilds Gold; derives the public redacted projection; and compares the result with the publish candidate. An optional publish then re-downloads every S3 object and byte-compares it with the reconciled candidate.

The existing build and publish workflows accept `year=2022-2024`; the dedicated snapshot workflow runs after publication. All workflows are manual. They reuse the existing S3 bucket and GitHub-hosted runners and create no new infrastructure or always-on AWS service.
