from pathlib import Path

REQUIRED = [
    "conceptual_model.md",
    "README.md",
    "results.csv",
    "summary.json",
    "event_log.csv",
]

def test_required_output_files_exist(submission_outputs_dir):
    outputs = Path(submission_outputs_dir)
    missing = [name for name in REQUIRED if not (outputs / name).exists()]
    assert not missing, f"Missing required output files: {missing}"

