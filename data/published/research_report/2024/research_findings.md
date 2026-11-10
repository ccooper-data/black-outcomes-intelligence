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

State tests are adjusted separately within each outcome across non-suppressed comparisons; suppressed states are not tested or included in the family. The complete machine-readable appendix accompanies this report so the selected summaries can be audited.

### Marriage rate

Largest five absolute publishable differences, shown first to emphasize effect size and uncertainty rather than statistical significance (a descriptive display, not an importance or causal ranking):

| State | Difference | 95% CI | FDR evidence |
|---|---:|---:|---|
| Maine | -17.0% | -34.9% to +0.9% | not FDR-significant (q=0.0703) |
| Hawaii | -16.3% | -35.7% to +3.1% | not FDR-significant (q=0.109) |
| New Mexico | -16.0% | -28.8% to -3.2% | q=0.0188 |
| Minnesota | -13.6% | -19.6% to -7.5% | q=1.91e-05 |
| Utah | -12.7% | -25.4% to -0.0% | not FDR-significant (q=0.0571) |

After examining effect sizes, 37 of 44 tested, publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed and excluded from the testing family.

### Bachelor's-or-higher attainment

Largest five absolute publishable differences, shown first to emphasize effect size and uncertainty rather than statistical significance (a descriptive display, not an importance or causal ranking):

| State | Difference | 95% CI | FDR evidence |
|---|---:|---:|---|
| West Virginia | +12.7% | +3.2% to +22.2% | q=0.016 |
| Oklahoma | +11.5% | +6.0% to +17.0% | q=0.000104 |
| Rhode Island | +10.5% | -1.7% to +22.7% | not FDR-significant (q=0.15) |
| Maine | +9.7% | -7.3% to +26.6% | not FDR-significant (q=0.363) |
| Arkansas | +9.5% | +5.6% to +13.4% | q=4.43e-06 |

After examining effect sizes, 25 of 44 tested, publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed and excluded from the testing family.

### Employment rate

Largest five absolute publishable differences, shown first to emphasize effect size and uncertainty rather than statistical significance (a descriptive display, not an importance or causal ranking):

| State | Difference | 95% CI | FDR evidence |
|---|---:|---:|---|
| West Virginia | +17.0% | +6.9% to +27.2% | q=0.00511 |
| Rhode Island | -15.2% | -26.4% to -4.0% | q=0.028 |
| Minnesota | -10.4% | -16.5% to -4.3% | q=0.00511 |
| Utah | -10.3% | -21.4% to +0.7% | not FDR-significant (q=0.156) |
| Delaware | +8.7% | +1.9% to +15.6% | q=0.0389 |

After examining effect sizes, 14 of 44 tested, publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed and excluded from the testing family.

### Mean personal income

Largest five absolute publishable differences, shown first to emphasize effect size and uncertainty rather than statistical significance (a descriptive display, not an importance or causal ranking):

| State | Difference | 95% CI | FDR evidence |
|---|---:|---:|---|
| New Hampshire | +$28,724 | +$10,877 to +$46,571 | q=0.00283 |
| Hawaii | -$25,234 | -$53,681 to +$3,214 | not FDR-significant (q=0.113) |
| Kansas | -$16,825 | -$26,979 to -$6,670 | q=0.00214 |
| Washington | -$16,501 | -$25,148 to -$7,854 | q=0.000405 |
| Colorado | -$16,486 | -$23,883 to -$9,089 | q=3.45e-05 |

After examining effect sizes, 29 of 44 tested, publishable state comparisons meet the within-outcome 5% Benjamini–Hochberg FDR rule; 7 are suppressed and excluded from the testing family.

## Methods and limitations

- Estimates use ACS person weights and all 80 person replicate weights with the Census SDR factor 4/80.
- Direct age standardization uses the common 2024 national Black-adult age distribution across six age bands.
- Women-minus-men differences and uncertainty are recomputed from paired replicate estimates.
- State p-values use Benjamini–Hochberg FDR adjustment within each outcome across non-suppressed state tests; national q-values equal p-values.
- Component estimates are suppressed for sample-size, denominator, or RSE failures. Signed contrasts are not suppressed for high or undefined contrast RSE; their uncertainty is reported with the SE, 95% CI, and adjusted test.
- If one component is suppressed, the direct comparison is suppressed; the other component remains visible only when it independently passes every publication rule.
- ACS PUMS is cross-sectional observational data. Results are associations, not causal effects.
- Race, sex, income, employment, education, and marital-status variables follow the source-data definitions and do not capture every relevant identity or structural factor.
- Cross-year change is not tested here because the available design does not provide cross-year covariance.
- The 2024 release was previously used for Phase 4 and Phase 5 model evaluation. This descriptive report is not a new predictive holdout evaluation.

## Provenance

This report was generated deterministically from the repository's public aggregate inference snapshot. No Census microdata, suppressed estimates, person-level predictions, or generative-AI-written findings are included.

- `inference.csv` SHA-256: `9a2b72adb4a21c1402053270cff2781ce6cec2db29753e487d74da18fa22e12a`
- `inference_manifest.json` SHA-256: `85447607ed837343284fe9853744e7595c4c48c1939a108ade98b1c194268aaa`
