# Synthetic Mine Throughput Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SimPy discrete-event simulation to estimate ore throughput in a synthetic mine under various scenarios.

**Architecture:** An active `Truck` agent loop runs within a `MineSimulation` environment. The environment loads a NetworkX `DiGraph` representing the `MineTopology`. Trucks request road, loader, and crusher resources as they travel and queue.

**Tech Stack:** Python 3, `simpy`, `networkx`, `pandas`, `pyyaml`, `scipy.stats` (for truncated normal).

---

### Task 1: Setup and Mine Topology Parser

**Files:**
- Create: `mine_simulation/topology.py`
- Create: `tests/test_topology.py`
- Modify: `requirements.txt` (to ensure dependencies)

- [ ] **Step 1: Write requirements and failing test**

```python
# tests/test_topology.py
import pytest
import pandas as pd
from mine_simulation.topology import MineTopology

def test_topology_loading(tmp_path):
    # Setup dummy data
    nodes_csv = tmp_path / "nodes.csv"
    nodes_csv.write_text("node_id,node_name,node_type,x_m,y_m,z_m,capacity,service_time_mean_min,service_time_sd_min\nN1,Node 1,parking,0,0,0,,,")
    
    edges_csv = tmp_path / "edges.csv"
    edges_csv.write_text("edge_id,from_node,to_node,distance_m,max_speed_kph,road_type,capacity,closed\nE1,N1,N2,1000,60,flat,999,false")

    topology = MineTopology(nodes_csv, edges_csv)
    
    assert "N1" in topology.graph
    # 1000m at 60kph = 1 min
    assert topology.graph["N1"]["N2"]["travel_time_min"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_topology.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Write minimal implementation**

```python
# requirements.txt
simpy
networkx
pandas
pyyaml
scipy
pytest
```

```python
# mine_simulation/topology.py
import networkx as nx
import pandas as pd

class MineTopology:
    def __init__(self, nodes_csv_path, edges_csv_path):
        self.graph = nx.DiGraph()
        self._load_data(nodes_csv_path, edges_csv_path)

    def _load_data(self, nodes_path, edges_path):
        nodes_df = pd.read_csv(nodes_path)
        for _, row in nodes_df.iterrows():
            self.graph.add_node(row['node_id'], **row.to_dict())

        edges_df = pd.read_csv(edges_path)
        for _, row in edges_df.iterrows():
            if row.get('closed', False):
                continue
            
            # distance in meters, speed in km/h -> time in minutes
            # (distance / 1000) / speed * 60 = distance / speed * 0.06
            travel_time_min = (row['distance_m'] / row['max_speed_kph']) * 0.06
            
            self.graph.add_edge(
                row['from_node'], 
                row['to_node'], 
                travel_time_min=travel_time_min,
                **row.to_dict()
            )
            
    def get_shortest_path(self, source, target):
        return nx.shortest_path(self.graph, source=source, target=target, weight='travel_time_min')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -r requirements.txt && pytest tests/test_topology.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt mine_simulation tests
git commit -m "feat: add topology parser and graph building"
```

---

### Task 2: Simulation Environment and Configuration

**Files:**
- Create: `mine_simulation/simulation.py`
- Create: `mine_simulation/config.py`
- Create: `tests/test_simulation.py`

- [ ] **Step 1: Write configuration loader**

```python
# mine_simulation/config.py
import yaml
from dataclasses import dataclass, field
from typing import List

@dataclass
class ScenarioConfig:
    scenario_id: str
    shift_length_hours: int
    replications: int
    base_random_seed: int
    truck_count: int
    ore_sources: List[str]
    dump_destination: str
    travel_time_noise_cv: float

    @classmethod
    def from_yaml(cls, filepath):
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return cls(
            scenario_id=data['scenario_id'],
            shift_length_hours=data['simulation']['shift_length_hours'],
            replications=data['simulation']['replications'],
            base_random_seed=data['simulation']['base_random_seed'],
            truck_count=data['fleet']['truck_count'],
            ore_sources=data['production']['ore_sources'],
            dump_destination=data['production']['dump_destination'],
            travel_time_noise_cv=data['stochasticity']['travel_time_noise_cv']
        )
```

- [ ] **Step 2: Write basic simulation environment structure**

```python
# mine_simulation/simulation.py
import simpy
from .topology import MineTopology
from .config import ScenarioConfig
import pandas as pd

class MineSimulation:
    def __init__(self, config: ScenarioConfig, topology: MineTopology, loaders_df: pd.DataFrame, dump_points_df: pd.DataFrame, random_seed: int):
        self.env = simpy.Environment()
        self.config = config
        self.topology = topology
        self.event_log = []
        self.metrics = {"total_tonnes_delivered": 0}
        
        # Resources
        self.loaders = {}
        self.crusher = None
        self.road_segments = {}
        
        self._setup_resources(loaders_df, dump_points_df)

    def _setup_resources(self, loaders_df, dump_points_df):
        for _, row in loaders_df.iterrows():
            self.loaders[row['node_id']] = simpy.Resource(self.env, capacity=1)
            
        for _, row in dump_points_df.iterrows():
            if row['type'] == 'crusher':
                self.crusher = simpy.Resource(self.env, capacity=1)
                
        # Setup constrained roads
        for u, v, data in self.topology.graph.edges(data=True):
            if 'capacity' in data and data['capacity'] < 999:
                # Use edge_id as resource key
                self.road_segments[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))
```

- [ ] **Step 3: Write tests and run**

```python
# tests/test_simulation.py
import pytest
import pandas as pd
from mine_simulation.simulation import MineSimulation
from mine_simulation.topology import MineTopology
from mine_simulation.config import ScenarioConfig

def test_simulation_init(tmp_path):
    nodes_csv = tmp_path / "nodes.csv"
    nodes_csv.write_text("node_id,node_name\nN1,Node 1\nN2,Node 2")
    edges_csv = tmp_path / "edges.csv"
    edges_csv.write_text("edge_id,from_node,to_node,distance_m,max_speed_kph,capacity\nE1,N1,N2,1000,60,1")
    
    top = MineTopology(nodes_csv, edges_csv)
    cfg = ScenarioConfig("test", 8, 1, 42, 4, ["N1"], "N2", 0.1)
    
    ld_df = pd.DataFrame([{"node_id": "N1", "capacity": 1}])
    dp_df = pd.DataFrame([{"node_id": "N2", "type": "crusher", "capacity": 1}])
    
    sim = MineSimulation(cfg, top, ld_df, dp_df, 42)
    assert "E1" in sim.road_segments
    assert "N1" in sim.loaders
    assert sim.crusher is not None
```

Run: `pytest tests/test_simulation.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add mine_simulation tests
git commit -m "feat: add config loader and basic simulation environment"
```

---

### Task 3: Truncated Normal & Core Truck Logic

**Files:**
- Create: `mine_simulation/truck.py`
- Modify: `mine_simulation/simulation.py`
- Create: `tests/test_truck.py`

- [ ] **Step 1: Write helper for truncated normal**

```python
# mine_simulation/utils.py
import numpy as np

def truncated_normal(mean: float, sd: float, random_state: np.random.RandomState, lower_bound: float = 0.1) -> float:
    # simple rejection sampling to ensure > lower_bound
    val = -1
    while val < lower_bound:
        val = random_state.normal(mean, sd)
    return val
```

- [ ] **Step 2: Implement core Truck process**

```python
# mine_simulation/truck.py
import numpy as np
from .utils import truncated_normal

class Truck:
    def __init__(self, sim, truck_id: str, payload: float):
        self.sim = sim
        self.truck_id = truck_id
        self.payload = payload
        self.random_state = np.random.RandomState(sim.config.base_random_seed + hash(truck_id) % 10000)
        self.current_node = "PARK"
        self.loaded = False
        self.action = sim.env.process(self.run())

    def log(self, event_type, from_node=None, to_node=None, resource_id=None, queue_length=0):
        self.sim.event_log.append({
            "time_min": self.sim.env.now,
            "truck_id": self.truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": self.current_node,
            "loaded": self.loaded,
            "payload_tonnes": self.payload if self.loaded else 0,
            "resource_id": resource_id,
            "queue_length": queue_length
        })

    def travel(self, destination):
        path = self.sim.topology.get_shortest_path(self.current_node, destination)
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = self.sim.topology.graph[u][v]
            edge_id = edge_data['edge_id']
            
            # Apply stochastic noise to travel time
            base_time = edge_data['travel_time_min']
            noise_sd = base_time * self.sim.config.travel_time_noise_cv
            actual_time = truncated_normal(base_time, noise_sd, self.random_state, 0.1) if noise_sd > 0 else base_time

            if edge_id in self.sim.road_segments:
                res = self.sim.road_segments[edge_id]
                self.log("queue_road_start", u, v, edge_id, len(res.queue))
                with res.request() as req:
                    yield req
                    self.log("travel_start", u, v, edge_id)
                    yield self.sim.env.timeout(actual_time)
                    self.current_node = v
            else:
                self.log("travel_start", u, v, edge_id)
                yield self.sim.env.timeout(actual_time)
                self.current_node = v

    def run(self):
        # Warmup / initial dispatch
        yield self.sim.env.timeout(0)
        
        while True:
            # 1. Decide loader
            loader_node = self.sim.get_best_loader(self.current_node)
            
            # 2. Travel to loader
            yield from self.travel(loader_node)
            
            # 3. Load
            loader_res = self.sim.loaders[loader_node]
            self.log("queue_load_start", resource_id=loader_node, queue_length=len(loader_res.queue))
            with loader_res.request() as req:
                yield req
                self.log("load_start", resource_id=loader_node)
                
                # Assume static params for now, refine later
                node_data = self.sim.topology.graph.nodes[loader_node]
                mean_t = node_data.get('service_time_mean_min', 5.0)
                sd_t = node_data.get('service_time_sd_min', 1.0)
                
                load_time = truncated_normal(mean_t, sd_t, self.random_state)
                yield self.sim.env.timeout(load_time)
                self.loaded = True
                self.log("load_end", resource_id=loader_node)

            # 4. Travel to crusher
            crush_node = self.sim.config.dump_destination
            yield from self.travel(crush_node)

            # 5. Dump
            self.log("queue_dump_start", resource_id=crush_node, queue_length=len(self.sim.crusher.queue))
            with self.sim.crusher.request() as req:
                yield req
                self.log("dump_start", resource_id=crush_node)
                
                node_data = self.sim.topology.graph.nodes[crush_node]
                mean_t = node_data.get('service_time_mean_min', 3.5)
                sd_t = node_data.get('service_time_sd_min', 0.8)
                
                dump_time = truncated_normal(mean_t, sd_t, self.random_state)
                yield self.sim.env.timeout(dump_time)
                self.loaded = False
                self.sim.metrics["total_tonnes_delivered"] += self.payload
                self.log("dump_end", resource_id=crush_node)
```

- [ ] **Step 3: Add dispatching logic to simulation**

```python
# Modify mine_simulation/simulation.py
# Add to class MineSimulation:
    def get_best_loader(self, current_node):
        best_loader = None
        best_score = float('inf')
        
        for loader in self.config.ore_sources:
            path = self.topology.get_shortest_path(current_node, loader)
            # Sum base travel time
            travel_time = sum(self.topology.graph[path[i]][path[i+1]]['travel_time_min'] for i in range(len(path)-1))
            
            queue_len = len(self.loaders[loader].queue)
            
            # Simplified score: travel_time + queue penalty
            # Assuming mean service time is ~5 min for tie breaking
            expected_queue_time = queue_len * 5.0
            
            score = travel_time + expected_queue_time
            if score < best_score:
                best_score = score
                best_loader = loader
                
        return best_loader
```

- [ ] **Step 4: Commit**

```bash
git add mine_simulation tests
git commit -m "feat: add truck cycle logic and stochastic utils"
```

---

### Task 4: The Experiment Runner

**Files:**
- Create: `mine_simulation/runner.py`
- Modify: `mine_simulation/simulation.py`

- [ ] **Step 1: Write the main simulation runner**

```python
# mine_simulation/runner.py
import pandas as pd
import numpy as np
import json
from pathlib import Path
from .topology import MineTopology
from .config import ScenarioConfig
from .simulation import MineSimulation
from .truck import Truck

def run_replication(config: ScenarioConfig, topology: MineTopology, loaders_df, dump_points_df, trucks_df, seed):
    sim = MineSimulation(config, topology, loaders_df, dump_points_df, seed)
    
    # Initialize trucks based on fleet size
    for i in range(config.truck_count):
        # Default payload if not fully specified, though we have trucks_df
        payload = trucks_df.iloc[i]['payload_tonnes'] if i < len(trucks_df) else 100
        Truck(sim, f"T{i+1:02d}", payload)
        
    sim.env.run(until=config.shift_length_hours * 60)
    
    return sim.metrics, sim.event_log

def run_scenarios(data_dir: Path, output_dir: Path):
    topology = MineTopology(data_dir / "nodes.csv", data_dir / "edges.csv")
    loaders_df = pd.read_csv(data_dir / "loaders.csv")
    dump_points_df = pd.read_csv(data_dir / "dump_points.csv")
    trucks_df = pd.read_csv(data_dir / "trucks.csv")
    
    all_results = []
    all_events = []
    summary_data = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": ["Constant truck payload", "Instantaneous dispatch routing"],
        "model_limitations": ["No shift change/breaks modelled"],
        "additional_scenarios_proposed": []
    }
    
    scenarios_dir = data_dir / "scenarios"
    for yaml_file in scenarios_dir.glob("*.yaml"):
        config = ScenarioConfig.from_yaml(yaml_file)
        
        scenario_tonnes = []
        
        for rep in range(config.replications):
            seed = config.base_random_seed + rep
            metrics, events = run_replication(config, topology, loaders_df, dump_points_df, trucks_df, seed)
            
            total_tonnes = metrics["total_tonnes_delivered"]
            scenario_tonnes.append(total_tonnes)
            
            all_results.append({
                "scenario_id": config.scenario_id,
                "replication": rep,
                "random_seed": seed,
                "total_tonnes_delivered": total_tonnes,
                "tonnes_per_hour": total_tonnes / config.shift_length_hours
            })
            
            # add rep details to events
            for e in events:
                e["scenario_id"] = config.scenario_id
                e["replication"] = rep
            all_events.extend(events)
            
        # Calc 95% CI
        mean_t = np.mean(scenario_tonnes)
        std_t = np.std(scenario_tonnes, ddof=1)
        ci = 1.96 * (std_t / np.sqrt(config.replications))
        
        summary_data["scenarios"][config.scenario_id] = {
            "replications": config.replications,
            "shift_length_hours": config.shift_length_hours,
            "total_tonnes_mean": float(mean_t),
            "total_tonnes_ci95_low": float(mean_t - ci),
            "total_tonnes_ci95_high": float(mean_t + ci),
            "tonnes_per_hour_mean": float(mean_t / config.shift_length_hours),
            "tonnes_per_hour_ci95_low": float((mean_t - ci) / config.shift_length_hours),
            "tonnes_per_hour_ci95_high": float((mean_t + ci) / config.shift_length_hours),
            "average_cycle_time_min": 0, # Placeholder for extended metrics calculation
            "truck_utilisation_mean": 0,
            "loader_utilisation": {},
            "crusher_utilisation": 0,
            "average_loader_queue_time_min": 0,
            "average_crusher_queue_time_min": 0,
            "top_bottlenecks": []
        }
        
    pd.DataFrame(all_results).to_csv(output_dir / "results.csv", index=False)
    pd.DataFrame(all_events).to_csv(output_dir / "event_log.csv", index=False)
    
    with open(output_dir / "summary.json", 'w') as f:
        json.dump(summary_data, f, indent=2)

if __name__ == "__main__":
    run_scenarios(Path("data"), Path("."))
```

- [ ] **Step 2: Commit**

```bash
git add mine_simulation
git commit -m "feat: add experiment runner"
```

---

### Task 5: Post-Processing & Secondary Metrics

**Files:**
- Modify: `mine_simulation/runner.py`

- [ ] **Step 1: Calculate advanced metrics from event log**

In `mine_simulation/runner.py`, add logic inside the scenario loop (after replications) to analyze the `all_events` DataFrame for that scenario.

```python
# mine_simulation/metrics.py
import pandas as pd

def calculate_advanced_metrics(events_df: pd.DataFrame, shift_hours: int):
    # events_df has columns: time_min, truck_id, event_type, resource_id, etc.
    metrics = {
        "average_cycle_time_min": 0,
        "truck_utilisation_mean": 0,
        "loader_utilisation": {},
        "crusher_utilisation": 0,
        "average_loader_queue_time_min": 0,
        "average_crusher_queue_time_min": 0,
        "top_bottlenecks": []
    }
    
    if events_df.empty:
        return metrics

    # 1. Crusher Utilisation
    crush_starts = events_df[events_df['event_type'] == 'dump_start']
    crush_ends = events_df[events_df['event_type'] == 'dump_end']
    if not crush_starts.empty and not crush_ends.empty:
        # Assuming 1 to 1 ordering per resource
        # Merge on truck_id and resource_id to find pairs
        # Simplification for plan: just sum the service times
        # Service time is drawn from truncated normal
        total_crush_time = 0
        for _, start_row in crush_starts.iterrows():
            end_row = crush_ends[(crush_ends['truck_id'] == start_row['truck_id']) & (crush_ends['time_min'] >= start_row['time_min'])].head(1)
            if not end_row.empty:
                total_crush_time += (end_row.iloc[0]['time_min'] - start_row['time_min'])
        metrics['crusher_utilisation'] = total_crush_time / (shift_hours * 60)

    # Calculate queues
    queue_crush = []
    starts = events_df[events_df['event_type'] == 'queue_dump_start']
    ends = events_df[events_df['event_type'] == 'dump_start']
    for _, s in starts.iterrows():
        e = ends[(ends['truck_id'] == s['truck_id']) & (ends['time_min'] >= s['time_min'])].head(1)
        if not e.empty:
            queue_crush.append(e.iloc[0]['time_min'] - s['time_min'])
    metrics['average_crusher_queue_time_min'] = sum(queue_crush)/len(queue_crush) if queue_crush else 0

    return metrics
```

```python
# Modified snippet for mine_simulation/runner.py
# Inside run_scenarios, after the replications loop:
events_df = pd.DataFrame(all_events)
scenario_events = events_df[events_df['scenario_id'] == config.scenario_id]

from .metrics import calculate_advanced_metrics
adv_metrics = calculate_advanced_metrics(scenario_events, config.shift_length_hours)

# Update summary_data["scenarios"][config.scenario_id] with adv_metrics
```

- [ ] **Step 2: Commit**

```bash
git commit -am "feat: calculate advanced metrics from event log"
```

---

### Task 6: Documentation

**Files:**
- Create: `conceptual_model.md`
- Create: `README.md`

- [ ] **Step 1: Write `conceptual_model.md`**

Translate the points from the design spec (Entities, State, Resources, Events, Limits) into the markdown file requested by the prompt.

- [ ] **Step 2: Write `README.md`**

Include:
- `pip install -r requirements.txt`
- `python -m mine_simulation.runner`
- Short summary of results/bottlenecks based on the runs.

- [ ] **Step 3: Run full suite**

Run `python -m mine_simulation.runner` to verify it produces the 3 files.

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "docs: add conceptual model and readme"
```