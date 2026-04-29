from src.config import load_scenario, load_csv_data

def test_load_scenario(tmp_path):
    yaml_file = tmp_path / "baseline.yaml"
    yaml_file.write_text("""
scenario_id: baseline
simulation:
  shift_length_hours: 8
  replications: 30
  base_random_seed: 123
fleet:
  truck_count: 8
""")
    config = load_scenario(yaml_file)
    assert config.scenario_id == "baseline"
    assert config.shift_length_hours == 8
    assert config.replications == 30
    assert config.truck_count == 8

def test_load_csv_data(tmp_path):
    csv_file = tmp_path / "nodes.csv"
    csv_file.write_text("node_id,node_type\nPARK,parking\nLOAD_N,load_ore\n")
    df = load_csv_data(csv_file)
    assert len(df) == 2
    assert "node_id" in df.columns
