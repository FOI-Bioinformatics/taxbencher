"""Unit tests for bin/taxbencher_taxonomy.py (taxopy-based lineage lookups)."""

import shutil
import tarfile
import zipfile

import pytest

from conftest import read_profile

ECOLI = 562
OUTDATED_ECOLI = 99999562  # not in the reduced taxonomy; merged into 562 below


@pytest.fixture
def merged_taxonomy(taxonomy_dir, tmp_path):
    """Copy of the reduced taxdump whose merged.dmp maps OUTDATED_ECOLI to E. coli."""
    directory = tmp_path / "taxdump_merged"
    shutil.copytree(taxonomy_dir, directory)
    (directory / "merged.dmp").write_text(f"{OUTDATED_ECOLI}\t|\t{ECOLI}\t|\n")
    return directory


def test_lineage_is_root_first(taxonomy, taxonomy_dir):
    lineage = taxonomy.TaxonomyResolver(taxonomy_dir).resolve(ECOLI)
    assert lineage.taxids[0] == 1
    assert lineage.taxids[-1] == ECOLI
    assert lineage.ranks[-1] == "species"
    assert lineage.names[-1] == "Escherichia coli"
    assert len(lineage.taxids) == len(lineage.ranks) == len(lineage.names)


def test_unknown_taxid_resolves_to_none(taxonomy, taxonomy_dir):
    assert taxonomy.TaxonomyResolver(taxonomy_dir).resolve(999999999) is None


def test_merged_taxid_resolves_to_current_node(taxonomy, merged_taxonomy):
    resolver = taxonomy.TaxonomyResolver(merged_taxonomy)
    assert resolver.current_taxid(OUTDATED_ECOLI) == ECOLI
    lineage = resolver.resolve(OUTDATED_ECOLI)
    # taxopy on its own keeps the outdated ID as the leaf; it must be the current node
    assert lineage.taxids == resolver.resolve(ECOLI).taxids


def test_archive_and_directory_give_same_lineage(taxonomy, taxdump, taxonomy_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from_archive = taxonomy.TaxonomyResolver(taxdump).resolve(ECOLI)
    from_dir = taxonomy.TaxonomyResolver(taxonomy_dir).resolve(ECOLI)
    assert from_archive.taxids == from_dir.taxids
    assert (tmp_path / "taxdump_extracted" / "nodes.dmp").is_file()


def test_extract_zip_with_subdirectory_and_without_merged(taxonomy, taxonomy_dir, tmp_path):
    archive = tmp_path / "taxdmp_2025-01-01.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for name in ("nodes.dmp", "names.dmp"):
            zf.write(taxonomy_dir / name, f"taxdmp/{name}")
    out = taxonomy.extract_taxdump(archive, tmp_path / "out")
    assert sorted(p.name for p in out.iterdir()) == ["merged.dmp", "names.dmp", "nodes.dmp"]
    assert (out / "merged.dmp").stat().st_size == 0
    assert taxonomy.TaxonomyResolver(out).resolve(ECOLI).taxids[-1] == ECOLI


def test_extract_rejects_archive_without_names(taxonomy, taxonomy_dir, tmp_path):
    archive = tmp_path / "broken.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(taxonomy_dir / "nodes.dmp", arcname="nodes.dmp")
    with pytest.raises(ValueError, match="names.dmp"):
        taxonomy.extract_taxdump(archive, tmp_path / "out")


def test_directory_without_dmp_files_is_rejected(taxonomy, tmp_path):
    with pytest.raises(FileNotFoundError, match="nodes.dmp"):
        taxonomy.taxdump_dir(tmp_path)


def test_cli_extract(taxonomy, taxdump, tmp_path, capsys):
    assert taxonomy.main(["extract", str(taxdump), str(tmp_path / "td")]) == 0
    assert (tmp_path / "td" / "names.dmp").is_file()
    assert taxonomy.main(["extract", str(tmp_path / "missing.tar.gz"), str(tmp_path / "x")]) == 1


def test_converter_places_merged_taxid_on_current_node(converter, merged_taxonomy, tmp_path):
    src = tmp_path / "merged.tsv"
    src.write_text(f"taxonomy_id\tcount\n{OUTDATED_ECOLI}\t10\n")
    out = tmp_path / "merged.bioboxes"
    converter.convert_taxpasta_to_bioboxes(input_file=src, output_file=out, sample_id="s1",
                                           ranks=converter.parse_ranks(converter.DEFAULT_RANKS),
                                           taxdump=merged_taxonomy)
    _, rows = read_profile(out)
    species = [row for row in rows if row["RANK"] == "species"]
    assert [row["TAXID"] for row in species] == [str(ECOLI)]


def test_fixer_replaces_merged_taxid(fixer, merged_taxonomy, tmp_path):
    src = tmp_path / "truth.tsv"
    src.write_text(f"{OUTDATED_ECOLI}\tspecies\t100\n")
    out = tmp_path / "gold.bioboxes"
    fixer.fix_gold_standard(src, out, "s", fixer.DEFAULT_RANKS, merged_taxonomy,
                            True, False, "NCBI", "0.9.1")
    _, rows = read_profile(out)
    assert {row["TAXID"] for row in rows if row["RANK"] == "species"} == {str(ECOLI)}
