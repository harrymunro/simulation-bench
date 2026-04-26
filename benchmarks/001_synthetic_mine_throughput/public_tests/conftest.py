import os
import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--submission-outputs-dir",
        action="store",
        default=os.environ.get("SUBMISSION_OUTPUTS_DIR", "."),
        help="Directory containing submission output files.",
    )

@pytest.fixture
def submission_outputs_dir(request):
    return request.config.getoption("--submission-outputs-dir")

