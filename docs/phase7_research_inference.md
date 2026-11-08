# Phase 7: research inference foundation

## Decision question

Phase 7 asks whether observed 2024 Black-women-minus-Black-men differences remain statistically distinguishable after age adjustment and state-level multiplicity control. It covers marriage, bachelor's-or-higher attainment, employment, and mean personal income. It does not claim that sex, education, employment, geography, or marriage causes another outcome.

## Age standardization

Direct standardization uses six age bands: 18–24, 25–34, 35–44, 45–54, 55–64, and 65+. The reference distribution is the 2024 national Black-alone adult population (`RAC1P = 2`, age 18+). Black women's and Black men's stratum-specific estimates are averaged using this same reference. The reference weights and every stratum estimate are recomputed with each of the 80 ACS person replicate weights, so their sampling variation is propagated into the adjusted estimates and direct contrast.

## Direct inference

The contrast is Black women minus Black men. Its point estimate and all 80 replicate estimates are formed by paired subtraction. The ACS SDR standard error uses `(4/80) × Σ(θr − θ)²`; the two-sided p-value uses the resulting normal test statistic. A precise zero difference is retained rather than suppressed for having an undefined relative standard error.

National results report `q = p`. State comparisons use Benjamini–Hochberg false-discovery-rate adjustment separately for each outcome across the 51 state-level comparisons. Adjustment is performed in log space so extreme probabilities cannot collapse to a false exact zero. Values smaller than the smallest positive IEEE-754 float are stored at that positive floor, explicitly flagged, and accompanied by their `log10` value. `difference_fdr_significant` means `q ≤ 0.05`; it is not a causal or practical-importance label. The dashboard always displays the difference in its original unit so readers can judge magnitude separately from sampling evidence.

## Suppression and publication

Each age-adjusted component retains the existing minimum unweighted sample, positive-denominator, and relative-standard-error rules. A direct difference is suppressed when either component is suppressed, a component has fewer than 30 unweighted records, a denominator is nonpositive, or the difference or its standard error is nonfinite. Suppressed public rows blank component estimates, difference estimates, uncertainty, p-values, q-values, and the FDR decision while retaining flags, reasons, sample sizes, and denominators.

The manual workflow downloads the authoritative Bronze ZIP and Silver Parquet independently, builds Gold and public candidates, reconciles source→Silver→Gold→published, and retains a seven-day aggregate review artifact. `publish=false` writes nothing to S3. Publication and repository snapshotting require separate manual actions from `main` and provision no infrastructure.
