#!/usr/bin/env python3
"""
Cross-sample benchmark summary.

Aggregates the per-sample wide OPAL metric tables written by comparative_analysis.py
(``<sample>_metrics_wide.tsv``: sample, tool, rank, one column per metric) over all
samples of a run and produces:

  * ``<prefix>_summary.tsv``        per classifier, rank and metric: n_samples, mean, median, sd, min, max
  * ``<prefix>_ranking.tsv``        per metric at the summary rank: mean value, rank of each classifier
                                    (1 = best, direction-aware) and an overall mean rank
  * ``<prefix>_table_mqc.tsv``      MultiQC table: mean of the key metrics per classifier at the summary rank
  * ``<prefix>_f1_by_rank_mqc.tsv`` MultiQC line graph: mean F1 score per classifier across ranks
  * ``<prefix>_l1_by_rank_mqc.tsv`` MultiQC line graph: mean L1 norm error per classifier across ranks

The gold standard pseudo-tool is excluded. With a single sample the summary equals that
sample's values (sd is empty).

Author: taxbencher pipeline
"""

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

__version__ = "1.0.0"

GOLD_STANDARD_LABEL = "Gold standard"
RANK_ORDER = ["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"]
KEY_METRICS = ["Completeness", "Purity", "F1 score", "L1 norm error", "Bray-Curtis distance",
               "Weighted UniFrac error", "Unweighted UniFrac error", "Jaccard index",
               "True positives", "False positives", "False negatives", "Taxon counts"]
LOWER_IS_BETTER = {"L1 norm error", "Bray-Curtis distance", "Weighted UniFrac error",
                   "Unweighted UniFrac error", "False positives", "False negatives"}
RANKED_METRICS = ["Completeness", "Purity", "F1 score", "L1 norm error", "Bray-Curtis distance",
                  "Weighted UniFrac error", "Jaccard index"]


def log(msg: str) -> None:
    print(f"[summarise_benchmark.py] {msg}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarise OPAL metrics across samples")
    parser.add_argument("--metrics", type=Path, nargs="+", required=True,
                        help="Per-sample *_metrics_wide.tsv files from comparative_analysis.py")
    parser.add_argument("--output-prefix", type=str, default="benchmark", help="Output file prefix")
    parser.add_argument("--summary-rank", type=str, default="species",
                        help="Rank used for the ranking and the MultiQC table (default: species)")
    parser.add_argument("--version", action="version", version=f"summarise_benchmark.py {__version__}")
    return parser.parse_args()


def load_metrics(files: List[Path]) -> pd.DataFrame:
    frames = []
    for path in files:
        try:
            df = pd.read_csv(path, sep="\t")
        except Exception as exc:
            log(f"WARNING: could not read {path}: {exc}")
            continue
        if df.empty or not {"tool", "rank"}.issubset(df.columns):
            log(f"WARNING: {path} has no metrics; skipped")
            continue
        if "sample" not in df.columns:
            df.insert(0, "sample", path.name.replace("_metrics_wide.tsv", ""))
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["sample", "tool", "rank"])
    data = pd.concat(frames, ignore_index=True)
    data = data[data["tool"] != GOLD_STANDARD_LABEL]
    return data


def summarise(data: pd.DataFrame) -> pd.DataFrame:
    metric_cols = [c for c in data.columns if c not in ("sample", "tool", "rank")
                   and pd.api.types.is_numeric_dtype(data[c])]
    long = data.melt(id_vars=["sample", "tool", "rank"], value_vars=metric_cols,
                     var_name="metric", value_name="value").dropna(subset=["value"])
    grouped = long.groupby(["tool", "rank", "metric"])["value"]
    summary = grouped.agg(n_samples="count", mean="mean", median="median", sd="std", min="min", max="max").reset_index()
    summary["rank_order"] = summary["rank"].map({r: i for i, r in enumerate(RANK_ORDER)}).fillna(len(RANK_ORDER))
    summary = summary.sort_values(["metric", "rank_order", "tool"]).drop(columns="rank_order")
    summary = summary.rename(columns={"tool": "classifier"})
    return summary


def rank_classifiers(summary: pd.DataFrame, summary_rank: str) -> pd.DataFrame:
    subset = summary[(summary["rank"] == summary_rank) & (summary["metric"].isin(RANKED_METRICS))]
    if subset.empty:
        return pd.DataFrame(columns=["classifier", "metric", "mean", "rank_position", "direction"])
    rows = []
    for metric, grp in subset.groupby("metric"):
        ascending = metric in LOWER_IS_BETTER
        ordered = grp.sort_values("mean", ascending=ascending).reset_index(drop=True)
        ordered["rank_position"] = ordered["mean"].rank(method="min", ascending=ascending).astype(int)
        for _, r in ordered.iterrows():
            rows.append({"classifier": r["classifier"], "metric": metric, "mean": r["mean"],
                         "rank_position": r["rank_position"],
                         "direction": "lower is better" if ascending else "higher is better"})
    ranking = pd.DataFrame(rows)
    overall = ranking.groupby("classifier")["rank_position"].mean().rename("mean").reset_index()
    overall["metric"] = "Overall (mean rank)"
    overall["rank_position"] = overall["mean"].rank(method="min").astype(int)
    overall["direction"] = "lower is better"
    ranking = pd.concat([ranking, overall[ranking.columns]], ignore_index=True)
    return ranking.sort_values(["metric", "rank_position", "classifier"])


def write_mqc_table(summary: pd.DataFrame, summary_rank: str, output: Path) -> None:
    subset = summary[summary["rank"] == summary_rank]
    if subset.empty:
        available = [r for r in RANK_ORDER if r in set(summary["rank"])]
        if available:
            summary_rank = available[-1]
            subset = summary[summary["rank"] == summary_rank]
    metrics = [m for m in KEY_METRICS if m in set(subset["metric"])]
    wide = subset.pivot_table(index="classifier", columns="metric", values="mean", aggfunc="first")
    n = subset.groupby("classifier")["n_samples"].max()
    header = [
        "# id: 'taxbencher_benchmark_summary'",
        "# section_name: 'Benchmark summary across samples'",
        f"# description: 'Mean CAMI OPAL metrics per classifier over all samples at the {summary_rank} rank "
        "(n_samples = samples contributing). Completeness = recall, Purity = precision; L1 norm error, "
        "Bray-Curtis and UniFrac: lower is better.'",
        "# plot_type: 'table'",
        "# pconfig:",
        "#     id: 'taxbencher_benchmark_summary_table'",
        "#     namespace: 'taxbencher'",
    ]
    with open(output, "w") as handle:
        handle.write("\n".join(header) + "\n")
        handle.write("\t".join(["Classifier", "Rank", "n_samples"] + metrics) + "\n")
        for classifier in wide.index:
            vals = ["" if pd.isna(wide.loc[classifier, m]) else f"{wide.loc[classifier, m]:.6g}" for m in metrics]
            handle.write("\t".join([classifier, summary_rank, str(int(n.get(classifier, 0)))] + vals) + "\n")


def write_mqc_linegraph(summary: pd.DataFrame, metric: str, section_id: str, title: str, ylab: str, output: Path) -> None:
    subset = summary[summary["metric"] == metric]
    ranks = [r for r in RANK_ORDER if r in set(subset["rank"])]
    header = [
        f"# id: '{section_id}'",
        f"# section_name: '{title}'",
        f"# description: 'Mean {metric} per classifier at each taxonomic rank, averaged over samples.'",
        "# plot_type: 'linegraph'",
        "# pconfig:",
        f"#     id: '{section_id}_plot'",
        f"#     title: 'taxbencher: {title}'",
        f"#     ylab: '{ylab}'",
        "#     xlab: 'Taxonomic rank'",
        "#     categories: true",
    ]
    with open(output, "w") as handle:
        handle.write("\n".join(header) + "\n")
        if not ranks:
            handle.write("Classifier\n")
            return
        handle.write("\t".join(["Classifier"] + ranks) + "\n")
        wide = subset.pivot_table(index="classifier", columns="rank", values="mean", aggfunc="first")
        for classifier in wide.index:
            vals = ["" if r not in wide.columns or pd.isna(wide.loc[classifier, r]) else f"{wide.loc[classifier, r]:.6g}" for r in ranks]
            handle.write("\t".join([classifier] + vals) + "\n")


def main() -> None:
    args = parse_args()
    data = load_metrics(args.metrics)
    prefix = args.output_prefix
    summary_tsv = Path(f"{prefix}_summary.tsv")
    ranking_tsv = Path(f"{prefix}_ranking.tsv")
    table_mqc = Path(f"{prefix}_table_mqc.tsv")
    f1_mqc = Path(f"{prefix}_f1_by_rank_mqc.tsv")
    l1_mqc = Path(f"{prefix}_l1_by_rank_mqc.tsv")

    if data.empty:
        log("WARNING: no metrics to summarise")
        summary = pd.DataFrame(columns=["classifier", "rank", "metric", "n_samples", "mean", "median", "sd", "min", "max"])
    else:
        log(f"Loaded metrics for {data['sample'].nunique()} sample(s), {data['tool'].nunique()} classifier(s)")
        summary = summarise(data)

    summary.to_csv(summary_tsv, sep="\t", index=False, float_format="%.6g")
    ranking = rank_classifiers(summary, args.summary_rank)
    ranking.to_csv(ranking_tsv, sep="\t", index=False, float_format="%.6g")
    write_mqc_table(summary, args.summary_rank, table_mqc)
    write_mqc_linegraph(summary, "F1 score", "taxbencher_f1_by_rank", "F1 score by rank", "F1 score", f1_mqc)
    write_mqc_linegraph(summary, "L1 norm error", "taxbencher_l1_by_rank", "L1 norm error by rank", "L1 norm error", l1_mqc)
    for f in (summary_tsv, ranking_tsv, table_mqc, f1_mqc, l1_mqc):
        log(f"Created: {f}")
    if not ranking.empty:
        best = ranking[ranking["metric"] == "Overall (mean rank)"].iloc[0]
        log(f"Best overall classifier at {args.summary_rank}: {best['classifier']} (mean rank {best['mean']:.2f})")
    log("SUCCESS")


if __name__ == "__main__":
    main()
