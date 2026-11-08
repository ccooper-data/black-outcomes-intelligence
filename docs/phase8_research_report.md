# Phase 8: automated research findings report

Phase 8 converts the validated Phase 7 public aggregate snapshot into deterministic Markdown, HTML, CSV appendix, and JSON manifest artifacts. It does not rerun Census microdata, call a language model, provision infrastructure, or publish automatically.

## Evidence contract

The builder accepts only the 208-row 2024 Phase 7 inference grain: one national and 51 state rows for each of four outcomes. It verifies the unique state-outcome grain, required statistical fields, source manifest row count, and the explicit prohibition on causal interpretation.

The report includes all four national comparisons. For each outcome, its state narrative reports the count of publishable FDR-significant comparisons and the count suppressed. A compact table shows the five largest absolute differences among publishable FDR-significant states. This is disclosed as a descriptive display rule, not a causal, practical-importance, or overall state ranking. The complete 208-row aggregate appendix accompanies the report.

Suppressed public rows retain only flags, reasons, and denominator metadata. Their estimates, intervals, and probabilities remain blank. Report text is template-generated from validated records; generative AI does not author or embellish findings.

## Reproducibility and release gate

Every artifact is generated twice and compared byte-for-byte. CSV scalar formatting and line endings are controlled by the standard-library writer rather than pandas' version-dependent defaults. Floating-point appendix values use a canonical 15-significant-digit representation, which removes parser-level last-bit differences while retaining substantially more precision than the displayed report. The manifest records SHA-256 hashes for both source snapshots and all report artifacts. The manual workflow retains the review package for seven days and has no cloud credentials or publication step.

Publication is a separate decision after reviewing the real artifact. A future publication mechanism must preserve the reviewed bytes, keep versioned provenance, and receive explicit authorization.
