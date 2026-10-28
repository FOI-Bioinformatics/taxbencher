"""Unit tests for bin/summarise_benchmark.py (cross-sample aggregation)."""

import pandas as pd
import pytest


def make_wide(sample, scale=1.0):
    rows = []
    for tool, f1, l1 in (("kraken2", 0.8, 0.4), ("metaphlan", 0.6, 0.8), ("Gold standard", 1.0, 0.0)):
        for rank in ("genus", "species"):
            rows.append({"sample": sample, "tool": tool, "rank": rank,
                         "F1 score": f1 * scale, "L1 norm error": l1 * scale,
                         "Completeness": f1 * scale, "Purity": 1.0})
    return pd.DataFrame(rows)


@pytest.fixture
def wide_files(tmp_path):
    files = []
    for sample, scale in (("s1", 1.0), ("s2", 0.5)):
        f = tmp_path / f"{sample}_metrics_wide.tsv"
        make_wide(sample, scale).to_csv(f, sep="\t", index=False)
        files.append(f)
    return files


def test_summary_excludes_gold_standard_and_aggregates(summariser, wide_files):
    data = summariser.load_metrics(wide_files)
    assert "Gold standard" not in set(data["tool"])
    summary = summariser.summarise(data)
    row = summary[(summary.classifier == "kraken2") & (summary["rank"] == "species") & (summary.metric == "F1 score")].iloc[0]
    assert row["n_samples"] == 2
    assert row["mean"] == pytest.approx(0.6)       # (0.8 + 0.4) / 2
    assert row["min"] == pytest.approx(0.4) and row["max"] == pytest.approx(0.8)
    assert row["sd"] == pytest.approx(pd.Series([0.8, 0.4]).std())


def test_ranking_is_direction_aware(summariser, wide_files):
    summary = summariser.summarise(summariser.load_metrics(wide_files))
    ranking = summariser.rank_classifiers(summary, "species")
    f1 = ranking[ranking.metric == "F1 score"].set_index("classifier")["rank_position"]
    l1 = ranking[ranking.metric == "L1 norm error"].set_index("classifier")["rank_position"]
    assert f1["kraken2"] == 1 and f1["metaphlan"] == 2          # higher F1 is better
    assert l1["kraken2"] == 1 and l1["metaphlan"] == 2          # lower L1 is better
    overall = ranking[ranking.metric == "Overall (mean rank)"].set_index("classifier")
    assert overall.loc["kraken2", "rank_position"] == 1


def test_sample_derived_from_filename_when_column_missing(summariser, tmp_path):
    df = make_wide("ignored").drop(columns="sample")
    f = tmp_path / "mysample_metrics_wide.tsv"
    df.to_csv(f, sep="\t", index=False)
    data = summariser.load_metrics([f])
    assert set(data["sample"]) == {"mysample"}


def test_mqc_outputs(summariser, wide_files, tmp_path):
    summary = summariser.summarise(summariser.load_metrics(wide_files))
    table = tmp_path / "t_mqc.tsv"
    line = tmp_path / "f1_mqc.tsv"
    summariser.write_mqc_table(summary, "species", table)
    summariser.write_mqc_linegraph(summary, "F1 score", "x", "F1", "F1", line)
    tl = [l for l in table.read_text().splitlines() if not l.startswith("#")]
    assert tl[0].split("\t")[:3] == ["Classifier", "Rank", "n_samples"]
    assert len(tl) == 3  # header + 2 classifiers
    ll = [l for l in line.read_text().splitlines() if not l.startswith("#")]
    assert ll[0] == "Classifier\tgenus\tspecies"
    assert "# plot_type: 'linegraph'" in line.read_text()


def test_empty_input_produces_headers_only(summariser, tmp_path):
    f = tmp_path / "empty_metrics_wide.tsv"
    f.write_text("sample\ttool\trank\n")
    data = summariser.load_metrics([f])
    assert data.empty
