# Phase 2: Black women intersectional outcomes

## Scope

Phase 2 adds a research-grade descriptive layer for Black women age 18 or older (`RAC1P = 2`, `SEX = 2`). Black men (`SEX = 1`) are included only as a same-geography, same-age descriptive benchmark. The analysis does not claim that sex causes an observed difference and does not label a difference statistically significant without a direct contrast variance test.

The intersectional mart contains national and state estimates for all adults and six age bands: 18–24, 25–34, 35–44, 45–54, 55–64, and 65+. It publishes population, marriage, bachelor's-or-higher education, employment, and mean personal income measures.

## Employment definition

The employment numerator includes ACS `ESR` codes 1, 2, 4, and 5. Its denominator includes nonmissing substantive `ESR` codes 1 through 6. Each replicate rate independently recomputes the numerator and denominator using `PWGTP1`–`PWGTP80`.

## Statistical and publication rules

All Phase 1 rules remain mandatory: ACS SDR standard errors, 95% confidence intervals, explicit unweighted n and weighted denominators, and suppression for n below 30, nonpositive denominators, or RSE above 30%/undefined. Suppressed cells remain auditable in Gold but render as “Suppressed” publicly. The dashboard never converts a suppressed result to zero.

The mart grain is `(survey_year, state, sex, age_band)`. A null state means national. Source→Silver→Gold→published reconciliation covers the new `SEX` field and `intersectional.csv` artifact.
