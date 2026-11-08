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
    tl = [row for row in table.read_text().splitlines() if not row.startswith("#")]
    assert tl[0].split("\t")[:3] == ["Classifier", "Rank", "n_samples"]
    assert len(tl) == 3  # header + 2 classifiers
    ll = [row for row in line.read_text().splitlines() if not row.startswith("#")]
    # MultiQC only uses the header row as x categories when its first cell is empty
    assert ll[0] == "\tgenus\tspecies"
    assert "# plot_type: 'linegraph'" in line.read_text()


def test_empty_input_produces_headers_only(summariser, tmp_path):
    f = tmp_path / "empty_metrics_wide.tsv"
    f.write_text("sample\ttool\trank\n")
    data = summariser.load_metrics([f])
    assert data.empty


def labelled_wide(sample, classifiers, values):
    """Wide table with schema-conformant unique labels (<sample>_<classifier>) and a classifier column."""
    rows = []
    for classifier, (f1, l1) in zip(classifiers, values):
        for rank in ("genus", "species"):
            rows.append({"sample": sample, "tool": f"{sample}_{classifier}", "classifier": classifier,
                         "rank": rank, "F1 score": f1, "L1 norm error": l1, "Completeness": f1, "Purity": 1.0})
    return pd.DataFrame(rows)


def test_samples_are_pooled_per_classifier_not_per_label(summariser, tmp_path):
    files = []
    for sample, vals in (("s1", [(0.8, 0.4), (0.6, 0.8)]), ("s2", [(0.4, 0.2), (0.2, 0.6)])):
        f = tmp_path / f"{sample}_metrics_wide.tsv"
        labelled_wide(sample, ["kraken2", "metaphlan"], vals).to_csv(f, sep="\t", index=False)
        files.append(f)
    summary = summariser.summarise(summariser.load_metrics(files))
    assert set(summary["classifier"]) == {"kraken2", "metaphlan"}
    row = summary[(summary.classifier == "kraken2") & (summary["rank"] == "species") & (summary.metric == "F1 score")].iloc[0]
    assert row["n_samples"] == 2 and row["mean"] == pytest.approx(0.6)


def test_repeated_classifier_within_a_sample_stays_separate(summariser, tmp_path):
    df = pd.concat([labelled_wide("s1", ["kraken2"], [(0.8, 0.4)]),
                    labelled_wide("s1", ["kraken2"], [(0.6, 0.8)]).assign(tool="s1_kraken2_db2")])
    f = tmp_path / "s1_metrics_wide.tsv"
    df.to_csv(f, sep="\t", index=False)
    summary = summariser.summarise(summariser.load_metrics([f]))
    assert set(summary["classifier"]) == {"s1_kraken2", "s1_kraken2_db2"}


def test_missing_opal_values_count_as_zero_f1_and_rank_last(summariser, tmp_path):
    # s1: 'empty' predicted nothing at species -> OPAL writes Completeness 0 but no F1/L1/Purity
    s1 = labelled_wide("s1", ["good", "empty"], [(0.6, 0.5), (0.9, 0.1)])
    mask = (s1.classifier == "empty") & (s1["rank"] == "species")
    s1.loc[mask, ["F1 score", "L1 norm error", "Purity"]] = float("nan")
    s1.loc[mask, "Completeness"] = 0.0
    s2 = labelled_wide("s2", ["good", "empty"], [(0.6, 0.5), (0.9, 0.1)])
    files = []
    for name, df in (("s1", s1), ("s2", s2)):
        f = tmp_path / f"{name}_metrics_wide.tsv"
        df.to_csv(f, sep="\t", index=False)
        files.append(f)
    summary = summariser.summarise(summariser.load_metrics(files))
    f1 = summary[(summary.classifier == "empty") & (summary["rank"] == "species") & (summary.metric == "F1 score")].iloc[0]
    assert f1["n_samples"] == 2 and f1["mean"] == pytest.approx(0.45)   # (0 + 0.9) / 2
    l1 = summary[(summary.classifier == "empty") & (summary["rank"] == "species") & (summary.metric == "L1 norm error")].iloc[0]
    assert l1["n_missing"] == 1
    ranking = summariser.rank_classifiers(summary, "species")
    l1_rank = ranking[ranking.metric == "L1 norm error"].set_index("classifier")["rank_position"]
    assert l1_rank["good"] == 1 and l1_rank["empty"] == 2    # lower mean, but missing in one sample


def test_ranking_falls_back_to_deepest_available_rank(summariser, tmp_path):
    df = labelled_wide("s1", ["kraken2", "metaphlan"], [(0.8, 0.4), (0.6, 0.8)])
    df = df[df["rank"] == "genus"]
    f = tmp_path / "s1_metrics_wide.tsv"
    df.to_csv(f, sep="\t", index=False)
    summary = summariser.summarise(summariser.load_metrics([f]))
    ranking = summariser.rank_classifiers(summary, "species")
    assert not ranking.empty and set(ranking["rank"]) == {"genus"}


def test_na_like_labels_are_kept(summariser, tmp_path):
    df = labelled_wide("s1", ["NA", "None"], [(0.8, 0.4), (0.6, 0.8)])
    f = tmp_path / "s1_metrics_wide.tsv"
    df.to_csv(f, sep="\t", index=False)
    data = summariser.load_metrics([f])
    assert set(data["classifier"]) == {"NA", "None"}
