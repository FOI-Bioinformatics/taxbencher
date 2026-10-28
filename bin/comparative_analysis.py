#!/usr/bin/env python3
"""
Comparative analysis of taxonomic classifiers within one biological sample.

Inputs are the OPAL results directory for the sample (``results.tsv`` in OPAL's
long format: tool, rank, metric, sample, value), the gold standard and,
optionally, the CAMI profiles of the evaluated classifiers.

Outputs (``<prefix>_...``):
  * ``_metrics_wide.tsv``      OPAL metrics pivoted to one row per tool and rank
  * ``_pca.html``              PCA of tools on their OPAL metric profile (all ranks)
  * ``_diff_taxa.tsv``         per taxon comparison of each classifier against the
                               gold standard (observed vs expected abundance,
                               absolute and log2 difference, TP/FP/FN status)
  * ``_comparison.html``       HTML report with per-rank metric plots and tables
  * ``_opal_summary_mqc.tsv``  MultiQC custom-content table (one row per tool)

No p-values are reported: a single profile per classifier offers no replication
for a statistical test; differences are descriptive.

Author: Andreas Sjödin (with Claude Code assistance)
"""

import argparse
import math
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional

warnings.filterwarnings("ignore")

try:
    import numpy as np
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    FULL_ANALYSIS = True
except ImportError as exc:  # pragma: no cover - depends on environment
    print(f"[comparative_analysis.py] WARNING: Missing dependencies: {exc}", file=sys.stderr)
    print("[comparative_analysis.py] Falling back to placeholder mode", file=sys.stderr)
    FULL_ANALYSIS = False

__version__ = "2.0.0"

GOLD_STANDARD_LABEL = "Gold standard"
RANK_ORDER = ["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"]
# Metrics shown in the MultiQC table and the report (OPAL naming)
SUMMARY_METRICS = [
    "Completeness", "Purity", "F1 score", "L1 norm error", "Bray-Curtis distance",
    "Weighted UniFrac error", "Unweighted UniFrac error", "Jaccard index",
    "Shannon diversity", "True positives", "False positives", "False negatives", "Taxon counts",
]
# Metrics where lower is better (used for colouring hints only)
LOWER_IS_BETTER = {"L1 norm error", "Bray-Curtis distance", "Weighted UniFrac error",
                   "Unweighted UniFrac error", "False positives", "False negatives"}


def log(msg: str) -> None:
    print(f"[comparative_analysis.py] {msg}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Comparative analysis of taxonomic classifiers (per sample)")
    parser.add_argument("--opal-dir", type=Path, required=True, help="OPAL results directory (contains results.tsv)")
    parser.add_argument("--gold-standard", type=Path, required=True, help="Gold standard bioboxes file")
    parser.add_argument("--sample-id", type=str, required=True, help="Sample ID (matches @SampleID)")
    parser.add_argument("--labels", type=str, required=True, help="Comma-separated classifier labels")
    parser.add_argument("--bioboxes", type=Path, nargs="*", default=[],
                        help="CAMI profiles of the classifiers, in the same order as --labels")
    parser.add_argument("--output-prefix", type=str, required=True, help="Output file prefix")
    parser.add_argument("--summary-rank", type=str, default="species",
                        help="Rank used for the MultiQC summary table (default: species)")
    parser.add_argument("--diff-min-abs", type=float, default=0.0,
                        help="Only report taxa whose |observed - expected| exceeds this many percent (default: 0)")
    parser.add_argument("--version", action="version", version=f"comparative_analysis.py {__version__}")
    return parser.parse_args()


# --------------------------------------------------------------------------------------
# OPAL metrics
# --------------------------------------------------------------------------------------
def parse_opal_metrics(opal_dir: Path, sample_id: str) -> Optional["pd.DataFrame"]:
    """Read OPAL results.tsv (long format) and return it filtered to this sample."""
    results = opal_dir / "results.tsv"
    if not results.exists():
        candidates = sorted(opal_dir.glob("*.tsv"))
        if not candidates:
            log(f"WARNING: no results.tsv in {opal_dir}")
            return None
        results = candidates[0]
    try:
        df = pd.read_csv(results, sep="\t")
    except Exception as exc:
        log(f"ERROR parsing {results}: {exc}")
        return None
    expected = {"tool", "rank", "metric", "value"}
    if not expected.issubset(df.columns):
        log(f"WARNING: {results} does not look like OPAL output (columns: {list(df.columns)})")
        return None
    if "sample" in df.columns and sample_id in set(df["sample"].astype(str)):
        df = df[df["sample"].astype(str) == sample_id]
    df = df.dropna(subset=["value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    # OPAL reports rank-independent metrics (UniFrac) with rank "na"
    df["rank"] = df["rank"].fillna("na").astype(str).replace({"nan": "na", "": "na"})
    log(f"Loaded {len(df)} OPAL metric values for {df['tool'].nunique()} tools "
        f"and {df['rank'].nunique()} ranks from {results.name}")
    return df


def pivot_metrics(long_df: "pd.DataFrame") -> "pd.DataFrame":
    """Long OPAL table -> one row per (tool, rank), one column per metric."""
    ranked = long_df[long_df["rank"] != "na"]
    wide = ranked.pivot_table(index=["tool", "rank"], columns="metric", values="value", aggfunc="first").reset_index()
    sample_level = long_df[long_df["rank"] == "na"]
    if not sample_level.empty:
        # broadcast rank-independent metrics (e.g. UniFrac) to every rank row of the tool
        per_tool = sample_level.pivot_table(index="tool", columns="metric", values="value", aggfunc="first").reset_index()
        wide = wide.merge(per_tool, on="tool", how="left", suffixes=("", "_sample"))
    wide["rank_order"] = wide["rank"].map({r: i for i, r in enumerate(RANK_ORDER)}).fillna(len(RANK_ORDER))
    wide = wide.sort_values(["tool", "rank_order"]).drop(columns="rank_order")
    wide.columns.name = None
    return wide


# --------------------------------------------------------------------------------------
# PCA
# --------------------------------------------------------------------------------------
def perform_pca_analysis(long_df: "pd.DataFrame", sample_id: str, output_file: Path) -> None:
    """PCA of tools (incl. gold standard as reference) on their metric-by-rank profile."""
    log("Performing PCA analysis...")
    informative = long_df[long_df["metric"].isin(SUMMARY_METRICS)]
    if informative.empty:
        informative = long_df
    features = informative.pivot_table(index="tool", columns=["metric", "rank"], values="value", aggfunc="first")
    features = features.loc[:, ~features.isna().all(axis=0)]
    features = features.dropna(axis=1, how="any")
    # drop constant columns (StandardScaler would produce NaN)
    features = features.loc[:, features.std(axis=0) > 0]

    if features.shape[0] < 2 or features.shape[1] < 2:
        log(f"WARNING: not enough data for PCA (tools={features.shape[0]}, features={features.shape[1]})")
        create_placeholder_pca(sample_id, list(features.index), output_file,
                               reason="PCA needs at least two tools and two informative, non-constant metrics.")
        return

    scaled = StandardScaler().fit_transform(features.values)
    n_components = min(2, features.shape[0] - 1, features.shape[1])
    pca = PCA(n_components=n_components)
    coords = pca.fit_transform(scaled)
    explained = pca.explained_variance_ratio_

    tools = list(features.index)
    is_gs = [t == GOLD_STANDARD_LABEL for t in tools]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=coords[:, 0],
        y=coords[:, 1] if n_components > 1 else [0] * len(tools),
        mode="markers+text",
        text=tools,
        textposition="top center",
        marker=dict(size=[18 if g else 14 for g in is_gs],
                    symbol=["star" if g else "circle" for g in is_gs],
                    color=["#d62728" if g else "#1f77b4" for g in is_gs]),
        hovertemplate="<b>%{text}</b><br>PC1: %{x:.3f}<br>PC2: %{y:.3f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Classifier performance PCA - {sample_id}<br><sup>{features.shape[1]} OPAL metric/rank features; "
              f"star = gold standard (perfect scores)</sup>",
        xaxis_title=f"PC1 ({explained[0]:.1%} variance)",
        yaxis_title=f"PC2 ({explained[1]:.1%} variance)" if n_components > 1 else "",
        template="plotly_white", width=850, height=620, hovermode="closest",
    )
    fig.write_html(output_file, include_plotlyjs="cdn")
    log(f"Created PCA plot: {output_file} (explained variance {np.round(explained, 3)})")


def create_placeholder_pca(sample_id: str, labels: List[str], output_file: Path, reason: str = "") -> None:
    with open(output_file, "w") as handle:
        handle.write(f"""<!DOCTYPE html>
<html><head><title>PCA Analysis - {sample_id}</title>
<style>body {{ font-family: Arial, sans-serif; margin: 40px; }} .warning {{ background:#fff3cd; padding:15px; border-radius:5px; }}</style>
</head><body>
<h1>Classifier Performance PCA - {sample_id}</h1>
<p>Classifiers analyzed: {', '.join(labels) if labels else 'n/a'}</p>
<div class="warning"><p><strong>Note:</strong> PCA could not be computed. {reason}</p></div>
</body></html>
""")


# --------------------------------------------------------------------------------------
# Profiles / differential taxa
# --------------------------------------------------------------------------------------
def read_bioboxes(path: Path, sample_id: Optional[str] = None) -> "pd.DataFrame":
    """Parse a CAMI profile into a DataFrame (TAXID, RANK, TAXPATH, TAXPATHSN, PERCENTAGE).

    For multi-sample files only the block matching ``sample_id`` is returned.
    """
    rows = []
    columns: List[str] = []
    current_sample = None
    reading = False
    with open(path) as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("@@"):
                columns = [c.strip() for c in line[2:].split("\t")]
                continue
            if line.startswith("@"):
                key, _, value = line[1:].partition(":")
                if key.strip().lower() == "sampleid":
                    current_sample = value.strip()
                reading = False
                continue
            reading = True
            if sample_id is not None and current_sample is not None and current_sample != sample_id:
                continue
            fields = line.split("\t")
            if not columns or len(fields) < len(columns):
                continue
            rows.append(dict(zip(columns, fields)))
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["TAXID", "RANK", "TAXPATH", "TAXPATHSN", "PERCENTAGE"])
    df["PERCENTAGE"] = pd.to_numeric(df["PERCENTAGE"], errors="coerce").fillna(0.0)
    if "TAXPATHSN" not in df.columns:
        df["TAXPATHSN"] = ""
    df["TAXID"] = df["TAXID"].astype(str)
    df["name"] = df["TAXPATHSN"].astype(str).str.split("|").str[-1].fillna("")
    return df[["TAXID", "RANK", "PERCENTAGE", "name"]]


def perform_differential_abundance(gold_df: "pd.DataFrame", profiles: Dict[str, "pd.DataFrame"],
                                   output_file: Path, min_abs: float = 0.0) -> "pd.DataFrame":
    """Per-taxon comparison of each profile with the gold standard."""
    log("Comparing per-taxon abundances with the gold standard...")
    records = []
    for label, prof in profiles.items():
        merged = pd.merge(
            gold_df.rename(columns={"PERCENTAGE": "expected_pct", "name": "name_gs"}),
            prof.rename(columns={"PERCENTAGE": "observed_pct", "name": "name_obs"}),
            on=["TAXID", "RANK"], how="outer",
        )
        merged["expected_pct"] = merged["expected_pct"].fillna(0.0)
        merged["observed_pct"] = merged["observed_pct"].fillna(0.0)
        merged["name"] = merged["name_gs"].where(merged["name_gs"].notna() & (merged["name_gs"] != ""), merged["name_obs"])
        for _, row in merged.iterrows():
            obs, exp = float(row["observed_pct"]), float(row["expected_pct"])
            if obs <= 0 and exp <= 0:
                continue
            diff = obs - exp
            if abs(diff) < min_abs:
                continue
            if exp > 0 and obs > 0:
                status, log2fc = "TP", math.log2(obs / exp)
            elif exp > 0:
                status, log2fc = "FN", float("-inf")
            else:
                status, log2fc = "FP", float("inf")
            records.append({
                "classifier": label,
                "rank": row["RANK"],
                "taxid": row["TAXID"],
                "taxname": row["name"] if isinstance(row["name"], str) else "",
                "observed_pct": round(obs, 6),
                "expected_pct": round(exp, 6),
                "abs_diff_pct": round(diff, 6),
                "log2_ratio": log2fc if math.isfinite(log2fc) else ("+inf" if log2fc > 0 else "-inf"),
                "status": status,
            })
    diff_df = pd.DataFrame(records, columns=["classifier", "rank", "taxid", "taxname", "observed_pct",
                                             "expected_pct", "abs_diff_pct", "log2_ratio", "status"])
    if not diff_df.empty:
        diff_df["rank_order"] = diff_df["rank"].map({r: i for i, r in enumerate(RANK_ORDER)}).fillna(99)
        diff_df["abs_order"] = diff_df["abs_diff_pct"].abs()
        diff_df = diff_df.sort_values(["classifier", "rank_order", "abs_order"], ascending=[True, True, False])
        diff_df = diff_df.drop(columns=["rank_order", "abs_order"])
    diff_df.to_csv(output_file, sep="\t", index=False)
    log(f"Wrote {len(diff_df)} taxon comparisons to {output_file}")
    return diff_df


def create_placeholder_diff_taxa(output_file: Path, reason: str) -> None:
    with open(output_file, "w") as handle:
        handle.write("classifier\trank\ttaxid\ttaxname\tobserved_pct\texpected_pct\tabs_diff_pct\tlog2_ratio\tstatus\n")
        handle.write(f"# {reason}\n")


# --------------------------------------------------------------------------------------
# MultiQC custom content
# --------------------------------------------------------------------------------------
def write_multiqc_table(wide: Optional["pd.DataFrame"], sample_id: str, labels: List[str],
                        summary_rank: str, output_file: Path) -> None:
    header = [
        "# id: 'taxbencher_opal_summary'",
        "# section_name: 'OPAL summary'",
        f"# description: 'Key CAMI OPAL metrics per classifier at the {summary_rank} rank (one row per sample and classifier). "
        "Completeness = recall, Purity = precision; L1 norm error ranges 0-2; UniFrac and Bray-Curtis: lower is better.'",
        "# plot_type: 'table'",
        "# pconfig:",
        "#     id: 'taxbencher_opal_summary_table'",
        "#     namespace: 'taxbencher'",
    ]
    cols = ["Sample", "Classifier", "Rank"]
    metrics = [m for m in SUMMARY_METRICS if wide is not None and m in wide.columns]
    with open(output_file, "w") as handle:
        handle.write("\n".join(header) + "\n")
        handle.write("\t".join(cols + metrics) + "\n")
        if wide is None:
            return
        subset = wide[(wide["rank"] == summary_rank) & (wide["tool"] != GOLD_STANDARD_LABEL)]
        if subset.empty:
            # fall back to the deepest available rank
            available = [r for r in RANK_ORDER if r in set(wide["rank"])]
            if available:
                summary_rank = available[-1]
                subset = wide[(wide["rank"] == summary_rank) & (wide["tool"] != GOLD_STANDARD_LABEL)]
        for _, row in subset.iterrows():
            values = []
            for m in metrics:
                v = row[m]
                values.append("" if pd.isna(v) else f"{v:.6g}")
            handle.write("\t".join([f"{sample_id}|{row['tool']}", str(row["tool"]), str(row["rank"])] + values) + "\n")
    log(f"Wrote MultiQC table: {output_file}")


# --------------------------------------------------------------------------------------
# HTML report
# --------------------------------------------------------------------------------------
def create_comparison_report(sample_id: str, labels: List[str], wide: Optional["pd.DataFrame"],
                             diff_df: Optional["pd.DataFrame"], pca_file: Path, diff_file: Path,
                             output_file: Path) -> None:
    log("Creating comparison report...")
    figs_html: List[str] = []
    table_html = "<p><em>No OPAL metrics available.</em></p>"
    if wide is not None and not wide.empty:
        plot_metrics = [m for m in ["Completeness", "Purity", "F1 score", "L1 norm error",
                                    "Weighted UniFrac error", "Bray-Curtis distance"] if m in wide.columns]
        plot_df = wide[wide["tool"] != GOLD_STANDARD_LABEL].copy()
        plot_df["rank"] = pd.Categorical(plot_df["rank"], categories=[r for r in RANK_ORDER if r in set(plot_df["rank"])], ordered=True)
        plot_df = plot_df.sort_values("rank")
        for metric in plot_metrics:
            try:
                fig = px.bar(plot_df, x="rank", y=metric, color="tool", barmode="group",
                             title=f"{metric} by rank" + (" (lower is better)" if metric in LOWER_IS_BETTER else " (higher is better)"),
                             template="plotly_white")
                fig.update_layout(height=420)
                figs_html.append(fig.to_html(full_html=False, include_plotlyjs="cdn" if not figs_html else False))
            except Exception as exc:
                log(f"WARNING: could not plot {metric}: {exc}")
        show_cols = ["tool", "rank"] + [m for m in SUMMARY_METRICS if m in wide.columns]
        table_html = wide[show_cols].to_html(index=False, float_format=lambda v: f"{v:.4g}", classes="metrics", border=0)

    diff_html = "<p><em>Per-taxon comparison not available (no profiles were provided).</em></p>"
    if diff_df is not None and not diff_df.empty:
        counts = diff_df.groupby(["classifier", "rank", "status"]).size().unstack(fill_value=0)
        diff_html = (
            "<p>Number of taxa per classifier and rank that are shared with the gold standard (TP), "
            "predicted but absent from it (FP) or missed (FN):</p>"
            + counts.to_html(classes="metrics", border=0)
        )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Classifier Comparison - {sample_id}</title>
<style>
 body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
 .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
 h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
 h2 {{ color: #666; margin-top: 30px; }}
 .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
 .metric-card {{ background: #f9f9f9; padding: 12px; border-radius: 5px; border-left: 4px solid #4CAF50; }}
 table.metrics {{ border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 13px; }}
 table.metrics th, table.metrics td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #ddd; }}
 table.metrics th {{ background: #4CAF50; color: white; }}
 .plot-container {{ margin: 30px 0; }}
 .note {{ color: #666; font-size: 13px; }}
</style></head>
<body><div class="container">
<h1>Classifier Comparison Report - {sample_id}</h1>
<h2>Classifiers analysed ({len(labels)})</h2>
<div class="metric-grid">{''.join(f'<div class="metric-card"><strong>{label}</strong></div>' for label in labels)}</div>
<h2>Linked outputs</h2>
<ul>
 <li><strong>PCA:</strong> <a href="{pca_file.name}">{pca_file.name}</a></li>
 <li><strong>Per-taxon comparison:</strong> <a href="{diff_file.name}">{diff_file.name}</a></li>
</ul>
<h2>OPAL metrics by rank</h2>
{''.join(f'<div class="plot-container">{f}</div>' for f in figs_html) if figs_html else '<p><em>Visualisations require OPAL metrics</em></p>'}
<h2>Metrics table</h2>
{table_html}
<h2>Taxon-level agreement with the gold standard</h2>
{diff_html}
<p class="note">Metrics are computed by CAMI OPAL. Completeness = recall, Purity = precision, F1 = harmonic mean of both;
L1 norm error (0-2), Bray-Curtis (0-1) and UniFrac errors are distances where lower is better.
No significance testing is performed: one profile per classifier provides no replication.</p>
<hr><p style="text-align:center;color:#666;font-size:12px;">Generated by taxbencher comparative_analysis.py v{__version__}</p>
</div></body></html>
"""
    with open(output_file, "w") as handle:
        handle.write(html)
    log(f"Created comparison report: {output_file}")


# --------------------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    labels = [l.strip() for l in args.labels.split(",") if l.strip()]
    log(f"Sample ID: {args.sample_id} | labels: {labels} | OPAL dir: {args.opal_dir} | full analysis: {FULL_ANALYSIS}")

    pca_html = Path(f"{args.output_prefix}_pca.html")
    diff_tsv = Path(f"{args.output_prefix}_diff_taxa.tsv")
    comparison_html = Path(f"{args.output_prefix}_comparison.html")
    wide_tsv = Path(f"{args.output_prefix}_metrics_wide.tsv")
    mqc_tsv = Path(f"{args.output_prefix}_opal_summary_mqc.tsv")

    if not FULL_ANALYSIS:
        create_placeholder_pca(args.sample_id, labels, pca_html, "Python dependencies are missing.")
        create_placeholder_diff_taxa(diff_tsv, "analysis dependencies (pandas, scikit-learn, plotly) are missing")
        wide_tsv.write_text("tool\trank\n")
        write_multiqc_table(None, args.sample_id, labels, args.summary_rank, mqc_tsv)
        comparison_html.write_text(f"<html><body><h1>Classifier Comparison - {args.sample_id}</h1>"
                                   f"<p>Full analysis requires pandas, scikit-learn and plotly.</p></body></html>")
        log("SUCCESS (placeholder mode)")
        return

    long_df = parse_opal_metrics(args.opal_dir, args.sample_id)
    wide = None
    if long_df is not None and not long_df.empty:
        wide = pivot_metrics(long_df)
        wide.to_csv(wide_tsv, sep="\t", index=False)
        missing_labels = [l for l in labels if l not in set(wide["tool"])]
        if missing_labels:
            log(f"WARNING: labels without OPAL metrics: {missing_labels}")
        perform_pca_analysis(long_df, args.sample_id, pca_html)
    else:
        wide_tsv.write_text("tool\trank\n")
        create_placeholder_pca(args.sample_id, labels, pca_html, "OPAL metrics were not found.")

    diff_df = None
    if args.bioboxes:
        if len(args.bioboxes) != len(labels):
            log(f"WARNING: {len(args.bioboxes)} profiles for {len(labels)} labels; using file names as labels")
            profile_labels = [p.name.rsplit(".", 1)[0] for p in args.bioboxes]
        else:
            profile_labels = labels
        gold_df = read_bioboxes(args.gold_standard, args.sample_id)
        if gold_df.empty:
            log(f"WARNING: no entries for sample {args.sample_id} in gold standard; using whole file")
            gold_df = read_bioboxes(args.gold_standard)
        profiles = {}
        for label, path in zip(profile_labels, args.bioboxes):
            try:
                profiles[label] = read_bioboxes(path)
                log(f"Loaded profile {label}: {len(profiles[label])} taxa")
            except Exception as exc:
                log(f"WARNING: could not read {path}: {exc}")
        if profiles and not gold_df.empty:
            diff_df = perform_differential_abundance(gold_df, profiles, diff_tsv, args.diff_min_abs)
        else:
            create_placeholder_diff_taxa(diff_tsv, "gold standard or profiles could not be parsed")
    else:
        create_placeholder_diff_taxa(diff_tsv, "no classifier profiles were provided (--bioboxes)")

    write_multiqc_table(wide, args.sample_id, labels, args.summary_rank, mqc_tsv)
    create_comparison_report(args.sample_id, labels, wide, diff_df, pca_html, diff_tsv, comparison_html)

    for f in (pca_html, diff_tsv, comparison_html, wide_tsv, mqc_tsv):
        log(f"Created: {f}")
    log("SUCCESS")


if __name__ == "__main__":
    main()
