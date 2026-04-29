import sys
from unittest.mock import patch
import pytest

def test_main_runs_successfully(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    
    test_args = [
        "main.py",
        "--scenario", "data/scenarios/baseline.yaml",
        "--data-dir", "data",
        "--out-dir", str(out_dir)
    ]
    
    # We must patch sys.argv and import main to test it
    try:
        from main import main
    except ImportError:
        pytest.fail("main.py not implemented yet")
        
    with patch.object(sys, 'argv', test_args):
        main()
        
    assert (out_dir / "summary.json").exists()
