"""Shared pytest fixtures."""
from pathlib import Path
import pytest


SUBMISSION_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def data_dir() -> Path:
    return SUBMISSION_ROOT / "data"


@pytest.fixture
def scenarios_dir(data_dir) -> Path:
    return data_dir / "scenarios"


@pytest.fixture
def tmp_output_dir(tmp_path) -> Path:
    out = tmp_path / "results"
    out.mkdir()
    return out
