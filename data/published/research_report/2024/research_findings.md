# Black Outcomes Intelligence: 2024 Research Findings

**Release:** Phase 8 research report  
**Population:** Black-alone adults age 18+ in the 2024 ACS 1-year PUMS  
**Comparison:** Age-adjusted Black women minus Black men

## Executive summary

This report describes age-adjusted differences in marriage, bachelor's-or-higher attainment, employment, and mean personal income. It reports sampling uncertainty and multiplicity-adjusted evidence; it does not identify causes or predict individual outcomes.

The validated inference snapshot contains 208 comparisons: 180 publishable and 28 suppressed under the project's transparent stability rules.

## National findings

| Outcome | Black women | Black men | Women minus men (95% CI) | Multiplicity-adjusted evidence |
|---|---:|---:|---:|---|
| Marriage rate | 28.1% | 37.0% | -8.9% (-9.2% to -8.5%) | q=below machine precision (log10(q)=-471.392) |
| Bachelor's-or-higher attainment | 27.7% | 21.3% | +6.4% (+6.0% to +6.9%) | q=4.19e-169 |
| Employment rate | 61.8% | 59.5% | +2.3% (+1.9% to +2.7%) | q=1.79e-25 |
| Mean personal income | $38,760 | $45,141 | -$6,380 (-$6,887 to -$5,874) | q=1.52e-134 |

Differences are descriptive population estimates. Statistical distinguishability does not imply practical importance, fairness, mechanism, or causation.

## State findings

State tests are adjusted separately within each outcome across 51 comparisons. The complete machine-readable appendix accompanies this report so the selected summaries can be audited.

### Marriage rate

37 of 44 publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed.

Largest five absolute publishable differences among FDR-significant states (a transparent descriptive ranking, not an importance or causal ranking):

| State | Difference | 95% CI | q-value |
|---|---:|---:|---:|
| New Mexico | -16.0% | -28.8% to -3.2% | 0.0188 |
| Minnesota | -13.6% | -19.6% to -7.5% | 1.91e-05 |
| Oregon | -12.0% | -20.2% to -3.9% | 0.00485 |
| Wisconsin | -11.3% | -15.9% to -6.8% | 2.28e-06 |
| Connecticut | -10.9% | -14.8% to -7.0% | 1.02e-07 |

### Bachelor's-or-higher attainment

25 of 44 publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed.

Largest five absolute publishable differences among FDR-significant states (a transparent descriptive ranking, not an importance or causal ranking):

| State | Difference | 95% CI | q-value |
|---|---:|---:|---:|
| West Virginia | +12.7% | +3.2% to +22.2% | 0.016 |
| Oklahoma | +11.5% | +6.0% to +17.0% | 0.000104 |
| Arkansas | +9.5% | +5.6% to +13.4% | 4.43e-06 |
| Mississippi | +9.4% | +7.0% to +11.8% | 1.12e-13 |
| Tennessee | +8.8% | +6.5% to +11.2% | 1.27e-12 |

### Employment rate

14 of 44 publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed.

Largest five absolute publishable differences among FDR-significant states (a transparent descriptive ranking, not an importance or causal ranking):

| State | Difference | 95% CI | q-value |
|---|---:|---:|---:|
| West Virginia | +17.0% | +6.9% to +27.2% | 0.00511 |
| Rhode Island | -15.2% | -26.4% to -4.0% | 0.028 |
| Minnesota | -10.4% | -16.5% to -4.3% | 0.00511 |
| Delaware | +8.7% | +1.9% to +15.6% | 0.0389 |
| Illinois | +8.5% | +6.2% to +10.8% | 3.44e-11 |

### Mean personal income

29 of 44 publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed.

Largest five absolute publishable differences among FDR-significant states (a transparent descriptive ranking, not an importance or causal ranking):

| State | Difference | 95% CI | q-value |
|---|---:|---:|---:|
| New Hampshire | +$28,724 | +$10,877 to +$46,571 | 0.00283 |
| Kansas | -$16,825 | -$26,979 to -$6,670 | 0.00214 |
| Washington | -$16,501 | -$25,148 to -$7,854 | 0.000405 |
| Colorado | -$16,486 | -$23,883 to -$9,089 | 3.45e-05 |
| Massachusetts | -$10,593 | -$14,910 to -$6,276 | 5.13e-06 |

## Methods and limitations

- Estimates use ACS person weights and all 80 person replicate weights with the Census SDR factor 4/80.
- Direct age standardization uses the common 2024 national Black-adult age distribution across six age bands.
- Women-minus-men differences and uncertainty are recomputed from paired replicate estimates.
- State p-values use Benjamini–Hochberg FDR adjustment within each outcome; national q-values equal p-values.
- Cells are suppressed when component stability, sample-size, denominator, or finite-uncertainty rules fail.
- If one component is suppressed, the direct comparison is suppressed; the other component remains visible only when it independently passes every publication rule.
- ACS PUMS is cross-sectional observational data. Results are associations, not causal effects.
- Race, sex, income, employment, education, and marital-status variables follow the source-data definitions and do not capture every relevant identity or structural factor.
- Cross-year change is not tested here because the available design does not provide cross-year covariance.

## Provenance

This report was generated deterministically from the repository's public aggregate inference snapshot. No Census microdata, suppressed estimates, person-level predictions, or generative-AI-written findings are included.

- `inference.csv` SHA-256: `419fe8bf28e4dfdf9ccddad03e4f2d60260d1314bc3ff7d3f5c7cfe7c2e03762`
- `inference_manifest.json` SHA-256: `7e01629042d26e05240cf1483ee820dddda57830c08f487c42bfe3dd5250a4a5`
