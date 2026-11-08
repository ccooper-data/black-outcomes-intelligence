"""Build a deterministic, publication-ready report from public aggregate snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import numbers
from pathlib import Path

import pandas as pd

from src.ask_data import STATE_NAMES


METRICS = {
    "married_rate": ("Marriage rate", "percent"),
    "bachelors_plus_rate": ("Bachelor's-or-higher attainment", "percent"),
    "employment_rate": ("Employment rate", "percent"),
    "mean_personal_income": ("Mean personal income", "currency"),
}
REPORT_COLUMNS = [
    "state",
    "survey_year",
    "metric",
    "women_estimate",
    "men_estimate",
    "difference_estimate",
    "difference_ci95_lower",
    "difference_ci95_upper",
    "difference_q_value",
    "difference_log10_q_value",
    "difference_q_value_below_machine_precision",
    "difference_fdr_significant",
    "difference_is_suppressed",
    "difference_suppression_reason",
    "women_unweighted_n",
    "women_weighted_denominator",
    "men_unweighted_n",
    "men_weighted_denominator",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _csv_value(value: object) -> object:
    """Return a stable CSV scalar independent of pandas' float formatter."""
    if pd.isna(value):
        return ""
    if isinstance(value, (bool,)):
        return "True" if value else "False"
    if isinstance(value, numbers.Integral):
        return str(int(value))
    if isinstance(value, numbers.Real):
        # Fifteen significant digits collapse parser-level, last-bit variation
        # while retaining far more precision than any published display value.
        return format(float(value), ".15g")
    return str(value)


def write_deterministic_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write RFC-style CSV with Python-controlled scalar formatting and newlines."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(frame.columns)
        for row in frame.itertuples(index=False, name=None):
            writer.writerow([_csv_value(value) for value in row])


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().map({"true": True, "false": False})


def validate_inference(frame: pd.DataFrame, manifest: dict) -> None:
    required = set(REPORT_COLUMNS) | {"comparison", "method"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Inference snapshot is missing columns: {sorted(missing)}")
    if len(frame) != 208 or set(frame["survey_year"]) != {2024}:
        raise ValueError("Expected exactly 208 inference rows for survey year 2024")
    if frame.duplicated(["state", "metric"]).any():
        raise ValueError("Inference state-metric grain is not unique")
    if set(frame["metric"]) != set(METRICS):
        raise ValueError("Inference metrics do not match the Phase 8 report contract")
    if manifest.get("causal_interpretation") is not False:
        raise ValueError("The source manifest must explicitly prohibit causal interpretation")
    if manifest.get("rows") != len(frame):
        raise ValueError("The source manifest row count does not match inference.csv")


def _format_value(value: float, style: str, *, signed: bool = False) -> str:
    if pd.isna(value):
        return "Suppressed"
    if style == "percent":
        return f"{value:+.1%}" if signed else f"{value:.1%}"
    if signed:
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.0f}"
    return f"${value:,.0f}"


def _format_q(row: pd.Series) -> str:
    if bool(row["difference_q_value_below_machine_precision"]):
        return f"below machine precision (log10(q)={row['difference_log10_q_value']:.3f})"
    return f"{row['difference_q_value']:.3g}"


def _national_table(frame: pd.DataFrame) -> list[str]:
    lines = [
        "| Outcome | Black women | Black men | Women minus men (95% CI) | Multiplicity-adjusted evidence |",
        "|---|---:|---:|---:|---|",
    ]
    national = frame[frame["state"].isna()].set_index("metric")
    for metric, (label, style) in METRICS.items():
        row = national.loc[metric]
        difference = _format_value(row["difference_estimate"], style, signed=True)
        lower = _format_value(row["difference_ci95_lower"], style, signed=True)
        upper = _format_value(row["difference_ci95_upper"], style, signed=True)
        lines.append(
            f"| {label} | {_format_value(row['women_estimate'], style)} | "
            f"{_format_value(row['men_estimate'], style)} | {difference} ({lower} to {upper}) | "
            f"q={_format_q(row)} |"
        )
    return lines


def _state_sections(frame: pd.DataFrame) -> list[str]:
    lines: list[str] = []
    states = frame[frame["state"].notna()].copy()
    states["difference_is_suppressed"] = _bool_series(states["difference_is_suppressed"])
    states["difference_fdr_significant"] = _bool_series(states["difference_fdr_significant"])
    for metric, (label, style) in METRICS.items():
        subset = states[states["metric"] == metric]
        visible = subset[~subset["difference_is_suppressed"]]
        significant = visible[visible["difference_fdr_significant"]]
        suppressed = int(subset["difference_is_suppressed"].sum())
        lines.extend(
            [
                f"### {label}",
                "",
                f"{len(significant)} of {len(visible)} publishable state comparisons meet the "
                f"within-outcome 5% Benjamini–Hochberg FDR rule; {suppressed} are suppressed.",
                "",
            ]
        )
        if significant.empty:
            lines.extend(["No state comparison meets the stated FDR rule.", ""])
            continue
        selected = significant.assign(
            absolute_difference=significant["difference_estimate"].abs()
        ).sort_values(["absolute_difference", "state_name"], ascending=[False, True]).head(5)
        lines.extend(
            [
                "Largest five absolute publishable differences among FDR-significant states "
                "(a transparent descriptive ranking, not an importance or causal ranking):",
                "",
                "| State | Difference | 95% CI | q-value |",
                "|---|---:|---:|---:|",
            ]
        )
        for _, row in selected.iterrows():
            lines.append(
                f"| {row['state_name']} | {_format_value(row['difference_estimate'], style, signed=True)} | "
                f"{_format_value(row['difference_ci95_lower'], style, signed=True)} to "
                f"{_format_value(row['difference_ci95_upper'], style, signed=True)} | "
                f"{_format_q(row)} |"
            )
        lines.append("")
    return lines


def build_markdown(frame: pd.DataFrame, source_hashes: dict[str, str]) -> str:
    visible = (~_bool_series(frame["difference_is_suppressed"])).sum()
    suppressed = _bool_series(frame["difference_is_suppressed"]).sum()
    lines = [
        "# Black Outcomes Intelligence: 2024 Research Findings",
        "",
        "**Release:** Phase 8 research report  ",
        "**Population:** Black-alone adults age 18+ in the 2024 ACS 1-year PUMS  ",
        "**Comparison:** Age-adjusted Black women minus Black men",
        "",
        "## Executive summary",
        "",
        "This report describes age-adjusted differences in marriage, bachelor's-or-higher attainment, "
        "employment, and mean personal income. It reports sampling uncertainty and multiplicity-adjusted "
        "evidence; it does not identify causes or predict individual outcomes.",
        "",
        f"The validated inference snapshot contains {len(frame)} comparisons: {visible} publishable and "
        f"{suppressed} suppressed under the project's transparent stability rules.",
        "",
        "## National findings",
        "",
        *_national_table(frame),
        "",
        "Differences are descriptive population estimates. Statistical distinguishability does not imply "
        "practical importance, fairness, mechanism, or causation.",
        "",
        "## State findings",
        "",
        "State tests are adjusted separately within each outcome across 51 comparisons. The complete "
        "machine-readable appendix accompanies this report so the selected summaries can be audited.",
        "",
        *_state_sections(frame),
        "## Methods and limitations",
        "",
        "- Estimates use ACS person weights and all 80 person replicate weights with the Census SDR factor 4/80.",
        "- Direct age standardization uses the common 2024 national Black-adult age distribution across six age bands.",
        "- Women-minus-men differences and uncertainty are recomputed from paired replicate estimates.",
        "- State p-values use Benjamini–Hochberg FDR adjustment within each outcome; national q-values equal p-values.",
        "- Cells are suppressed when component stability, sample-size, denominator, or finite-uncertainty rules fail.",
        "- ACS PUMS is cross-sectional observational data. Results are associations, not causal effects.",
        "- Race, sex, income, employment, education, and marital-status variables follow the source-data definitions and do not capture every relevant identity or structural factor.",
        "- Cross-year change is not tested here because the available design does not provide cross-year covariance.",
        "",
        "## Provenance",
        "",
        "This report was generated deterministically from the repository's public aggregate inference snapshot. "
        "No Census microdata, suppressed estimates, person-level predictions, or generative-AI-written findings "
        "are included.",
        "",
        f"- `inference.csv` SHA-256: `{source_hashes['inference.csv']}`",
        f"- `inference_manifest.json` SHA-256: `{source_hashes['inference_manifest.json']}`",
        "",
    ]
    return "\n".join(lines)


def markdown_to_html(markdown: str) -> str:
    """Render a dependency-free, accessible HTML document from controlled Markdown."""
    output = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
        "<title>Black Outcomes Intelligence: 2024 Research Findings</title>",
        "<style>body{font:16px/1.55 system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17202a}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0 2rem}th,td{border:1px solid #bbb;padding:.55rem;text-align:left}"
        "th{background:#f2f4f4}code{overflow-wrap:anywhere}h1,h2,h3{line-height:1.2}</style></head><body>",
    ]
    in_list = False
    in_table = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("|---"):
            continue
        if line.startswith("|"):
            cells = [html.escape(cell.strip()) for cell in line.strip("|").split("|")]
            if not in_table:
                output.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr></thead><tbody>")
                in_table = True
            else:
                output.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            output.append("</tbody></table>")
            in_table = False
        if line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{html.escape(line[2:])}</li>")
            continue
        if in_list:
            output.append("</ul>")
            in_list = False
        if not line:
            continue
        if line.startswith("### "):
            output.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            output.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            output.append(f"<h1>{html.escape(line[2:])}</h1>")
        else:
            output.append(f"<p>{html.escape(line).replace('  ', '<br>')}</p>")
    if in_table:
        output.append("</tbody></table>")
    if in_list:
        output.append("</ul>")
    output.append("</body></html>")
    return "\n".join(output)


def build_report(inference_path: Path, manifest_path: Path, output_dir: Path) -> dict:
    frame = pd.read_csv(inference_path)
    manifest = json.loads(manifest_path.read_text())
    validate_inference(frame, manifest)
    frame["state_name"] = frame["state"].map(STATE_NAMES).fillna("National")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hashes = {
        inference_path.name: sha256(inference_path),
        manifest_path.name: sha256(manifest_path),
    }
    appendix = frame[["state_name", *REPORT_COLUMNS]].sort_values(
        ["metric", "state_name"]
    ).reset_index(drop=True)
    appendix_path = output_dir / "research_findings_appendix.csv"
    write_deterministic_csv(appendix, appendix_path)
    markdown = build_markdown(frame, source_hashes)
    markdown_path = output_dir / "research_findings.md"
    markdown_path.write_text(markdown)
    html_path = output_dir / "research_findings.html"
    html_path.write_text(markdown_to_html(markdown))
    report_manifest = {
        "phase": 8,
        "survey_year": 2024,
        "causal_interpretation": False,
        "source_hashes": source_hashes,
        "rows": len(frame),
        "publishable_rows": int((~_bool_series(frame["difference_is_suppressed"])).sum()),
        "suppressed_rows": int(_bool_series(frame["difference_is_suppressed"]).sum()),
        "artifacts": {
            path.name: sha256(path) for path in [markdown_path, html_path, appendix_path]
        },
    }
    (output_dir / "research_findings_manifest.json").write_text(
        json.dumps(report_manifest, indent=2, sort_keys=True) + "\n"
    )
    return report_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inference", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build_report(args.inference, args.manifest, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
