"""Unit tests for bin/validate_profiler_format.py (raw profiler output checks)."""

import subprocess
import sys

import pytest

from conftest import BIN, load_script

SCRIPT = BIN / "validate_profiler_format.py"


@pytest.fixture(scope="module")
def checker():
    return load_script("validate_profiler_format")


@pytest.mark.parametrize("profiler, name", [
    ("kraken2", "sample1_kraken2.kreport"),
    ("centrifuge", "sample1_centrifuge.report"),
    ("metaphlan", "sample1_metaphlan.profile"),
])
def test_repository_raw_outputs_are_valid(checker, test_data, profiler, name):
    ok, issues = checker.validate_file_format(profiler, test_data / "profiler_outputs" / name)
    assert ok, issues


def test_kraken2_report_with_minimizer_columns_is_valid(checker, tmp_path):
    # kraken2 --report-minimizer-data adds two columns (8 in total)
    report = tmp_path / "sample.report"
    report.write_text(" 100.00\t10\t10\t1000\t900\tS\t562\tEscherichia coli\n")
    ok, issues = checker.validate_file_format("kraken2", report)
    assert ok, issues


def test_unknown_profiler_is_rejected(checker, test_data):
    ok, issues = checker.validate_file_format("blast", test_data / "profiler_outputs" / "sample1_kraken2.kreport")
    assert not ok
    assert "Unknown profiler 'blast'" in issues[0]


def test_missing_and_empty_files_are_rejected(checker, tmp_path):
    ok, issues = checker.validate_file_format("kraken2", tmp_path / "missing.kreport")
    assert not ok and "does not exist" in issues[0]
    empty = tmp_path / "empty.kreport"
    empty.write_text("\n")
    ok, issues = checker.validate_file_format("kraken2", empty)
    assert not ok and issues == ["File is empty"]


def test_header_only_metaphlan_profile_is_rejected(checker, tmp_path):
    profile = tmp_path / "only_header.profile"
    profile.write_text("#mpa_vJan21\n#clade_name\tNCBI_tax_id\trelative_abundance\n")
    ok, issues = checker.validate_file_format("metaphlan", profile)
    assert not ok
    assert "no data lines" in issues[0]


def test_wrong_column_count_and_extension_are_reported(checker, tmp_path):
    report = tmp_path / "sample.csv"
    report.write_text("50.0\t5\t562\n")
    ok, issues = checker.validate_file_format("centrifuge", report)
    assert not ok
    assert any("does not match expected extensions" in issue for issue in issues)
    assert any("expects at least 6" in issue for issue in issues)


def test_inconsistent_column_counts_are_only_a_warning(checker, tmp_path):
    out = tmp_path / "sample.kaiju"
    out.write_text("C\tread1\t562\nC\tread2\t562\textra\n")
    ok, issues = checker.validate_file_format("kaiju", out)
    assert ok
    assert any(issue.startswith("WARNING: Inconsistent column counts") for issue in issues)


def run_cli(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def test_cli_exit_codes(test_data, tmp_path):
    assert run_cli("kraken2", str(test_data / "profiler_outputs" / "sample1_kraken2.kreport")).returncode == 0
    bad = tmp_path / "bad.kreport"
    bad.write_text("only\ttwo\n")
    assert run_cli("kraken2", str(bad)).returncode == 1
    # the file argument is only optional together with --show-spec
    assert run_cli("kraken2").returncode == 2
    spec = run_cli("metaphlan", "--show-spec")
    assert spec.returncode == 0
    assert "Format specification for metaphlan" in spec.stdout
    assert run_cli("blast", "--show-spec").returncode == 1
