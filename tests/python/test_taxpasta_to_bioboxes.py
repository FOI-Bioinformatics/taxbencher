"""Unit tests for bin/taxpasta_to_bioboxes.py (taxopy-based, pandas-free)."""

from pathlib import Path

import pytest
import taxpasta_to_bioboxes as t2b


def write_tsv(path: Path, rows):
    lines = ["taxonomy_id\tcount"]
    lines += [f"{tid}\t{count}" for tid, count in rows]
    path.write_text("\n".join(lines) + "\n")


def parse_bioboxes(path: Path):
    """Return (headers dict, list of data-row field lists)."""
    headers, data = {}, []
    for line in path.read_text().splitlines():
        if line.startswith("@@") or not line.strip():
            continue
        if line.startswith("@"):
            key, _, val = line[1:].partition(":")
            headers[key] = val
        else:
            data.append(line.split("\t"))
    return headers, data


def test_read_taxpasta_tsv_filters_invalid(tmp_path):
    f = tmp_path / "in.tsv"
    f.write_text(
        "taxonomy_id\tcount\n"
        "561\t100\n"
        "\t50\n"          # missing taxid
        "2\tNaNish\n"     # non-numeric count
        "1224\t0\n"        # zero count dropped
        "1236\t5.5\n"
    )
    rows = t2b.read_taxpasta_tsv(f)
    assert rows == [(561, 100.0), (1236, 5.5)]


def test_read_taxpasta_tsv_requires_columns(tmp_path):
    f = tmp_path / "bad.tsv"
    f.write_text("foo\tbar\n1\t2\n")
    with pytest.raises(SystemExit):
        t2b.read_taxpasta_tsv(f)


def test_get_taxonomy_info_root_first_lineage(taxonomy_dir):
    taxdb = t2b.load_taxonomy(taxonomy_dir)
    rank, taxpath, taxpathsn = t2b.get_taxonomy_info(561, taxdb)
    assert rank == "genus"
    # Root-first, pipe-separated, starts at root (1) and ends at the taxon.
    assert taxpath.startswith("1|131567|2")
    assert taxpath.endswith("|561")
    assert taxpathsn.split("|")[0] == "root"
    assert taxpathsn.endswith("Escherichia")
    # TAXPATH and TAXPATHSN must have matching depth.
    assert len(taxpath.split("|")) == len(taxpathsn.split("|"))


def test_get_taxonomy_info_unknown_taxid(taxonomy_dir):
    taxdb = t2b.load_taxonomy(taxonomy_dir)
    assert t2b.get_taxonomy_info(999999999, taxdb) is None


def test_convert_produces_valid_bioboxes(tmp_path, taxonomy_dir):
    inp = tmp_path / "in.tsv"
    write_tsv(inp, [(561, 300), (1236, 100), (2, 50)])
    out = tmp_path / "out.bioboxes"
    n = t2b.convert_taxpasta_to_bioboxes(
        input_file=inp, output_file=out, sample_id="s1",
        ranks=["superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"],
        taxonomy_dir=taxonomy_dir,
    )
    assert n == 3
    headers, data = parse_bioboxes(out)
    assert headers["SampleID"] == "s1"
    assert headers["Version"] == "0.9.1"
    assert headers["TaxonomyID"] == "NCBI"
    assert len(data) == 3
    # Percentages renormalised to ~100.
    total = sum(float(row[4]) for row in data)
    assert abs(total - 100.0) < 0.01
    # Every row has the 5 required columns and an OPAL-supported rank.
    valid = {"superkingdom", "phylum", "class", "order", "family", "genus", "species", "strain"}
    for row in data:
        assert len(row) == 5
        assert row[1] in valid


def test_convert_fails_loudly_when_all_unresolved(tmp_path, taxonomy_dir):
    inp = tmp_path / "in.tsv"
    # taxid 0 is invalid, 999999999 not in taxonomy -> nothing convertible.
    write_tsv(inp, [(0, 100), (999999999, 50)])
    out = tmp_path / "out.bioboxes"
    with pytest.raises(SystemExit):
        t2b.convert_taxpasta_to_bioboxes(
            input_file=inp, output_file=out, sample_id="s1",
            ranks=["genus"], taxonomy_dir=taxonomy_dir,
        )


def test_load_taxonomy_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        t2b.load_taxonomy(tmp_path)
