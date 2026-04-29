from pathlib import Path
from src.config import load_scenario
path = Path("data/scenarios/trucks_4.yaml")
config = load_scenario(path)
print(config)
