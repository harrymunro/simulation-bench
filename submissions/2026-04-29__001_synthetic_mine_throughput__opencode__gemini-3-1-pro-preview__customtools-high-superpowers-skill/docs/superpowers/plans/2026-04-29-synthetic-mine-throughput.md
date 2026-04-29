# Synthetic Mine Throughput Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SimPy discrete-event simulation of a mine haulage network to evaluate ore throughput under different scenarios.

**Architecture:** A segment-by-segment process model where trucks are active SimPy processes navigating a NetworkX directed graph. Constrained road segments and service points are modeled as SimPy resources.

**Tech Stack:** Python 3, SimPy, NetworkX, Pandas, PyYAML, SciPy.

---

### Task 1: Configuration Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from pathlib import Path
from src.config import Config, load_scenario, load_csv_data

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

```python
import yaml
import pandas as pd
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    scenario_id: str
    shift_length_hours: int
    replications: int
    base_random_seed: int
    truck_count: int

def load_scenario(yaml_path: Path) -> Config:
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return Config(
        scenario_id=data['scenario_id'],
        shift_length_hours=data['simulation']['shift_length_hours'],
        replications=data['simulation']['replications'],
        base_random_seed=data['simulation'].get('base_random_seed', 12345),
        truck_count=data['fleet']['truck_count']
    )

def load_csv_data(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_config.py src/config.py
git commit -m "feat: config loading module"
```

---

### Task 2: Topology Module

**Files:**
- Create: `src/topology.py`
- Create: `tests/test_topology.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
import pandas as pd
import networkx as nx
from src.topology import build_graph, get_base_travel_time

def test_build_graph():
    nodes_df = pd.DataFrame([
        {"node_id": "N1", "node_type": "junction", "capacity": None, "service_time_mean_min": None, "service_time_sd_min": None},
        {"node_id": "N2", "node_type": "load_ore", "capacity": 1, "service_time_mean_min": 5.0, "service_time_sd_min": 1.0}
    ])
    edges_df = pd.DataFrame([
        {"edge_id": "E1", "from_node": "N1", "to_node": "N2", "distance_m": 1000, "max_speed_kph": 30, "capacity": 999}
    ])
    
    G = build_graph(nodes_df, edges_df)
    
    assert isinstance(G, nx.DiGraph)
    assert "N1" in G.nodes
    assert "N2" in G.nodes
    assert G.nodes["N2"]["capacity"] == 1
    assert G.edges["N1", "N2"]["distance_m"] == 1000
    assert "E1" in [edge[2]["edge_id"] for edge in G.edges(data=True)]

def test_get_base_travel_time():
    # 1000m at 30kph = 2 minutes
    time_min = get_base_travel_time(1000, 30)
    assert time_min == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_topology.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
import networkx as nx
import pandas as pd

def build_graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    
    for _, row in nodes_df.iterrows():
        G.add_node(row["node_id"], **row.to_dict())
        
    for _, row in edges_df.iterrows():
        # Only add edge if it's not explicitly closed
        if "closed" not in row or not row["closed"]:
            G.add_edge(row["from_node"], row["to_node"], **row.to_dict())
            
    return G

def get_base_travel_time(distance_m: float, speed_kph: float) -> float:
    # return minutes
    if speed_kph <= 0:
        return float('inf')
    return (distance_m / 1000.0) / speed_kph * 60.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_topology.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_topology.py src/topology.py
git commit -m "feat: networkx graph builder"
```

---

### Task 3: Metrics & Event Logger

**Files:**
- Create: `src/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
from src.metrics import EventLogger, SimulationMetrics
import pandas as pd

def test_event_logger():
    logger = EventLogger()
    logger.log(0.0, 1, "baseline", "T01", "dispatch", "PARK", "LOAD_N", "PARK", False, 0.0, None, 0)
    
    df = logger.to_dataframe()
    assert len(df) == 1
    assert df.iloc[0]["event_type"] == "dispatch"
    assert df.iloc[0]["truck_id"] == "T01"

def test_metrics_collection():
    metrics = SimulationMetrics()
    metrics.record_cycle(truck_id="T1", cycle_time_min=30.0, payload=100.0)
    assert metrics.total_tonnes == 100.0
    assert metrics.cycle_times == [30.0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
import pandas as pd
from typing import List, Dict

class EventLogger:
    def __init__(self):
        self.events = []
        
    def log(self, time_min: float, replication: int, scenario_id: str, 
            truck_id: str, event_type: str, from_node: str, to_node: str, 
            location: str, loaded: bool, payload_tonnes: float, 
            resource_id: str, queue_length: int):
        self.events.append({
            "time_min": time_min,
            "replication": replication,
            "scenario_id": scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": loaded,
            "payload_tonnes": payload_tonnes,
            "resource_id": resource_id,
            "queue_length": queue_length
        })
        
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.events)

class SimulationMetrics:
    def __init__(self):
        self.total_tonnes = 0.0
        self.cycle_times = []
        self.loader_queue_times = []
        self.crusher_queue_times = []
        self.truck_active_times = {} # truck_id -> float
        
    def record_cycle(self, truck_id: str, cycle_time_min: float, payload: float):
        self.total_tonnes += payload
        self.cycle_times.append(cycle_time_min)
        
    def record_queue_time(self, resource_type: str, time_min: float):
        if resource_type == 'loader':
            self.loader_queue_times.append(time_min)
        elif resource_type == 'crusher':
            self.crusher_queue_times.append(time_min)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_metrics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_metrics.py src/metrics.py
git commit -m "feat: event logging and metrics tracking"
```

---

### Task 4: SimPy Environment Setup

**Files:**
- Create: `src/simulation.py`
- Create: `tests/test_simulation.py`

- [ ] **Step 1: Write the failing test**

```python
import simpy
import networkx as nx
import pandas as pd
from src.simulation import MineSimulation
from src.config import Config
from src.topology import build_graph

def test_simulation_init():
    env = simpy.Environment()
    config = Config("test", 8, 1, 123, 1)
    
    nodes = pd.DataFrame([
        {"node_id": "CRUSH", "node_type": "crusher", "capacity": 1, "service_time_mean_min": 3.0, "service_time_sd_min": 0.5}
    ])
    edges = pd.DataFrame([
        {"edge_id": "E1", "from_node": "A", "to_node": "B", "distance_m": 100, "max_speed_kph": 10, "capacity": 1}
    ])
    
    G = build_graph(nodes, edges)
    sim = MineSimulation(env, config, G, 1)
    
    # Should have instantiated resources
    assert "CRUSH" in sim.resources
    assert "E1" in sim.edge_resources
    assert sim.resources["CRUSH"].capacity == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_simulation.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
import simpy
import networkx as nx
from typing import Dict
from src.config import Config
from src.metrics import EventLogger, SimulationMetrics

class MineSimulation:
    def __init__(self, env: simpy.Environment, config: Config, graph: nx.DiGraph, replication: int):
        self.env = env
        self.config = config
        self.graph = graph
        self.replication = replication
        self.logger = EventLogger()
        self.metrics = SimulationMetrics()
        
        self.resources: Dict[str, simpy.Resource] = {}
        self.edge_resources: Dict[str, simpy.Resource] = {}
        
        self._init_resources()
        
    def _init_resources(self):
        # Init node resources (loaders, crushers)
        for node_id, data in self.graph.nodes(data=True):
            if pd.notna(data.get('capacity')):
                cap = int(data['capacity'])
                self.resources[node_id] = simpy.Resource(self.env, capacity=cap)
                
        # Init edge resources (narrow ramps)
        for u, v, data in self.graph.edges(data=True):
            if pd.notna(data.get('capacity')) and data['capacity'] < 999:
                self.edge_resources[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))
```

*(Note: We need to update `src/simulation.py` with `import pandas as pd` since it's used in `pd.notna`)*

- [ ] **Step 4: Fix implementation and Run test to verify it passes**

```python
import simpy
import networkx as nx
import pandas as pd
from typing import Dict
from src.config import Config
from src.metrics import EventLogger, SimulationMetrics

class MineSimulation:
    def __init__(self, env: simpy.Environment, config: Config, graph: nx.DiGraph, replication: int):
        self.env = env
        self.config = config
        self.graph = graph
        self.replication = replication
        self.logger = EventLogger()
        self.metrics = SimulationMetrics()
        
        self.resources: Dict[str, simpy.Resource] = {}
        self.edge_resources: Dict[str, simpy.Resource] = {}
        
        self._init_resources()
        
    def _init_resources(self):
        for node_id, data in self.graph.nodes(data=True):
            if pd.notna(data.get('capacity')):
                cap = int(data['capacity'])
                self.resources[node_id] = simpy.Resource(self.env, capacity=cap)
                
        for u, v, data in self.graph.edges(data=True):
            if pd.notna(data.get('capacity')) and data['capacity'] < 999:
                self.edge_resources[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))
```

Run: `pytest tests/test_simulation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_simulation.py src/simulation.py
git commit -m "feat: core simulation environment and resources"
```

---

### Task 5: Truck Process and Routing

**Files:**
- Create: `src/truck.py`
- Modify: `tests/test_simulation.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_simulation.py
from src.truck import get_shortest_path_time, choose_best_loader

def test_routing():
    G = nx.DiGraph()
    G.add_edge("A", "B", distance_m=1000, max_speed_kph=30) # 2 mins
    G.add_edge("B", "C", distance_m=500, max_speed_kph=30)  # 1 min
    
    time = get_shortest_path_time(G, "A", "C", 1.0)
    assert time == 3.0
    
    path = nx.shortest_path(G, "A", "C")
    assert path == ["A", "B", "C"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_simulation.py::test_routing -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/truck.py
import networkx as nx
from src.topology import get_base_travel_time
from src.simulation import MineSimulation

def get_shortest_path_time(graph: nx.DiGraph, start: str, end: str, speed_factor: float) -> float:
    # Custom weight function
    def weight(u, v, d):
        base = get_base_travel_time(d['distance_m'], d['max_speed_kph'])
        return base / speed_factor
        
    try:
        return nx.shortest_path_length(graph, start, end, weight=weight)
    except nx.NetworkXNoPath:
        return float('inf')

def choose_best_loader(sim: MineSimulation, current_node: str, loaders: list[str], speed_factor: float) -> str:
    best_loader = None
    min_expected_time = float('inf')
    
    for loader in loaders:
        travel_time = get_shortest_path_time(sim.graph, current_node, loader, speed_factor)
        
        # Estimate wait time: queue length * mean service time
        queue_len = len(sim.resources[loader].queue)
        mean_service = sim.graph.nodes[loader].get('service_time_mean_min', 5.0)
        expected_wait = (queue_len + 1) * mean_service
        
        total_time = travel_time + expected_wait
        if total_time < min_expected_time:
            min_expected_time = total_time
            best_loader = loader
            
    return best_loader
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_simulation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_simulation.py src/truck.py src/topology.py
git commit -m "feat: truck routing logic"
```

---

### Task 6: The Full Truck Cycle

**Files:**
- Modify: `src/truck.py`

- [ ] **Step 1: Write the complex implementation**
*(Because SimPy processes are hard to unit test in isolation, we will implement the full cycle generator function here, ensuring it yields events properly).*

```python
# src/truck.py (append)
import random
import scipy.stats as stats

def get_truncated_normal(mean, sd, lower=0):
    if sd == 0:
        return mean
    a = (lower - mean) / sd
    return stats.truncnorm(a, float('inf'), loc=mean, scale=sd).rvs()

def truck_process(env, sim, truck_id, start_node, payload_capacity, empty_speed, loaded_speed):
    current_node = start_node
    loaders = [n for n, d in sim.graph.nodes(data=True) if d.get('node_type') == 'load_ore']
    
    while True:
        cycle_start = env.now
        
        # 1. Choose loader & travel
        target_loader = choose_best_loader(sim, current_node, loaders, empty_speed)
        if not target_loader:
            yield env.timeout(1) # wait if nowhere to go
            continue
            
        path = nx.shortest_path(sim.graph, current_node, target_loader)
        
        # Traverse path
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = sim.graph.edges[u, v]
            edge_id = edge_data['edge_id']
            
            base_t = get_base_travel_time(edge_data['distance_m'], edge_data['max_speed_kph']) / empty_speed
            actual_t = get_truncated_normal(base_t, base_t * sim.config.stochasticity_cv if hasattr(sim.config, 'stochasticity_cv') else 0)
            
            # Request edge capacity if constrained
            if edge_id in sim.edge_resources:
                with sim.edge_resources[edge_id].request() as req:
                    yield req
                    sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "enter_edge", u, v, edge_id, False, 0, edge_id, 0)
                    yield env.timeout(actual_t)
            else:
                yield env.timeout(actual_t)
                
        current_node = target_loader
        
        # 2. Queue & Load
        arrive_time = env.now
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "arrive_loader", current_node, "", current_node, False, 0, current_node, len(sim.resources[current_node].queue))
        
        with sim.resources[current_node].request() as req:
            yield req
            wait_time = env.now - arrive_time
            sim.metrics.record_queue_time('loader', wait_time)
            
            mean_lt = sim.graph.nodes[current_node].get('service_time_mean_min', 5.0)
            sd_lt = sim.graph.nodes[current_node].get('service_time_sd_min', 1.0)
            load_t = get_truncated_normal(mean_lt, sd_lt)
            yield env.timeout(load_t)
            
        # 3. Travel Loaded to Crusher
        path = nx.shortest_path(sim.graph, current_node, "CRUSH")
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = sim.graph.edges[u, v]
            edge_id = edge_data['edge_id']
            base_t = get_base_travel_time(edge_data['distance_m'], edge_data['max_speed_kph']) / loaded_speed
            actual_t = get_truncated_normal(base_t, base_t * sim.config.stochasticity_cv if hasattr(sim.config, 'stochasticity_cv') else 0)
            
            if edge_id in sim.edge_resources:
                with sim.edge_resources[edge_id].request() as req:
                    yield req
                    yield env.timeout(actual_t)
            else:
                yield env.timeout(actual_t)
                
        current_node = "CRUSH"
        
        # 4. Queue & Dump
        arrive_time = env.now
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "arrive_crusher", current_node, "", current_node, True, payload_capacity, current_node, len(sim.resources[current_node].queue))
        
        with sim.resources[current_node].request() as req:
            yield req
            wait_time = env.now - arrive_time
            sim.metrics.record_queue_time('crusher', wait_time)
            
            mean_dt = sim.graph.nodes[current_node].get('service_time_mean_min', 3.5)
            sd_dt = sim.graph.nodes[current_node].get('service_time_sd_min', 0.8)
            dump_t = get_truncated_normal(mean_dt, sd_dt)
            yield env.timeout(dump_t)
            
        sim.metrics.record_cycle(truck_id, env.now - cycle_start, payload_capacity)
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "finish_dump", current_node, "", current_node, False, 0, current_node, 0)
```

- [ ] **Step 2: Commit**

```bash
git add src/truck.py
git commit -m "feat: complete truck simulation cycle process"
```

---

### Task 7: Output Generation and Summarization

**Files:**
- Create: `src/output.py`

- [ ] **Step 1: Write the minimal implementation**

```python
import json
import pandas as pd
import numpy as np
import scipy.stats as st
from typing import List
from pathlib import Path

def calculate_ci(data: list, confidence=0.95):
    if not data or len(data) < 2:
        return np.mean(data) if data else 0, 0, 0
    a = 1.0 * np.array(data)
    m, se = np.mean(a), st.sem(a)
    h = se * st.t.ppf((1 + confidence) / 2., len(a)-1)
    return m, m-h, m+h

def generate_summary(metrics_list: List['SimulationMetrics'], config: 'Config', output_path: Path):
    tonnes = [m.total_tonnes for m in metrics_list]
    tph = [m.total_tonnes / config.shift_length_hours for m in metrics_list]
    cycles = [np.mean(m.cycle_times) if m.cycle_times else 0 for m in metrics_list]
    
    t_m, t_l, t_h = calculate_ci(tonnes)
    tph_m, tph_l, tph_h = calculate_ci(tph)
    
    summary = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {
            config.scenario_id: {
                "replications": config.replications,
                "shift_length_hours": config.shift_length_hours,
                "total_tonnes_mean": float(t_m),
                "total_tonnes_ci95_low": float(t_l),
                "total_tonnes_ci95_high": float(t_h),
                "tonnes_per_hour_mean": float(tph_m),
                "tonnes_per_hour_ci95_low": float(tph_l),
                "tonnes_per_hour_ci95_high": float(tph_h),
                "average_cycle_time_min": float(np.mean(cycles)),
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
```

- [ ] **Step 2: Commit**

```bash
git add src/output.py
git commit -m "feat: JSON summary generation and CI calculation"
```

---

### Task 8: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main execution loop**

```python
import argparse
import random
import simpy
from pathlib import Path
from src.config import load_scenario, load_csv_data
from src.topology import build_graph
from src.simulation import MineSimulation
from src.truck import truck_process
from src.output import generate_summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=str, required=True, help="Path to scenario yaml")
    parser.add_argument('--data-dir', type=str, default='data', help="Path to data dir")
    parser.add_argument('--out-dir', type=str, default='.', help="Output directory")
    args = parser.parse_args()
    
    config = load_scenario(Path(args.scenario))
    config.stochasticity_cv = 0.10 # Hardcoded fallback if not in yaml
    
    nodes = load_csv_data(Path(args.data_dir) / 'nodes.csv')
    edges = load_csv_data(Path(args.data_dir) / 'edges.csv')
    trucks_df = load_csv_data(Path(args.data_dir) / 'trucks.csv')
    
    G = build_graph(nodes, edges)
    
    all_metrics = []
    
    for rep in range(config.replications):
        random.seed(config.base_random_seed + rep)
        env = simpy.Environment()
        sim = MineSimulation(env, config, G, rep)
        
        # Spawn trucks based on config (up to fleet limit in csv)
        truck_configs = trucks_df.head(config.truck_count).to_dict('records')
        for tc in truck_configs:
            env.process(truck_process(
                env, sim, tc['truck_id'], tc['start_node'], 
                tc['payload_tonnes'], tc['empty_speed_factor'], tc['loaded_speed_factor']
            ))
            
        env.run(until=config.shift_length_hours * 60)
        all_metrics.append(sim.metrics)
        print(f"Replication {rep+1}/{config.replications} finished. Tonnes: {sim.metrics.total_tonnes}")
        
    generate_summary(all_metrics, config, Path(args.out_dir) / 'summary.json')
    print("Done!")

if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: main execution script"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-04-29-synthetic-mine-throughput.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?