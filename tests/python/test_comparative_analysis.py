"""Unit tests for bin/comparative_analysis.py (per-sample classifier comparison)."""

import pandas as pd

OPAL_RESULTS = """tool\trank\tmetric\tsample\tvalue
Gold standard\tspecies\tF1 score\ts1\t1.0
Gold standard\tspecies\tCompleteness\ts1\t1.0
NA\tspecies\tF1 score\ts1\t0.5
NA\tspecies\tCompleteness\ts1\t0.6
NA\tna\tWeighted UniFrac error\ts1\t1.2
k2_std\tgenus\tF1 score\ts1\t0.9
k2_std\tspecies\tF1 score\ts1\t0.7
k2_std\tspecies\tCompleteness\ts1\t
k2_std\tna\tWeighted UniFrac error\ts1\t0.8
"""


def write_opal(tmp_path):
    opal = tmp_path / "opal"
    opal.mkdir()
    (opal / "results.tsv").write_text(OPAL_RESULTS)
    return opal


def test_parse_keeps_na_labels_and_drops_empty_values(comparer, tmp_path):
    long_df = comparer.parse_opal_metrics(write_opal(tmp_path), "s1")
    assert "NA" in set(long_df["tool"])
    # the empty Completeness value of k2_std is dropped, not read as 0
    k2 = long_df[(long_df["tool"] == "k2_std") & (long_df["metric"] == "Completeness")]
    assert k2.empty


def test_pivot_adds_classifier_and_broadcasts_unifrac(comparer, tmp_path):
    long_df = comparer.parse_opal_metrics(write_opal(tmp_path), "s1")
    wide = comparer.pivot_metrics(long_df, "s1", {"NA": "metaphlan", "k2_std": "kraken2"})
    assert list(wide.columns[:4]) == ["sample", "tool", "classifier", "rank"]
    classifier = dict(zip(wide["tool"], wide["classifier"]))
    assert classifier == {"Gold standard": "Gold standard", "NA": "metaphlan", "k2_std": "kraken2"}
    k2 = wide[wide["tool"] == "k2_std"].set_index("rank")
    assert list(k2.index) == ["genus", "species"]  # taxonomic order
    assert (k2["Weighted UniFrac error"] == 0.8).all()
    assert pd.isna(k2.loc["genus", "Completeness"])


def gold_and_profile():
    gold = pd.DataFrame({"TAXID": ["1", "2", "3"], "RANK": ["species"] * 3,
                         "PERCENTAGE": [50.0, 49.5, 0.5], "name": ["a", "b", "c"]})
    prof = pd.DataFrame({"TAXID": ["1", "2", "4"], "RANK": ["species"] * 3,
                         "PERCENTAGE": [60.0, 39.9, 0.1], "name": ["a", "b", "d"]})
    return gold, prof


def test_diff_status_and_min_abs_only_filters_written_table(comparer, tmp_path):
    gold, prof = gold_and_profile()
    out = tmp_path / "diff.tsv"
    diff = comparer.perform_differential_abundance(gold, {"k2": prof}, out, min_abs=1.0)
    status = dict(zip(diff["taxid"], diff["status"]))
    assert status == {"1": "TP", "2": "TP", "3": "FN", "4": "FP"}
    written = pd.read_csv(out, sep="\t", dtype=str)
    # taxa 3 and 4 differ by < 1 percentage point: not written, but still counted in the returned table
    assert set(written["taxid"]) == {"1", "2"}
    assert len(diff) == 4
