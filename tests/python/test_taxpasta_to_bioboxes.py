"""Unit tests for bin/taxpasta_to_bioboxes.py (CAMI profile conversion)."""

import argparse

import pytest

from conftest import rank_sums, read_profile


def convert(converter, tmp_path, src, **kwargs):
    out = tmp_path / "out.bioboxes"
    defaults = dict(sample_id="s1", ranks=converter.parse_ranks(converter.DEFAULT_RANKS))
    defaults.update(kwargs)
    n = converter.convert_taxpasta_to_bioboxes(input_file=src, output_file=out, **defaults)
    return n, out


def test_direct_counts_accumulate_and_sum_per_rank(converter, test_data, taxonomy_dir, tmp_path):
    n, out = convert(converter, tmp_path, test_data / "taxpasta" / "sample1_kraken2.tsv", taxdump=taxonomy_dir)
    headers, rows = read_profile(out)
    assert n == len(rows) > 0
    assert headers["SampleID"] == "s1"
    sums = rank_sums(rows)
    # all classified reads of this profile are placed at superkingdom
    assert sums["superkingdom"] == pytest.approx(100.0, abs=1e-3)
    # no rank may exceed 100 %
    assert all(v <= 100.0 + 1e-6 for v in sums.values())
    # genus Francisella includes its species and strains
    francisella = [r for r in rows if r["TAXID"] == "262"][0]
    tularensis = [r for r in rows if r["TAXID"] == "263"][0]
    assert float(francisella["PERCENTAGE"]) >= float(tularensis["PERCENTAGE"])
    # TAXPATH is one element per rank of @Ranks
    assert tularensis["TAXPATH"] == "2|1224|1236|72273|34064|262|263"
    assert tularensis["TAXPATHSN"].split("|")[-1] == "Francisella tularensis"


def test_clade_mode_does_not_double_count(converter, test_data, taxonomy_dir, tmp_path):
    src = test_data / "taxpasta" / "sample1_metaphlan.tsv"
    n, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir, abundance_mode="clade")
    _, rows = read_profile(out)
    sums = rank_sums(rows)
    # the top level carries everything; deeper ranks may be incomplete but never exceed it
    assert sums["superkingdom"] == pytest.approx(100.0, abs=1e-3)
    assert all(v <= 100.0 + 1e-6 for v in sums.values())
    # values are used as they are: genus Francisella (262) relative to Bacteria (2) in the input
    counts = {int(row.split("\t")[0]): float(row.split("\t")[1]) for row in src.read_text().splitlines()[1:]}
    francisella = [r for r in rows if r["TAXID"] == "262"][0]
    assert float(francisella["PERCENTAGE"]) == pytest.approx(counts[262] / counts[2] * 100, abs=1e-3)


def test_clade_mode_on_direct_counts_is_rejected(converter, test_data, taxonomy_dir, tmp_path):
    with pytest.raises(RuntimeError, match="exceed 100"):
        convert(converter, tmp_path, test_data / "taxpasta" / "sample1_kraken2.tsv",
                taxdump=taxonomy_dir, abundance_mode="clade")


def test_lineage_columns_without_taxonomy(converter, tmp_path, test_data):
    src = test_data.parent.parent / "modules" / "local" / "taxpasta_to_bioboxes" / "testdata" / "test_kraken2_lineage.tsv"
    n, out = convert(converter, tmp_path, src, use_taxonomy=False)
    _, rows = read_profile(out)
    sums = rank_sums(rows)
    assert sums["superkingdom"] == pytest.approx(100.0, abs=1e-6)
    assert sums["genus"] == pytest.approx(100.0, abs=1e-6)
    escherichia = [r for r in rows if r["TAXID"] == "561"][0]
    assert escherichia["TAXPATH"] == "2|1224|1236|91347|543|561"


def test_no_lineage_and_no_taxonomy_fails(converter, test_data, tmp_path):
    with pytest.raises(RuntimeError, match="lineage columns"):
        convert(converter, tmp_path, test_data / "taxpasta" / "sample1_kraken2.tsv", use_taxonomy=False)


def test_unknown_taxids_only_fails_instead_of_empty_profile(converter, taxonomy_dir, tmp_path):
    src = tmp_path / "unknown.tsv"
    src.write_text("taxonomy_id\tcount\n999999\t10\n888888\t5\n")
    with pytest.raises(RuntimeError, match="empty profile"):
        convert(converter, tmp_path, src, taxdump=taxonomy_dir)
    # allow_empty writes a header-only file
    n, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir, allow_empty=True)
    assert n == 0
    assert all(line.startswith("@") for line in out.read_text().splitlines())


def test_include_unclassified_lowers_percentages(converter, taxonomy_dir, tmp_path):
    src = tmp_path / "unc.tsv"
    src.write_text("taxonomy_id\tcount\n0\t100\n562\t100\n")
    _, out_excl = convert(converter, tmp_path, src, taxdump=taxonomy_dir)
    _, rows_excl = read_profile(out_excl)
    assert rank_sums(rows_excl)["species"] == pytest.approx(100.0)
    out2 = tmp_path / "incl.bioboxes"
    converter.convert_taxpasta_to_bioboxes(input_file=src, output_file=out2, sample_id="s",
                                           ranks=converter.parse_ranks(converter.DEFAULT_RANKS),
                                           taxdump=taxonomy_dir, include_unclassified=True)
    _, rows_incl = read_profile(out2)
    assert rank_sums(rows_incl)["species"] == pytest.approx(50.0)


def test_kingdom_is_not_mapped_to_superkingdom(converter, taxonomy_dir, tmp_path):
    # 3379134 (Pseudomonadati) has rank 'kingdom' in the reduced taxonomy
    src = tmp_path / "k.tsv"
    src.write_text("taxonomy_id\tcount\n3379134\t10\n562\t90\n")
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir)
    _, rows = read_profile(out)
    sk = [r for r in rows if r["RANK"] == "superkingdom"]
    assert [r["TAXID"] for r in sk] == ["2"]
    assert float(sk[0]["PERCENTAGE"]) == pytest.approx(100.0)


def test_strain_from_no_rank_below_species(converter, taxonomy_dir, tmp_path):
    # 272631 is a strain of Burkholderia pseudomallei (28450)
    src = tmp_path / "strain.tsv"
    src.write_text("taxonomy_id\tcount\n272631\t10\n")
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir)
    _, rows = read_profile(out)
    by_rank = {r["RANK"]: r for r in rows}
    assert by_rank["species"]["TAXID"] == "28450"
    assert by_rank["strain"]["TAXID"] == "272631"
    assert by_rank["strain"]["TAXPATH"].endswith("|28450|272631")


def test_missing_columns_exit(converter, tmp_path):
    src = tmp_path / "bad.tsv"
    src.write_text("foo\tbar\n1\t2\n")
    with pytest.raises(SystemExit):
        converter.read_profile(src)


def test_parse_ranks_accepts_pipe_and_comma():
    import conftest  # noqa: F401
    from conftest import load_script
    conv = load_script("taxpasta_to_bioboxes")
    assert conv.parse_ranks("superkingdom|phylum") == ["superkingdom", "phylum"]
    assert conv.parse_ranks("domain,species") == ["superkingdom", "species"]
    with pytest.raises(argparse.ArgumentTypeError):
        conv.parse_ranks("species|species")


FRANCISELLA = ["2", "1224", "1236", "72273", "34064", "262", "263"]


def write_counts(path, rows, extra_header=""):
    path.write_text("taxonomy_id\tcount" + extra_header + "\n" + "".join("\t".join(map(str, r)) + "\n" for r in rows))
    return path


def test_clade_mode_nested_strains_are_counted_once(converter, test_data, taxonomy_dir, validator, tmp_path):
    # 119857 (subsp. holarctica) and its strains 1432652/393011: one strain-rank entry, own TAXPATH
    src = write_counts(tmp_path / "in.tsv", [(t, 100) for t in FRANCISELLA] + [(119857, 100), (393011, 60)])
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir, abundance_mode="clade")
    _, rows = read_profile(out)
    strains = [r for r in rows if r["RANK"] == "strain"]
    assert [(r["TAXID"], float(r["PERCENTAGE"])) for r in strains] == [("119857", pytest.approx(100.0))]
    assert strains[0]["TAXPATH"].split("|")[-1] == "119857"
    # without the parent, the listed strains are summed onto it
    src = write_counts(tmp_path / "in2.tsv", [(t, 100) for t in FRANCISELLA] + [(393011, 60), (1432652, 30)])
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir, abundance_mode="clade")
    _, rows = read_profile(out)
    assert rank_sums(rows)["strain"] == pytest.approx(90.0)
    # the bundled realistic MetaPhlAn fixture converts to a valid profile
    _, out = convert(converter, tmp_path, test_data / "taxpasta" / "realistic_metaphlan.tsv",
                     taxdump=taxonomy_dir, abundance_mode="clade")
    ok, errors, _, _ = validator.validate_bioboxes(out)
    assert ok, errors


def test_tiny_abundances_are_not_rounded_to_zero(converter, taxonomy_dir, tmp_path):
    src = write_counts(tmp_path / "in.tsv", [(562, 300_000_000), (263, 1)])
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir)
    _, rows = read_profile(out)
    tiny = [r for r in rows if r["TAXID"] == "263"][0]
    assert 0 < float(tiny["PERCENTAGE"]) < 1e-6


def test_clade_mode_include_unclassified_caps_merged_taxid0(converter, taxonomy_dir, tmp_path):
    # MetaPhlAn 4 via taxpasta: taxid 0 holds UNCLASSIFIED (10 %) plus an unmappable t__SGB row (90 %)
    lineage = ["2", "1224", "1236", "91347", "543", "561", "562"]
    src = write_counts(tmp_path / "in.tsv", [(0, 100_000_000)] + [(t, 90_000_000) for t in lineage])
    _, out = convert(converter, tmp_path, src, taxdump=taxonomy_dir, abundance_mode="clade", include_unclassified=True)
    _, rows = read_profile(out)
    assert rank_sums(rows)["superkingdom"] == pytest.approx(90.0)


def test_multi_sample_long_table_is_rejected(converter, taxonomy_dir, tmp_path):
    src = write_counts(tmp_path / "in.tsv", [(562, 10, "a"), (263, 5, "b")], extra_header="\tsample")
    with pytest.raises(SystemExit):
        convert(converter, tmp_path, src, taxdump=taxonomy_dir)
