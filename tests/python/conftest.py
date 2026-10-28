"""Shared fixtures for the Python unit tests of the pipeline's bin/ scripts."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin"
TEST_DATA = ROOT / "assets" / "test_data"
TAXDUMP = TEST_DATA / "taxonomy" / "taxdump.tar.gz"


def load_script(name: str):
    """Import a bin/ script (no .py package) as a module."""
    spec = importlib.util.spec_from_file_location(name, BIN / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def test_data() -> Path:
    return TEST_DATA


@pytest.fixture(scope="session")
def taxdump() -> Path:
    assert TAXDUMP.exists(), f"missing reduced taxonomy {TAXDUMP}"
    return TAXDUMP


@pytest.fixture(scope="session")
def ete3_db(tmp_path_factory, taxdump) -> Path:
    """ete3 sqlite database built once per session from the reduced taxdump."""
    from ete3 import NCBITaxa  # noqa: WPS433

    db = tmp_path_factory.mktemp("taxdb") / "taxa.sqlite"
    NCBITaxa(dbfile=str(db), taxdump_file=str(taxdump))
    return db


@pytest.fixture(scope="session")
def converter():
    return load_script("taxpasta_to_bioboxes")


@pytest.fixture(scope="session")
def validator():
    return load_script("validate_bioboxes")


@pytest.fixture(scope="session")
def fixer():
    return load_script("fix_gold_standard")


@pytest.fixture(scope="session")
def summariser():
    return load_script("summarise_benchmark")


def read_profile(path: Path):
    """Return (headers, rows) of a CAMI profile; rows are dicts keyed by column name."""
    headers, columns, rows = {}, [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith("@@"):
            columns = line[2:].split("\t")
        elif line.startswith("@"):
            key, _, value = line[1:].partition(":")
            headers[key] = value
        elif line.strip():
            rows.append(dict(zip(columns, line.split("\t"))))
    return headers, rows


def rank_sums(rows):
    sums = {}
    for row in rows:
        sums[row["RANK"]] = sums.get(row["RANK"], 0.0) + float(row["PERCENTAGE"])
    return sums
