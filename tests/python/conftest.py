"""Shared pytest fixtures for taxbencher bin/ script tests."""

import sys
from pathlib import Path

import pytest

# Make the pipeline's bin/ scripts importable as modules.
REPO_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = REPO_ROOT / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


@pytest.fixture(scope="session")
def taxonomy_dir() -> Path:
    """Directory holding the bundled test taxdump (nodes.dmp + names.dmp)."""
    d = REPO_ROOT / "assets" / "test_data" / "taxonomy"
    assert (d / "nodes.dmp").exists(), "test taxdump nodes.dmp missing"
    assert (d / "names.dmp").exists(), "test taxdump names.dmp missing"
    return d


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return REPO_ROOT / "assets" / "test_data"
