import sys
from unittest.mock import patch
from pathlib import Path
import pytest

def test_main_runs_successfully(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    
    base_dir = Path(__file__).parent.parent
    
    test_args = [
        "main.py",
        "--scenario", str(base_dir / "data/scenarios/baseline.yaml"),
        "--data-dir", str(base_dir / "data"),
        "--out-dir", str(out_dir)
    ]
    
    # We must patch sys.argv and import main to test it
    from main import main
        
    with patch.object(sys, 'argv', test_args):
        main()
        
    assert (out_dir / "summary.json").exists()
