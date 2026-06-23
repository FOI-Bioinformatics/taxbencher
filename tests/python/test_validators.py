"""Unit tests for the bin/ validation scripts."""

from pathlib import Path

import validate_bioboxes
import validate_profiler_format

VALID_BIOBOXES = """@SampleID:s1
@Version:0.9.1
@Ranks:superkingdom|phylum|class|order|family|genus|species|strain
@TaxonomyID:NCBI
@@TAXID\tRANK\tTAXPATH\tTAXPATHSN\tPERCENTAGE
2\tsuperkingdom\t1|131567|2\troot|cellular organisms|Bacteria\t100.0
"""


def test_validate_bioboxes_accepts_valid(tmp_path):
    f = tmp_path / "ok.bioboxes"
    f.write_text(VALID_BIOBOXES)
    is_valid, errors, _stats = validate_bioboxes.validate_bioboxes(f)
    assert is_valid, errors


def test_validate_bioboxes_detects_column_mismatch(tmp_path):
    # Header declares 5 columns; data row has 4 -> the critical OPAL-breaking case.
    bad = VALID_BIOBOXES.replace(
        "2\tsuperkingdom\t1|131567|2\troot|cellular organisms|Bacteria\t100.0",
        "2\tsuperkingdom\t1|131567|2\t100.0",
    )
    f = tmp_path / "bad.bioboxes"
    f.write_text(bad)
    is_valid, errors, _stats = validate_bioboxes.validate_bioboxes(f)
    assert not is_valid
    assert any("Column count mismatch" in e for e in errors)


def test_validate_bioboxes_detects_unsupported_rank(tmp_path):
    bad = VALID_BIOBOXES.replace("superkingdom\t1|131567|2", "clade\t1|131567|2")
    f = tmp_path / "rank.bioboxes"
    f.write_text(bad)
    is_valid, errors, _stats = validate_bioboxes.validate_bioboxes(f)
    assert not is_valid


def test_validate_bioboxes_repo_gold_standards_are_valid():
    repo = Path(__file__).resolve().parents[2]
    for name in ("gold_standard.bioboxes", "gold_standard_realistic.bioboxes"):
        gs = repo / "assets" / "test_data" / name
        is_valid, errors, _stats = validate_bioboxes.validate_bioboxes(gs)
        assert is_valid, f"{name}: {errors}"


def test_validate_bioboxes_main_exit_codes(tmp_path, capsys, monkeypatch):
    bad = tmp_path / "bad.bioboxes"
    bad.write_text(VALID_BIOBOXES.replace("@TaxonomyID:NCBI\n", ""))  # missing header
    # Default: non-zero exit on invalid.
    monkeypatch.setattr("sys.argv", ["validate_bioboxes.py", str(bad)])
    assert validate_bioboxes.main() == 1
    # --warn-only: exit 0 even when invalid.
    monkeypatch.setattr("sys.argv", ["validate_bioboxes.py", str(bad), "--warn-only"])
    assert validate_bioboxes.main() == 0


def test_validate_profiler_format_kraken2(tmp_path):
    f = tmp_path / "s.kreport"
    f.write_text(" 50.00\t500\t500\tU\t0\tunclassified\n 30.00\t300\t0\tD\t2\tBacteria\n")
    is_valid, _issues = validate_profiler_format.validate_file_format("kraken2", f)
    assert is_valid


def test_validate_profiler_format_unknown_profiler(tmp_path):
    f = tmp_path / "s.kreport"
    f.write_text("x\n")
    is_valid, issues = validate_profiler_format.validate_file_format("notareal", f)
    assert not is_valid
    assert any("Unknown profiler" in i for i in issues)
