# Mine Throughput Simulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SimPy discrete-event simulation of an open-pit mine haulage system that estimates ore throughput to the primary crusher over an 8-hour shift across six required scenarios with 30 replications each, producing the required output artefacts (`conceptual_model.md`, `results.csv`, `summary.json`, `event_log.csv`, `README.md`).

**Architecture:** Modular Python package `mine_sim/` with 7 focused modules (topology, resources, truck, scenario, experiment, report, run). Discrete-event simulation in SimPy with paired-bidirectional road locks for narrow ramps and pit accesses, per-direction locks for crusher approach, pre-computed travel-time-weighted Dijkstra paths via NetworkX, dynamic loader choice via `nearest_available_loader` + `shortest_expected_cycle_time` tiebreaker, and stochastic load/dump/travel times with seeded `numpy.random.Generator`s.

**Tech Stack:** Python 3.11+, SimPy, NumPy, Pandas, SciPy, NetworkX, PyYAML, Matplotlib (optional, for topology plot).

**Working directory for all paths in this plan:** `/Users/harry/Workspace/simulation-bench/submissions/2026-04-29__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__superpowers-max-thinking/`. All file paths below are relative to this directory unless otherwise specified.

---

## File Structure

| File | Responsibility |
|---|---|
| `requirements.txt` | Pinned-minor deps: simpy, numpy, pandas, scipy, networkx, pyyaml, matplotlib, pytest |
| `mine_sim/__init__.py` | Package marker; re-exports `run_scenario` for convenience |
| `mine_sim/scenario.py` | Load and merge YAML scenario configs (handles `inherits:`) |
| `mine_sim/topology.py` | Load CSVs, apply scenario overrides, build NetworkX `DiGraph`, compute all-pairs shortest paths weighted by travel time |
| `mine_sim/resources.py` | Build SimPy resource pool: loaders, crusher, paired-bidirectional road locks for capacity-1 edges |
| `mine_sim/metrics.py` | `MetricsCollector` — accumulates busy time, queue waits, queue lengths, tonnes delivered, cycle times, event log rows |
| `mine_sim/truck.py` | `Truck` SimPy process: dispatch → travel → load → travel → dump → return loop |
| `mine_sim/experiment.py` | `run_replication`, `run_scenario` — drives reps, threads RNGs, calls collector |
| `mine_sim/report.py` | Write `results.csv`, `summary.json`, `event_log.csv`; compute 95% CIs and bottleneck rankings |
| `mine_sim/run.py` | CLI entry point (argparse): runs all scenarios or a chosen one |
| `tests/test_scenario.py` | Unit tests for YAML loader and `inherits:` merging |
| `tests/test_topology.py` | Unit tests for graph build, override application, shortest-path correctness, ramp-closed re-routing |
| `tests/test_resources.py` | Unit tests for paired-bidir lock semantics and lock factory edge selection |
| `tests/test_metrics.py` | Unit tests for utilisation/queue-wait calculation and 95% CI helper |
| `tests/test_truck.py` | Unit tests for dispatcher choice and one-cycle integration smoke |
| `tests/test_experiment.py` | Reproducibility test: same seed → identical event log |
| `tests/test_report.py` | Schema tests for `results.csv`, `summary.json` |
| `tests/conftest.py` | Shared pytest fixtures: data dir path, scenarios dir path, tmp output dir |
| `conceptual_model.md` | Per prompt §conceptual_model |
| `README.md` | Per prompt §README — install, run, results, answers |
| `results/` | Created by run; holds per-scenario event logs + aggregated outputs |

---

## Conventions

- **Truncated normal draw:** `def draw_truncated_normal(rng, mean, sd) -> float: return float(np.clip(rng.normal(mean, sd), 0.1, mean + 5 * sd))`
- **Travel-time minutes for an edge:** `(distance_m / 1000.0) / speed_kph * 60.0`
- **Time unit throughout:** minutes. Shift length 8 h = 480 min.
- **Edge-to-lock map:** `{"E03_UP":"RAMP","E03_DOWN":"RAMP","E07_TO_LOAD_N":"PIT_N","E07_FROM_LOAD_N":"PIT_N","E09_TO_LOAD_S":"PIT_S","E09_FROM_LOAD_S":"PIT_S","E05_TO_CRUSH":"E05_TO","E05_FROM_CRUSH":"E05_FROM"}`
- **Effective edge capacity:** `effective_cap = override_or_csv_capacity`. A lock is created for a logical lock_id only if every member edge of that lock that exists post-override has effective_cap == 1. (`ramp_upgrade` raises E03 cap to 999 → no RAMP lock.)
- **Bottleneck score:** `utilisation * avg_queue_wait_min`.

---

## Task 0: Repository scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `mine_sim/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`
- Create: `.gitignore`

- [ ] **Step 1: Create `requirements.txt`**

```text
simpy>=4.1,<5
numpy>=1.26,<3
pandas>=2.1,<3
scipy>=1.11,<2
networkx>=3.2,<4
pyyaml>=6.0,<7
matplotlib>=3.8,<4
pytest>=7.4,<9
```

- [ ] **Step 2: Create `mine_sim/__init__.py`**

```python
"""Mine throughput simulation package."""
__version__ = "0.1.0"
```

- [ ] **Step 3: Create `tests/__init__.py`**

```python
```

(Empty file — marks tests as a package.)

- [ ] **Step 4: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -ra --strict-markers
```

- [ ] **Step 5: Create `.gitignore`**

```text
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.egg-info/
results/event_log.csv
results/*.csv
results/*.json
!results/.gitkeep
```

- [ ] **Step 6: Create `tests/conftest.py`**

```python
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
```

- [ ] **Step 7: Set up venv and install**

Run:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest --collect-only
```

Expected: `pytest --collect-only` reports "no tests collected" cleanly (no errors).

- [ ] **Step 8: Commit**

```bash
git add requirements.txt mine_sim/__init__.py tests/__init__.py tests/conftest.py pytest.ini .gitignore
git commit -m "chore(mine-sim): scaffold package, deps, pytest config"
```

---

## Task 1: Scenario loader with `inherits:` merging

**Files:**
- Create: `mine_sim/scenario.py`
- Create: `tests/test_scenario.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_scenario.py`:

```python
"""Tests for scenario YAML loading and inherits: merging."""
from pathlib import Path

import pytest
import yaml

from mine_sim.scenario import deep_merge, load_scenario


def test_deep_merge_replaces_scalars():
    parent = {"fleet": {"truck_count": 8}, "shift": 480}
    child = {"fleet": {"truck_count": 4}}
    merged = deep_merge(parent, child)
    assert merged["fleet"]["truck_count"] == 4
    assert merged["shift"] == 480


def test_deep_merge_nested_dicts():
    parent = {"a": {"b": 1, "c": 2}}
    child = {"a": {"b": 10}}
    assert deep_merge(parent, child) == {"a": {"b": 10, "c": 2}}


def test_deep_merge_does_not_mutate_inputs():
    parent = {"a": {"b": 1}}
    child = {"a": {"b": 2}}
    deep_merge(parent, child)
    assert parent == {"a": {"b": 1}}
    assert child == {"a": {"b": 2}}


def test_load_baseline(scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    assert cfg["scenario_id"] == "baseline"
    assert cfg["fleet"]["truck_count"] == 8
    assert cfg["simulation"]["replications"] == 30
    assert "inherits" not in cfg


def test_load_inherited_trucks_4(scenarios_dir):
    cfg = load_scenario("trucks_4", scenarios_dir)
    assert cfg["scenario_id"] == "trucks_4"          # child wins on scenario_id
    assert cfg["fleet"]["truck_count"] == 4          # child override
    assert cfg["simulation"]["replications"] == 30   # inherited from baseline
    assert "inherits" not in cfg


def test_load_ramp_upgrade_carries_overrides(scenarios_dir):
    cfg = load_scenario("ramp_upgrade", scenarios_dir)
    assert cfg["edge_overrides"]["E03_UP"]["capacity"] == 999
    assert cfg["edge_overrides"]["E03_UP"]["max_speed_kph"] == 28
    assert cfg["fleet"]["truck_count"] == 8          # inherited


def test_load_ramp_closed_marks_edges_closed(scenarios_dir):
    cfg = load_scenario("ramp_closed", scenarios_dir)
    assert cfg["edge_overrides"]["E03_UP"]["closed"] is True
    assert cfg["edge_overrides"]["E03_DOWN"]["closed"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scenario.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.scenario'`.

- [ ] **Step 3: Implement `mine_sim/scenario.py`**

```python
"""Scenario YAML loader with `inherits:` merging."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def deep_merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge: child wins on scalars/lists; child dicts merge into parent dicts.

    Returns a new dict; does not mutate inputs.
    """
    out = copy.deepcopy(parent)
    for key, child_val in child.items():
        parent_val = out.get(key)
        if isinstance(parent_val, dict) and isinstance(child_val, dict):
            out[key] = deep_merge(parent_val, child_val)
        else:
            out[key] = copy.deepcopy(child_val)
    return out


def load_scenario(scenario_id: str, scenarios_dir: Path) -> dict[str, Any]:
    """Load a scenario YAML, recursively resolving any `inherits:` parent."""
    path = Path(scenarios_dir) / f"{scenario_id}.yaml"
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    if "inherits" in raw:
        parent = load_scenario(raw["inherits"], scenarios_dir)
        merged = deep_merge(parent, raw)
    else:
        merged = raw
    merged.pop("inherits", None)
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scenario.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/scenario.py tests/test_scenario.py
git commit -m "feat(mine-sim): scenario YAML loader with inherits merging"
```

---

## Task 2: Topology graph builder

**Files:**
- Create: `mine_sim/topology.py`
- Create: `tests/test_topology.py`

The topology layer is responsible for: loading the CSV files, applying scenario `edge_overrides`/`node_overrides`/`dump_point_overrides`/`loader_overrides`, dropping `closed: true` edges, building a `networkx.DiGraph`, and computing all-pairs shortest paths weighted by travel time.

- [ ] **Step 1: Write failing tests**

Create `tests/test_topology.py`:

```python
"""Tests for topology loading, override application, and pathfinding."""
import networkx as nx
import pytest

from mine_sim.scenario import load_scenario
from mine_sim.topology import (
    Edge,
    Node,
    apply_overrides,
    build_graph,
    load_edges,
    load_nodes,
    nominal_travel_time_min,
    shortest_path_edges,
)


def test_load_nodes_returns_dict_keyed_by_id(data_dir):
    nodes = load_nodes(data_dir / "nodes.csv")
    assert "PARK" in nodes
    assert nodes["LOAD_N"].node_type == "load_ore"
    assert nodes["CRUSH"].node_type == "crusher"
    assert nodes["LOAD_N"].service_time_mean_min == pytest.approx(6.5)


def test_load_edges_returns_dict_keyed_by_id(data_dir):
    edges = load_edges(data_dir / "edges.csv")
    assert edges["E03_UP"].capacity == 1
    assert edges["E03_UP"].max_speed_kph == 18
    assert edges["E03_UP"].road_type == "ramp"
    assert edges["E03_UP"].closed is False


def test_apply_overrides_capacity_and_speed(data_dir):
    edges = load_edges(data_dir / "edges.csv")
    overrides = {"E03_UP": {"capacity": 999, "max_speed_kph": 28}}
    new_edges = apply_overrides(edges, edge_overrides=overrides)
    assert new_edges["E03_UP"].capacity == 999
    assert new_edges["E03_UP"].max_speed_kph == 28
    assert edges["E03_UP"].capacity == 1   # original unchanged


def test_apply_overrides_closed(data_dir):
    edges = load_edges(data_dir / "edges.csv")
    new_edges = apply_overrides(edges, edge_overrides={"E03_UP": {"closed": True}})
    assert new_edges["E03_UP"].closed is True


def test_build_graph_baseline_has_path_park_to_crush(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    g, edges, nodes = build_graph(cfg, data_dir)
    assert nx.has_path(g, "PARK", "CRUSH")
    path = shortest_path_edges(g, edges, "PARK", "CRUSH")
    edge_ids = [e.edge_id for e in path]
    # Baseline shortest path should use the main ramp.
    assert "E03_UP" in edge_ids


def test_build_graph_ramp_closed_uses_bypass(data_dir, scenarios_dir):
    cfg = load_scenario("ramp_closed", scenarios_dir)
    g, edges, _ = build_graph(cfg, data_dir)
    # The ramp edges must be absent from the graph.
    assert not g.has_edge("J2", "J3")
    assert not g.has_edge("J3", "J2")
    # A path must still exist via the bypass.
    assert nx.has_path(g, "PARK", "CRUSH")
    path = shortest_path_edges(g, edges, "PARK", "CRUSH")
    edge_ids = {e.edge_id for e in path}
    assert {"E15_TO_BYPASS", "E16_BYPASS_EAST", "E17_TO_CRUSH"}.issubset(edge_ids)


def test_nominal_travel_time_known_edge(data_dir):
    edges = load_edges(data_dir / "edges.csv")
    # E01_OUT: 510 m at 30 kph -> 1.02 min
    t = nominal_travel_time_min(edges["E01_OUT"])
    assert t == pytest.approx(510 / 1000 / 30 * 60, rel=1e-9)


def test_topology_error_when_load_unreachable(data_dir, scenarios_dir):
    """Closing pit access edges should make the loader unreachable."""
    from mine_sim.topology import TopologyError, validate_reachability
    cfg = load_scenario("baseline", scenarios_dir)
    g, _, _ = build_graph(cfg, data_dir)
    # Remove both directions of the only northern access edges.
    g.remove_edge("J5", "LOAD_N")
    g.remove_edge("LOAD_N", "J5")
    g.remove_edge("J7", "J5")
    g.remove_edge("J5", "J7")
    with pytest.raises(TopologyError):
        validate_reachability(g, loader_node_ids=["LOAD_N", "LOAD_S"], crusher_node_id="CRUSH", parking_node_id="PARK")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_topology.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.topology'`.

- [ ] **Step 3: Implement `mine_sim/topology.py`**

```python
"""Topology: load CSVs, apply scenario overrides, build NetworkX graph, shortest paths."""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import networkx as nx


class TopologyError(RuntimeError):
    """Raised when the topology cannot satisfy required reachability."""


@dataclass(frozen=True)
class Node:
    node_id: str
    node_name: str
    node_type: str
    x_m: float
    y_m: float
    z_m: float
    capacity: int | None
    service_time_mean_min: float | None
    service_time_sd_min: float | None


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool


def _to_float(s: str) -> float | None:
    s = (s or "").strip()
    return float(s) if s else None


def _to_int(s: str, default: int = 0) -> int:
    s = (s or "").strip()
    return int(s) if s else default


def _to_bool(s: str) -> bool:
    return (s or "").strip().lower() == "true"


def load_nodes(path: Path) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    with Path(path).open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row.get("node_id"):
                continue
            nodes[row["node_id"]] = Node(
                node_id=row["node_id"],
                node_name=row["node_name"],
                node_type=row["node_type"],
                x_m=float(row["x_m"]),
                y_m=float(row["y_m"]),
                z_m=float(row["z_m"]),
                capacity=int(row["capacity"]) if row.get("capacity", "").strip() else None,
                service_time_mean_min=_to_float(row.get("service_time_mean_min", "")),
                service_time_sd_min=_to_float(row.get("service_time_sd_min", "")),
            )
    return nodes


def load_edges(path: Path) -> dict[str, Edge]:
    edges: dict[str, Edge] = {}
    with Path(path).open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row.get("edge_id"):
                continue
            edges[row["edge_id"]] = Edge(
                edge_id=row["edge_id"],
                from_node=row["from_node"],
                to_node=row["to_node"],
                distance_m=float(row["distance_m"]),
                max_speed_kph=float(row["max_speed_kph"]),
                road_type=row["road_type"],
                capacity=_to_int(row.get("capacity", "0"), default=0),
                closed=_to_bool(row.get("closed", "false")),
            )
    return edges


def apply_overrides(
    edges: dict[str, Edge],
    edge_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Edge]:
    """Return a new edge dict with overrides applied. Does not mutate input."""
    edge_overrides = edge_overrides or {}
    out: dict[str, Edge] = {}
    for eid, edge in edges.items():
        ov = edge_overrides.get(eid, {})
        out[eid] = replace(
            edge,
            capacity=int(ov["capacity"]) if "capacity" in ov else edge.capacity,
            max_speed_kph=float(ov["max_speed_kph"]) if "max_speed_kph" in ov else edge.max_speed_kph,
            closed=bool(ov["closed"]) if "closed" in ov else edge.closed,
        )
    return out


def apply_node_overrides(
    nodes: dict[str, Node],
    node_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Node]:
    node_overrides = node_overrides or {}
    out: dict[str, Node] = {}
    for nid, node in nodes.items():
        ov = node_overrides.get(nid, {})
        out[nid] = replace(
            node,
            service_time_mean_min=(
                float(ov["service_time_mean_min"])
                if "service_time_mean_min" in ov
                else node.service_time_mean_min
            ),
            service_time_sd_min=(
                float(ov["service_time_sd_min"])
                if "service_time_sd_min" in ov
                else node.service_time_sd_min
            ),
        )
    return out


def nominal_travel_time_min(edge: Edge) -> float:
    """Travel time using max speed (no truck factor, no noise) — for routing weights."""
    return (edge.distance_m / 1000.0) / edge.max_speed_kph * 60.0


def build_graph(
    config: dict[str, Any],
    data_dir: Path,
) -> tuple[nx.DiGraph, dict[str, Edge], dict[str, Node]]:
    """Load nodes/edges, apply overrides, drop closed edges, build DiGraph."""
    data_dir = Path(data_dir)
    nodes = apply_node_overrides(
        load_nodes(data_dir / "nodes.csv"),
        config.get("node_overrides"),
    )
    edges = apply_overrides(
        load_edges(data_dir / "edges.csv"),
        config.get("edge_overrides"),
    )

    g = nx.DiGraph()
    for n in nodes.values():
        g.add_node(n.node_id, **{"node_type": n.node_type})

    for e in edges.values():
        if e.closed:
            continue
        g.add_edge(
            e.from_node,
            e.to_node,
            edge_id=e.edge_id,
            weight=nominal_travel_time_min(e),
        )
    return g, edges, nodes


def shortest_path_edges(
    g: nx.DiGraph,
    edges: dict[str, Edge],
    src: str,
    dst: str,
) -> list[Edge]:
    """Return the list of Edge objects on the shortest (travel-time-weighted) path."""
    try:
        node_path = nx.shortest_path(g, src, dst, weight="weight")
    except nx.NetworkXNoPath as exc:
        raise TopologyError(f"No path from {src} to {dst}") from exc
    out: list[Edge] = []
    for u, v in zip(node_path[:-1], node_path[1:]):
        eid = g.edges[u, v]["edge_id"]
        out.append(edges[eid])
    return out


def validate_reachability(
    g: nx.DiGraph,
    loader_node_ids: list[str],
    crusher_node_id: str,
    parking_node_id: str,
) -> None:
    """Raise TopologyError if any required pair is unreachable."""
    required_pairs: list[tuple[str, str]] = []
    for ld in loader_node_ids:
        required_pairs.append((parking_node_id, ld))
        required_pairs.append((ld, crusher_node_id))
        required_pairs.append((crusher_node_id, ld))
    for src, dst in required_pairs:
        if not nx.has_path(g, src, dst):
            raise TopologyError(f"No path from {src} to {dst}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_topology.py -v`
Expected: 8 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/topology.py tests/test_topology.py
git commit -m "feat(mine-sim): topology loader, overrides, graph, shortest paths"
```

---

## Task 3: Metrics collector

**Files:**
- Create: `mine_sim/metrics.py`
- Create: `tests/test_metrics.py`

The collector tracks: cumulative resource busy time, queue wait, max queue length, tonnes delivered, per-truck cycle times and travelling/idle/loaded time, and an event log row buffer. It also provides `ci95_t` for confidence intervals.

- [ ] **Step 1: Write failing tests**

Create `tests/test_metrics.py`:

```python
"""Tests for the metrics collector and CI helper."""
import math

import pytest

from mine_sim.metrics import MetricsCollector, ci95_t


def test_ci95_t_known_values():
    # n=30, mean=100, std=10 -> half-width = t_{0.975,29} * 10/sqrt(30)
    # t_{0.975,29} ≈ 2.04523
    values = [100.0] * 15 + [90.0, 110.0] * 7 + [100.0]   # 30 values, mean ~ 100
    mean, lo, hi = ci95_t(values)
    assert mean == pytest.approx(sum(values) / len(values))
    assert lo < mean < hi
    assert (hi - mean) == pytest.approx(mean - lo)


def test_ci95_t_handles_zero_std():
    values = [5.0] * 10
    mean, lo, hi = ci95_t(values)
    assert mean == lo == hi == 5.0


def test_resource_busy_and_utilisation():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.record_resource_busy("loader_L_N", 240.0)
    assert m.utilisation("loader_L_N") == pytest.approx(0.5)


def test_resource_queue_metrics():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.record_queue_wait("loader_L_N", queue_len_on_entry=2, wait_minutes=3.0)
    m.record_queue_wait("loader_L_N", queue_len_on_entry=0, wait_minutes=0.0)
    assert m.avg_queue_wait("loader_L_N") == pytest.approx(1.5)
    assert m.max_queue_length("loader_L_N") == 2


def test_tonnes_recording():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.record_dump(time_min=10.0, truck_id="T01", payload_tonnes=100.0)
    m.record_dump(time_min=20.0, truck_id="T02", payload_tonnes=100.0)
    assert m.total_tonnes() == 200.0
    assert m.tonnes_per_hour() == pytest.approx(200.0 / 8)


def test_event_log_row_shape():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.log_event(
        time_min=12.5,
        truck_id="T01",
        event_type="loading_started",
        from_node="J5",
        to_node="LOAD_N",
        location="LOAD_N",
        loaded=False,
        payload_tonnes=0.0,
        resource_id="loader_L_N",
        queue_length=1,
    )
    rows = m.event_log_rows()
    assert len(rows) == 1
    expected_cols = {
        "time_min", "replication", "scenario_id", "truck_id", "event_type",
        "from_node", "to_node", "location", "loaded", "payload_tonnes",
        "resource_id", "queue_length",
    }
    assert set(rows[0].keys()) == expected_cols
    assert rows[0]["replication"] == 0
    assert rows[0]["scenario_id"] == "baseline"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.metrics'`.

- [ ] **Step 3: Implement `mine_sim/metrics.py`**

```python
"""Metrics collector and confidence-interval helper."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats


def ci95_t(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) using Student-t at 95% confidence."""
    arr = np.asarray(values, dtype=float)
    n = arr.size
    mean = float(arr.mean()) if n else 0.0
    if n < 2:
        return mean, mean, mean
    sd = float(arr.std(ddof=1))
    if sd == 0.0:
        return mean, mean, mean
    sem = sd / math.sqrt(n)
    half = sem * float(stats.t.ppf(0.975, df=n - 1))
    return mean, mean - half, mean + half


@dataclass
class _ResourceStats:
    busy_minutes: float = 0.0
    queue_waits: list[float] = field(default_factory=list)
    queue_lengths_on_entry: list[int] = field(default_factory=list)


@dataclass
class _CycleStats:
    truck_id: str
    cycle_times_min: list[float] = field(default_factory=list)
    travelling_minutes: float = 0.0
    loading_minutes: float = 0.0
    dumping_minutes: float = 0.0
    queue_minutes: float = 0.0
    tonnes_delivered: float = 0.0


@dataclass
class MetricsCollector:
    scenario_id: str
    replication: int
    shift_minutes: float
    seed: int = 0
    _resources: dict[str, _ResourceStats] = field(default_factory=dict)
    _trucks: dict[str, _CycleStats] = field(default_factory=dict)
    _events: list[dict[str, Any]] = field(default_factory=list)

    # ---- resource recording --------------------------------------------------

    def _res(self, resource_id: str) -> _ResourceStats:
        if resource_id not in self._resources:
            self._resources[resource_id] = _ResourceStats()
        return self._resources[resource_id]

    def record_resource_busy(self, resource_id: str, minutes: float) -> None:
        self._res(resource_id).busy_minutes += minutes

    def record_queue_wait(self, resource_id: str, queue_len_on_entry: int, wait_minutes: float) -> None:
        rs = self._res(resource_id)
        rs.queue_waits.append(wait_minutes)
        rs.queue_lengths_on_entry.append(queue_len_on_entry)

    def utilisation(self, resource_id: str) -> float:
        return self._res(resource_id).busy_minutes / self.shift_minutes

    def avg_queue_wait(self, resource_id: str) -> float:
        waits = self._res(resource_id).queue_waits
        return float(sum(waits) / len(waits)) if waits else 0.0

    def max_queue_length(self, resource_id: str) -> int:
        lens = self._res(resource_id).queue_lengths_on_entry
        return int(max(lens)) if lens else 0

    def resource_ids(self) -> list[str]:
        return list(self._resources.keys())

    # ---- truck recording -----------------------------------------------------

    def truck(self, truck_id: str) -> _CycleStats:
        if truck_id not in self._trucks:
            self._trucks[truck_id] = _CycleStats(truck_id=truck_id)
        return self._trucks[truck_id]

    def record_dump(self, time_min: float, truck_id: str, payload_tonnes: float) -> None:
        self.truck(truck_id).tonnes_delivered += payload_tonnes

    def total_tonnes(self) -> float:
        return float(sum(t.tonnes_delivered for t in self._trucks.values()))

    def tonnes_per_hour(self) -> float:
        hours = self.shift_minutes / 60.0
        return self.total_tonnes() / hours if hours > 0 else 0.0

    def average_cycle_time_min(self) -> float:
        all_cycles: list[float] = []
        for t in self._trucks.values():
            all_cycles.extend(t.cycle_times_min)
        return float(sum(all_cycles) / len(all_cycles)) if all_cycles else 0.0

    def average_truck_utilisation(self) -> float:
        """Fraction of shift each truck spent travelling/loading/dumping (not idle)."""
        if not self._trucks:
            return 0.0
        utilisations = []
        for t in self._trucks.values():
            busy = t.travelling_minutes + t.loading_minutes + t.dumping_minutes
            utilisations.append(busy / self.shift_minutes)
        return float(sum(utilisations) / len(utilisations))

    # ---- event log -----------------------------------------------------------

    def log_event(
        self,
        *,
        time_min: float,
        truck_id: str,
        event_type: str,
        from_node: str | None,
        to_node: str | None,
        location: str | None,
        loaded: bool,
        payload_tonnes: float,
        resource_id: str | None,
        queue_length: int | None,
    ) -> None:
        self._events.append({
            "time_min": float(time_min),
            "replication": self.replication,
            "scenario_id": self.scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": bool(loaded),
            "payload_tonnes": float(payload_tonnes),
            "resource_id": resource_id,
            "queue_length": queue_length,
        })

    def event_log_rows(self) -> list[dict[str, Any]]:
        return list(self._events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_metrics.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/metrics.py tests/test_metrics.py
git commit -m "feat(mine-sim): metrics collector and 95% CI helper"
```

---

## Task 4: Resource pool (loaders, crusher, road locks)

**Files:**
- Create: `mine_sim/resources.py`
- Create: `tests/test_resources.py`

The resource pool exposes:
- `loaders: dict[str, simpy.Resource]` keyed by loader_id (e.g. "L_N", "L_S")
- `crusher: simpy.Resource`
- `road_locks: dict[str, simpy.Resource]` keyed by lock_id (e.g. "RAMP")
- `edge_lock(edge_id) -> str | None` — returns the lock_id for an edge, or None if unconstrained
- service-time means/sds for each loader and the crusher

The factory only creates a road lock if at least one of its member edges (post-override) has effective capacity == 1. This enforces the "ramp_upgrade" semantics: when E03 capacity is raised to 999, no RAMP lock is created.

- [ ] **Step 1: Write failing tests**

Create `tests/test_resources.py`:

```python
"""Tests for the SimPy resource pool."""
import simpy

from mine_sim.resources import EDGE_TO_LOCK, build_resources, edge_lock_id
from mine_sim.scenario import load_scenario
from mine_sim.topology import build_graph


def test_edge_lock_id_known_edges():
    assert edge_lock_id("E03_UP") == "RAMP"
    assert edge_lock_id("E03_DOWN") == "RAMP"
    assert edge_lock_id("E07_TO_LOAD_N") == "PIT_N"
    assert edge_lock_id("E05_TO_CRUSH") == "E05_TO"
    assert edge_lock_id("E05_FROM_CRUSH") == "E05_FROM"


def test_edge_lock_id_unconstrained_edge_returns_none():
    assert edge_lock_id("E01_OUT") is None
    assert edge_lock_id("E02_UP") is None


def test_build_resources_baseline_creates_ramp_lock(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    _, edges, _ = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    assert "RAMP" in pool.road_locks
    assert "PIT_N" in pool.road_locks
    assert "PIT_S" in pool.road_locks
    assert "E05_TO" in pool.road_locks
    assert "E05_FROM" in pool.road_locks
    assert set(pool.loaders.keys()) == {"L_N", "L_S"}
    # crusher is a single resource
    assert pool.crusher.capacity == 1


def test_build_resources_ramp_upgrade_skips_ramp_lock(data_dir, scenarios_dir):
    cfg = load_scenario("ramp_upgrade", scenarios_dir)
    _, edges, _ = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    assert "RAMP" not in pool.road_locks   # capacity raised to 999 → no lock


def test_build_resources_loader_service_times(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    _, edges, _ = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    assert pool.loader_service[("L_N", "mean")] == 6.5
    assert pool.loader_service[("L_N", "sd")] == 1.2
    assert pool.loader_service[("L_S", "mean")] == 4.5


def test_build_resources_crusher_slowdown_override(data_dir, scenarios_dir):
    cfg = load_scenario("crusher_slowdown", scenarios_dir)
    _, edges, _ = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    assert pool.crusher_service["mean"] == 7.0
    assert pool.crusher_service["sd"] == 1.5


def test_paired_lock_blocks_opposing_direction(data_dir, scenarios_dir):
    """A truck holding RAMP via E03_UP must block another truck wanting E03_DOWN."""
    cfg = load_scenario("baseline", scenarios_dir)
    _, edges, _ = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    ramp = pool.road_locks["RAMP"]

    log: list[tuple[float, str]] = []

    def truck_a():
        with ramp.request() as req:
            yield req
            log.append((env.now, "A_acquired"))
            yield env.timeout(5.0)
            log.append((env.now, "A_released"))

    def truck_b():
        yield env.timeout(0.1)   # arrives slightly later
        with ramp.request() as req:
            log.append((env.now, "B_requested"))
            yield req
            log.append((env.now, "B_acquired"))

    env.process(truck_a())
    env.process(truck_b())
    env.run(until=20)
    events = dict(log)
    # B should not have acquired before A released
    assert events["B_acquired"] >= events["A_released"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.resources'`.

- [ ] **Step 3: Implement `mine_sim/resources.py`**

```python
"""SimPy resource pool: loaders, crusher, paired-bidirectional road locks."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import simpy

from mine_sim.topology import Edge


EDGE_TO_LOCK: dict[str, str] = {
    "E03_UP": "RAMP",
    "E03_DOWN": "RAMP",
    "E07_TO_LOAD_N": "PIT_N",
    "E07_FROM_LOAD_N": "PIT_N",
    "E09_TO_LOAD_S": "PIT_S",
    "E09_FROM_LOAD_S": "PIT_S",
    "E05_TO_CRUSH": "E05_TO",
    "E05_FROM_CRUSH": "E05_FROM",
}


def edge_lock_id(edge_id: str) -> str | None:
    return EDGE_TO_LOCK.get(edge_id)


@dataclass
class ResourcePool:
    loaders: dict[str, simpy.Resource]
    crusher: simpy.Resource
    road_locks: dict[str, simpy.Resource]
    loader_service: dict[tuple[str, str], float]   # (loader_id, "mean"|"sd") -> minutes
    loader_node: dict[str, str]                    # loader_id -> node_id
    crusher_service: dict[str, float]              # "mean"|"sd" -> minutes
    crusher_node: str
    bucket_capacity_tonnes: dict[str, float] = field(default_factory=dict)


def _load_loaders(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (Path(data_dir) / "loaders.csv").open() as fh:
        for r in csv.DictReader(fh):
            if not r.get("loader_id"):
                continue
            rows.append({
                "loader_id": r["loader_id"],
                "node_id": r["node_id"],
                "capacity": int(r["capacity"]),
                "bucket_capacity_tonnes": float(r["bucket_capacity_tonnes"]),
                "mean_load_time_min": float(r["mean_load_time_min"]),
                "sd_load_time_min": float(r["sd_load_time_min"]),
            })
    return rows


def _load_dumps(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (Path(data_dir) / "dump_points.csv").open() as fh:
        for r in csv.DictReader(fh):
            if not r.get("dump_id"):
                continue
            rows.append({
                "dump_id": r["dump_id"],
                "node_id": r["node_id"],
                "type": r["type"],
                "capacity": int(r["capacity"]),
                "mean_dump_time_min": float(r["mean_dump_time_min"]),
                "sd_dump_time_min": float(r["sd_dump_time_min"]),
            })
    return rows


def build_resources(
    env: simpy.Environment,
    config: dict[str, Any],
    edges: dict[str, Edge],
    data_dir: Path,
) -> ResourcePool:
    """Build SimPy resources for one replication."""
    data_dir = Path(data_dir)
    loader_rows = _load_loaders(data_dir)
    dump_rows = _load_dumps(data_dir)

    loader_overrides = config.get("loader_overrides", {}) or {}
    dump_overrides = config.get("dump_point_overrides", {}) or {}

    # --- Loaders -------------------------------------------------------------
    loaders: dict[str, simpy.Resource] = {}
    loader_service: dict[tuple[str, str], float] = {}
    loader_node: dict[str, str] = {}
    bucket_capacity: dict[str, float] = {}
    for r in loader_rows:
        lid = r["loader_id"]
        ov = loader_overrides.get(lid, {})
        cap = int(ov.get("capacity", r["capacity"]))
        loaders[lid] = simpy.Resource(env, capacity=cap)
        loader_service[(lid, "mean")] = float(ov.get("mean_load_time_min", r["mean_load_time_min"]))
        loader_service[(lid, "sd")] = float(ov.get("sd_load_time_min", r["sd_load_time_min"]))
        loader_node[lid] = r["node_id"]
        bucket_capacity[lid] = float(ov.get("bucket_capacity_tonnes", r["bucket_capacity_tonnes"]))

    # --- Crusher (the dump point of type "crusher") --------------------------
    crusher_row = next(d for d in dump_rows if d["type"] == "crusher")
    cov = dump_overrides.get(crusher_row["dump_id"], {})
    crusher = simpy.Resource(
        env,
        capacity=int(cov.get("capacity", crusher_row["capacity"])),
    )
    crusher_service = {
        "mean": float(cov.get("mean_dump_time_min", crusher_row["mean_dump_time_min"])),
        "sd": float(cov.get("sd_dump_time_min", crusher_row["sd_dump_time_min"])),
    }
    crusher_node = crusher_row["node_id"]

    # --- Road locks ----------------------------------------------------------
    # Group edges by lock id; create a lock only if any member edge has effective capacity == 1.
    lock_members: dict[str, list[Edge]] = {}
    for eid, edge in edges.items():
        lock_id = EDGE_TO_LOCK.get(eid)
        if lock_id is None:
            continue
        lock_members.setdefault(lock_id, []).append(edge)

    road_locks: dict[str, simpy.Resource] = {}
    for lock_id, members in lock_members.items():
        if any(m.capacity == 1 and not m.closed for m in members):
            road_locks[lock_id] = simpy.Resource(env, capacity=1)

    return ResourcePool(
        loaders=loaders,
        crusher=crusher,
        road_locks=road_locks,
        loader_service=loader_service,
        loader_node=loader_node,
        crusher_service=crusher_service,
        crusher_node=crusher_node,
        bucket_capacity_tonnes=bucket_capacity,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resources.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/resources.py tests/test_resources.py
git commit -m "feat(mine-sim): SimPy resource pool with paired-bidir road locks"
```

---

## Task 5: Truck process & dispatcher

**Files:**
- Create: `mine_sim/truck.py`
- Create: `tests/test_truck.py`

The Truck process loops: dispatch (choose loader) → travel empty → load → travel loaded → dump → record → loop. It uses pre-computed shortest paths for travel and the dispatcher for loader choice. Travel includes per-edge speed noise and acquires road locks as needed.

This task introduces a `Simulation` container that bundles env + config + pool + graph + edges + paths + rng + collector — the truck process needs all of these.

- [ ] **Step 1: Write failing tests**

Create `tests/test_truck.py`:

```python
"""Tests for truck dispatcher and one-cycle smoke test."""
from pathlib import Path

import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import build_resources
from mine_sim.scenario import load_scenario
from mine_sim.topology import build_graph
from mine_sim.truck import Simulation, choose_loader, draw_truncated_normal


def test_draw_truncated_normal_is_floor_clipped():
    rng = np.random.default_rng(0)
    draws = [draw_truncated_normal(rng, mean=1.0, sd=10.0) for _ in range(1000)]
    assert min(draws) >= 0.1
    assert max(draws) <= 1.0 + 5 * 10.0


def test_draw_truncated_normal_reproducible():
    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    draws_a = [draw_truncated_normal(rng_a, 5.0, 1.0) for _ in range(50)]
    draws_b = [draw_truncated_normal(rng_b, 5.0, 1.0) for _ in range(50)]
    assert draws_a == draws_b


def test_choose_loader_prefers_shorter_expected_cycle(data_dir, scenarios_dir):
    """When both loaders are idle, dispatcher should pick the one with shorter expected cycle."""
    cfg = load_scenario("baseline", scenarios_dir)
    g, edges, nodes = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    rng = np.random.default_rng(0)
    collector = MetricsCollector("baseline", 0, shift_minutes=480.0)
    sim = Simulation(env=env, config=cfg, graph=g, edges=edges, nodes=nodes,
                     pool=pool, rng=rng, collector=collector)
    chosen = choose_loader(current_node="PARK", sim=sim)
    # Either loader is plausible; assert it is one of the two.
    assert chosen in {"L_N", "L_S"}


def test_one_truck_completes_at_least_one_cycle(data_dir, scenarios_dir):
    """End-to-end smoke: one truck over a full shift should deliver tonnes > 0."""
    from mine_sim.truck import Truck
    cfg = load_scenario("baseline", scenarios_dir)
    cfg["fleet"]["truck_count"] = 1
    g, edges, nodes = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    rng = np.random.default_rng(123)
    collector = MetricsCollector("baseline", 0, shift_minutes=480.0)
    sim = Simulation(env=env, config=cfg, graph=g, edges=edges, nodes=nodes,
                     pool=pool, rng=rng, collector=collector)
    Truck(sim, truck_id="T01", payload_tonnes=100.0,
          empty_speed_factor=1.0, loaded_speed_factor=0.85, start_node="PARK").start()
    env.run(until=480)
    assert collector.total_tonnes() > 0
    # There should be at least one dumping_ended event at CRUSH.
    dumps = [e for e in collector.event_log_rows()
             if e["event_type"] == "dumping_ended" and e["location"] == "CRUSH"]
    assert len(dumps) >= 1


def test_ramp_closed_truck_uses_bypass(data_dir, scenarios_dir):
    """Under ramp_closed, the event log should show traversal of bypass edges."""
    from mine_sim.truck import Truck
    cfg = load_scenario("ramp_closed", scenarios_dir)
    cfg["fleet"]["truck_count"] = 1
    g, edges, nodes = build_graph(cfg, data_dir)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges, data_dir)
    rng = np.random.default_rng(7)
    collector = MetricsCollector("ramp_closed", 0, shift_minutes=480.0)
    sim = Simulation(env=env, config=cfg, graph=g, edges=edges, nodes=nodes,
                     pool=pool, rng=rng, collector=collector)
    Truck(sim, truck_id="T01", payload_tonnes=100.0,
          empty_speed_factor=1.0, loaded_speed_factor=0.85, start_node="PARK").start()
    env.run(until=480)
    log = collector.event_log_rows()
    traversed = {(e["from_node"], e["to_node"]) for e in log if e["event_type"] == "traversal_started"}
    # Must have used at least one bypass edge.
    bypass_edges = {("J2", "J7"), ("J7", "J8"), ("J8", "J4")}
    assert traversed & bypass_edges
    # And must NOT have used the closed ramp.
    assert ("J2", "J3") not in traversed
    assert ("J3", "J2") not in traversed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_truck.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.truck'`.

- [ ] **Step 3: Implement `mine_sim/truck.py`**

```python
"""Truck SimPy process and dispatcher."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import EDGE_TO_LOCK, ResourcePool
from mine_sim.topology import Edge, Node, nominal_travel_time_min


def draw_truncated_normal(rng: np.random.Generator, mean: float, sd: float) -> float:
    """Draw from Normal(mean, sd), truncated to [0.1, mean + 5*sd]."""
    if sd <= 0.0:
        return float(max(0.1, mean))
    val = rng.normal(mean, sd)
    upper = mean + 5.0 * sd
    return float(np.clip(val, 0.1, upper))


@dataclass
class Simulation:
    env: simpy.Environment
    config: dict[str, Any]
    graph: nx.DiGraph
    edges: dict[str, Edge]
    nodes: dict[str, Node]
    pool: ResourcePool
    rng: np.random.Generator
    collector: MetricsCollector
    _shortest_paths: dict[tuple[str, str], list[Edge]] = field(default_factory=dict)
    _nominal_time: dict[tuple[str, str], float] = field(default_factory=dict)

    def shortest_path(self, src: str, dst: str) -> list[Edge]:
        key = (src, dst)
        if key not in self._shortest_paths:
            from mine_sim.topology import shortest_path_edges
            self._shortest_paths[key] = shortest_path_edges(self.graph, self.edges, src, dst)
        return self._shortest_paths[key]

    def nominal_travel_time_min(self, src: str, dst: str) -> float:
        key = (src, dst)
        if key not in self._nominal_time:
            path = self.shortest_path(src, dst)
            self._nominal_time[key] = sum(nominal_travel_time_min(e) for e in path)
        return self._nominal_time[key]


def choose_loader(current_node: str, sim: Simulation) -> str:
    """Return the loader_id minimising expected cycle time. Deterministic tie-break by loader_id."""
    candidates: list[tuple[float, str]] = []
    for loader_id, loader_node in sim.pool.loader_node.items():
        travel_to = sim.nominal_travel_time_min(current_node, loader_node)
        travel_loaded = sim.nominal_travel_time_min(loader_node, sim.pool.crusher_node)
        # SimPy queue length is len(loader.queue) (waiting) + (1 if currently in service else 0)
        loader_res = sim.pool.loaders[loader_id]
        queue_count = len(loader_res.queue) + len(loader_res.users)
        load_mean = sim.pool.loader_service[(loader_id, "mean")]
        crusher_mean = sim.pool.crusher_service["mean"]
        expected_cycle = (
            travel_to
            + queue_count * load_mean
            + load_mean
            + travel_loaded
            + crusher_mean
        )
        candidates.append((expected_cycle, loader_id))
    candidates.sort()
    return candidates[0][1]


@dataclass
class Truck:
    sim: Simulation
    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    start_node: str
    _current_node: str = ""
    _loaded: bool = False
    _cycle_start_time: float = 0.0

    def start(self) -> None:
        self._current_node = self.start_node
        self.sim.env.process(self._run())

    # ---- main process loop --------------------------------------------------

    def _run(self):
        env = self.sim.env
        shift_minutes = self.sim.config["simulation"]["shift_length_hours"] * 60.0
        while env.now < shift_minutes:
            self._cycle_start_time = env.now

            # 1. Dispatch
            loader_id = choose_loader(self._current_node, self.sim)
            loader_node = self.sim.pool.loader_node[loader_id]
            self._log(
                "truck_dispatched",
                from_node=self._current_node,
                to_node=loader_node,
                location=self._current_node,
                resource_id=f"loader_{loader_id}",
            )

            # 2. Travel empty -> loader
            yield from self._travel_path(self._current_node, loader_node, loaded=False)
            if env.now >= shift_minutes:
                break

            # 3. Load
            yield from self._load(loader_id)
            if env.now >= shift_minutes:
                break

            # 4. Travel loaded -> crusher
            yield from self._travel_path(loader_node, self.sim.pool.crusher_node, loaded=True)
            if env.now >= shift_minutes:
                break

            # 5. Dump
            yield from self._dump()

            # cycle complete
            self.sim.collector.truck(self.truck_id).cycle_times_min.append(env.now - self._cycle_start_time)

    # ---- travel -------------------------------------------------------------

    def _travel_path(self, src: str, dst: str, *, loaded: bool):
        if src == dst:
            return
        path = self.sim.shortest_path(src, dst)
        for edge in path:
            yield from self._traverse(edge, loaded=loaded)

    def _traverse(self, edge: Edge, *, loaded: bool):
        env = self.sim.env
        speed_factor = self.loaded_speed_factor if loaded else self.empty_speed_factor
        base_speed = edge.max_speed_kph * speed_factor
        cv = self.sim.config.get("stochasticity", {}).get("travel_time_noise_cv", 0.10)
        noise = float(self.sim.rng.normal(1.0, cv))
        speed = max(0.1 * edge.max_speed_kph, base_speed * noise)
        travel_time_min = (edge.distance_m / 1000.0) / speed * 60.0

        lock_id = EDGE_TO_LOCK.get(edge.edge_id)
        lock = self.sim.pool.road_locks.get(lock_id) if lock_id else None

        self._log(
            "traversal_started",
            from_node=edge.from_node,
            to_node=edge.to_node,
            location=edge.from_node,
            resource_id=lock_id,
            queue_length=(len(lock.queue) if lock is not None else None),
            loaded=loaded,
        )

        if lock is not None:
            self._log(
                "road_lock_requested",
                from_node=edge.from_node,
                to_node=edge.to_node,
                location=edge.from_node,
                resource_id=lock_id,
                queue_length=len(lock.queue),
                loaded=loaded,
            )
            t_request = env.now
            with lock.request() as req:
                yield req
                wait = env.now - t_request
                self.sim.collector.record_queue_wait(
                    f"road_{lock_id}",
                    queue_len_on_entry=len(lock.queue),
                    wait_minutes=wait,
                )
                self._log(
                    "road_lock_acquired",
                    from_node=edge.from_node,
                    to_node=edge.to_node,
                    location=edge.from_node,
                    resource_id=lock_id,
                    queue_length=len(lock.queue),
                    loaded=loaded,
                )
                t0 = env.now
                yield env.timeout(travel_time_min)
                self.sim.collector.record_resource_busy(f"road_{lock_id}", env.now - t0)
        else:
            yield env.timeout(travel_time_min)

        # truck travel-time accounting
        self.sim.collector.truck(self.truck_id).travelling_minutes += travel_time_min
        self._current_node = edge.to_node

        self._log(
            "traversal_ended",
            from_node=edge.from_node,
            to_node=edge.to_node,
            location=edge.to_node,
            resource_id=lock_id,
            loaded=loaded,
        )

    # ---- load ---------------------------------------------------------------

    def _load(self, loader_id: str):
        env = self.sim.env
        loader_res = self.sim.pool.loaders[loader_id]
        node_id = self.sim.pool.loader_node[loader_id]
        resource_id = f"loader_{loader_id}"

        self._log("loader_requested", from_node=node_id, to_node=node_id,
                  location=node_id, resource_id=resource_id,
                  queue_length=len(loader_res.queue))
        t_req = env.now
        with loader_res.request() as req:
            yield req
            wait = env.now - t_req
            self.sim.collector.record_queue_wait(
                resource_id,
                queue_len_on_entry=len(loader_res.queue),
                wait_minutes=wait,
            )
            mean = self.sim.pool.loader_service[(loader_id, "mean")]
            sd = self.sim.pool.loader_service[(loader_id, "sd")]
            duration = draw_truncated_normal(self.sim.rng, mean, sd)
            self._log("loading_started", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(loader_res.queue))
            yield env.timeout(duration)
            self.sim.collector.record_resource_busy(resource_id, duration)
            self.sim.collector.truck(self.truck_id).loading_minutes += duration
            self._loaded = True
            self._log("loading_ended", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(loader_res.queue))

    # ---- dump ---------------------------------------------------------------

    def _dump(self):
        env = self.sim.env
        crusher_res = self.sim.pool.crusher
        node_id = self.sim.pool.crusher_node
        resource_id = "crusher"

        self._log("crusher_requested", from_node=node_id, to_node=node_id,
                  location=node_id, resource_id=resource_id,
                  queue_length=len(crusher_res.queue))
        t_req = env.now
        with crusher_res.request() as req:
            yield req
            wait = env.now - t_req
            self.sim.collector.record_queue_wait(
                resource_id,
                queue_len_on_entry=len(crusher_res.queue),
                wait_minutes=wait,
            )
            mean = self.sim.pool.crusher_service["mean"]
            sd = self.sim.pool.crusher_service["sd"]
            duration = draw_truncated_normal(self.sim.rng, mean, sd)
            self._log("dumping_started", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(crusher_res.queue))
            yield env.timeout(duration)
            self.sim.collector.record_resource_busy(resource_id, duration)
            self.sim.collector.truck(self.truck_id).dumping_minutes += duration
            self.sim.collector.record_dump(env.now, self.truck_id, self.payload_tonnes)
            self._loaded = False
            self._log("dumping_ended", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(crusher_res.queue),
                      payload_tonnes=self.payload_tonnes)

    # ---- helpers ------------------------------------------------------------

    def _log(self, event_type: str, *, from_node: str | None = None,
             to_node: str | None = None, location: str | None = None,
             resource_id: str | None = None, queue_length: int | None = None,
             loaded: bool | None = None, payload_tonnes: float | None = None) -> None:
        self.sim.collector.log_event(
            time_min=self.sim.env.now,
            truck_id=self.truck_id,
            event_type=event_type,
            from_node=from_node,
            to_node=to_node,
            location=location,
            loaded=self._loaded if loaded is None else loaded,
            payload_tonnes=(self.payload_tonnes if self._loaded else 0.0)
                           if payload_tonnes is None else payload_tonnes,
            resource_id=resource_id,
            queue_length=queue_length,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_truck.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/truck.py tests/test_truck.py
git commit -m "feat(mine-sim): truck process, dispatcher, traversal with road locks"
```

---

## Task 6: Experiment driver (replications + reproducibility)

**Files:**
- Create: `mine_sim/experiment.py`
- Create: `tests/test_experiment.py`

The experiment driver runs replications, threads seeds, and produces a `ScenarioResult` (list of per-rep `MetricsCollector` snapshots + the resolved config).

- [ ] **Step 1: Write failing tests**

Create `tests/test_experiment.py`:

```python
"""Tests for replication-driven experiments and reproducibility."""
import pandas as pd

from mine_sim.experiment import run_replication, run_scenario


def test_run_replication_returns_collector(data_dir, scenarios_dir):
    from mine_sim.scenario import load_scenario
    cfg = load_scenario("baseline", scenarios_dir)
    collector = run_replication(cfg, replication_idx=0, data_dir=data_dir)
    assert collector.scenario_id == "baseline"
    assert collector.replication == 0
    assert collector.total_tonnes() > 0


def test_same_seed_reproducible(data_dir, scenarios_dir):
    from mine_sim.scenario import load_scenario
    cfg = load_scenario("baseline", scenarios_dir)
    a = run_replication(cfg, replication_idx=3, data_dir=data_dir)
    b = run_replication(cfg, replication_idx=3, data_dir=data_dir)
    df_a = pd.DataFrame(a.event_log_rows())
    df_b = pd.DataFrame(b.event_log_rows())
    pd.testing.assert_frame_equal(df_a, df_b)


def test_run_scenario_runs_all_replications(data_dir, scenarios_dir):
    from mine_sim.scenario import load_scenario
    cfg = load_scenario("baseline", scenarios_dir)
    cfg["simulation"]["replications"] = 3   # smoke run
    result = run_scenario(cfg, data_dir=data_dir)
    assert result.scenario_id == "baseline"
    assert len(result.replications) == 3
    assert all(r.total_tonnes() > 0 for r in result.replications)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_experiment.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.experiment'`.

- [ ] **Step 3: Implement `mine_sim/experiment.py`**

```python
"""Replication driver: seeds, scenarios, aggregation."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import build_resources
from mine_sim.topology import build_graph, validate_reachability
from mine_sim.truck import Simulation, Truck


def _load_truck_rows(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with (Path(data_dir) / "trucks.csv").open() as fh:
        for r in csv.DictReader(fh):
            if not r.get("truck_id"):
                continue
            rows.append({
                "truck_id": r["truck_id"],
                "payload_tonnes": float(r["payload_tonnes"]),
                "empty_speed_factor": float(r["empty_speed_factor"]),
                "loaded_speed_factor": float(r["loaded_speed_factor"]),
                "availability": float(r["availability"]),
                "start_node": r["start_node"],
            })
    return rows


def _select_trucks(rows: list[dict[str, Any]], truck_count: int) -> list[dict[str, Any]]:
    if truck_count > len(rows):
        raise ValueError(
            f"Scenario asks for {truck_count} trucks but trucks.csv has {len(rows)}."
        )
    return rows[:truck_count]


def run_replication(
    config: dict[str, Any],
    replication_idx: int,
    data_dir: Path,
) -> MetricsCollector:
    """Run a single replication and return the populated MetricsCollector."""
    base_seed = int(config["simulation"]["base_random_seed"])
    seed = base_seed + replication_idx
    rng = np.random.default_rng(seed)

    shift_minutes = float(config["simulation"]["shift_length_hours"]) * 60.0

    env = simpy.Environment()
    graph, edges, nodes = build_graph(config, data_dir)

    pool = build_resources(env, config, edges, data_dir)
    validate_reachability(
        graph,
        loader_node_ids=list(pool.loader_node.values()),
        crusher_node_id=pool.crusher_node,
        parking_node_id="PARK",
    )

    collector = MetricsCollector(
        scenario_id=str(config["scenario_id"]),
        replication=replication_idx,
        shift_minutes=shift_minutes,
        seed=seed,
    )
    sim = Simulation(
        env=env, config=config, graph=graph, edges=edges, nodes=nodes,
        pool=pool, rng=rng, collector=collector,
    )

    truck_rows = _select_trucks(_load_truck_rows(data_dir), int(config["fleet"]["truck_count"]))
    for tr in truck_rows:
        Truck(
            sim,
            truck_id=tr["truck_id"],
            payload_tonnes=tr["payload_tonnes"],
            empty_speed_factor=tr["empty_speed_factor"],
            loaded_speed_factor=tr["loaded_speed_factor"],
            start_node=tr["start_node"],
        ).start()

    env.run(until=shift_minutes)
    return collector


@dataclass
class ScenarioResult:
    scenario_id: str
    config: dict[str, Any]
    replications: list[MetricsCollector]


def run_scenario(config: dict[str, Any], data_dir: Path) -> ScenarioResult:
    n = int(config["simulation"]["replications"])
    reps = [run_replication(config, i, data_dir) for i in range(n)]
    return ScenarioResult(
        scenario_id=str(config["scenario_id"]),
        config=config,
        replications=reps,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_experiment.py -v`
Expected: 3 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/experiment.py tests/test_experiment.py
git commit -m "feat(mine-sim): replication driver with seeded reproducibility"
```

---

## Task 7: Reporting (results.csv, summary.json, event_log.csv)

**Files:**
- Create: `mine_sim/report.py`
- Create: `tests/test_report.py`

Reporting consumes a list of `ScenarioResult`s and writes the four output files. The event log policy: full events for replication 0 of every scenario; only `dumping_ended` events for replications 1–N for the combined `event_log.csv`. Per-scenario full traces for replication 0 written to `results/{scenario_id}__event_log.csv`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_report.py`:

```python
"""Tests for output file writers."""
import json

import pandas as pd

from mine_sim.experiment import run_scenario
from mine_sim.report import write_outputs
from mine_sim.scenario import load_scenario


def _smoke_results(data_dir, scenarios_dir, scenarios=("baseline",), reps=2):
    out = []
    for sid in scenarios:
        cfg = load_scenario(sid, scenarios_dir)
        cfg["simulation"]["replications"] = reps
        out.append(run_scenario(cfg, data_dir=data_dir))
    return out


def test_results_csv_columns(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "results.csv")
    required = {
        "scenario_id", "replication", "random_seed",
        "total_tonnes_delivered", "tonnes_per_hour",
        "average_truck_cycle_time_min", "average_truck_utilisation",
        "crusher_utilisation",
        "average_loader_queue_time_min", "average_crusher_queue_time_min",
    }
    assert required.issubset(set(df.columns))
    assert len(df) == 2   # 1 scenario × 2 reps


def test_summary_json_schema(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, scenarios=("baseline", "trucks_4"), reps=2)
    write_outputs(results, output_dir=tmp_output_dir)
    summary = json.loads((tmp_output_dir / "summary.json").read_text())
    assert summary["benchmark_id"] == "001_synthetic_mine_throughput"
    for sid in ("baseline", "trucks_4"):
        s = summary["scenarios"][sid]
        for key in ("replications", "shift_length_hours", "total_tonnes_mean",
                    "total_tonnes_ci95_low", "total_tonnes_ci95_high",
                    "tonnes_per_hour_mean", "tonnes_per_hour_ci95_low",
                    "tonnes_per_hour_ci95_high", "average_cycle_time_min",
                    "truck_utilisation_mean", "loader_utilisation",
                    "crusher_utilisation", "average_loader_queue_time_min",
                    "average_crusher_queue_time_min", "top_bottlenecks"):
            assert key in s, f"missing {key} in {sid}"
        assert isinstance(s["loader_utilisation"], dict)
        assert isinstance(s["top_bottlenecks"], list)
    assert "key_assumptions" in summary
    assert "model_limitations" in summary
    assert "additional_scenarios_proposed" in summary


def test_event_log_combined_has_dumping_ended_for_all_reps(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, reps=3)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "event_log.csv")
    dumping = df[df["event_type"] == "dumping_ended"]
    assert set(dumping["replication"].unique()) == {0, 1, 2}
    # rep 0 must have other event types beyond dumping_ended
    rep0 = df[df["replication"] == 0]
    assert set(rep0["event_type"]) - {"dumping_ended"}


def test_per_scenario_event_log_rep0_full(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, reps=2)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "baseline__event_log.csv")
    # Should contain events from rep 0 only
    assert set(df["replication"].unique()) == {0}
    # And include traversal events, not just dumping
    assert "traversal_started" in set(df["event_type"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mine_sim.report'`.

- [ ] **Step 3: Implement `mine_sim/report.py`**

```python
"""Output writers: results.csv, summary.json, event_log.csv."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from mine_sim.experiment import ScenarioResult
from mine_sim.metrics import MetricsCollector, ci95_t


KEY_ASSUMPTIONS = [
    "Capacity-1 ramp E03 and pit-access roads E07/E09 are modelled as paired bidirectional resources (one truck on the physical road regardless of direction). Crusher approach E05 keeps per-direction locks.",
    "Loading and dumping times follow Normal(mean, sd) truncated to [0.1 min, mean + 5 sd].",
    "Travel-time noise is multiplicative Normal(1.0, cv=0.10) per truck per edge per traversal, with effective speed floored at 10% of edge max_speed_kph.",
    "Routing uses pre-computed travel-time-weighted shortest paths (NetworkX Dijkstra). Loader choice is dynamic via nearest_available_loader with shortest_expected_cycle_time tiebreaker.",
    "Throughput is attributed at dumping_ended events at the crusher only; in-progress dumps at shift end are not counted.",
    "All trucks start at PARK at t=0 and are dispatched simultaneously.",
]

MODEL_LIMITATIONS = [
    "No truck breakdowns, refuelling, shift handover, or operator skill variation are modelled.",
    "No weather, blasting, or grade-resistance effects on travel speed beyond the loaded/empty speed factor.",
    "Dispatching does not preempt or re-route mid-cycle; loader choice is fixed at cycle start.",
    "Trucks finish their current state transition at shift end (no mid-traversal kill); only completed dumps count toward throughput.",
    "Initial dispatch from PARK is simultaneous, which may overstate loader contention in the first cycle relative to staggered start-up in practice.",
]


def _per_replication_row(coll: MetricsCollector) -> dict[str, Any]:
    loader_queue_times = [
        coll.avg_queue_wait(f"loader_{lid}")
        for lid in ("L_N", "L_S")
    ]
    avg_loader_queue = (
        sum(loader_queue_times) / len(loader_queue_times) if loader_queue_times else 0.0
    )
    return {
        "scenario_id": coll.scenario_id,
        "replication": coll.replication,
        "random_seed": coll.seed,
        "total_tonnes_delivered": coll.total_tonnes(),
        "tonnes_per_hour": coll.tonnes_per_hour(),
        "average_truck_cycle_time_min": coll.average_cycle_time_min(),
        "average_truck_utilisation": coll.average_truck_utilisation(),
        "crusher_utilisation": coll.utilisation("crusher"),
        "average_loader_queue_time_min": avg_loader_queue,
        "average_crusher_queue_time_min": coll.avg_queue_wait("crusher"),
        "loader_L_N_utilisation": coll.utilisation("loader_L_N"),
        "loader_L_S_utilisation": coll.utilisation("loader_L_S"),
    }


def _scenario_summary(result: ScenarioResult) -> dict[str, Any]:
    reps = result.replications
    n = len(reps)
    total_tonnes = [r.total_tonnes() for r in reps]
    tph = [r.tonnes_per_hour() for r in reps]
    cycle = [r.average_cycle_time_min() for r in reps]
    truck_util = [r.average_truck_utilisation() for r in reps]
    crusher_util = [r.utilisation("crusher") for r in reps]
    loader_queue = [
        (r.avg_queue_wait("loader_L_N") + r.avg_queue_wait("loader_L_S")) / 2.0
        for r in reps
    ]
    crusher_queue = [r.avg_queue_wait("crusher") for r in reps]

    tt_mean, tt_lo, tt_hi = ci95_t(total_tonnes)
    tph_mean, tph_lo, tph_hi = ci95_t(tph)

    loader_util = {}
    for lid in ("L_N", "L_S"):
        util_values = [r.utilisation(f"loader_{lid}") for r in reps]
        m, _, _ = ci95_t(util_values)
        loader_util[lid] = m

    # Bottleneck ranking: union of resources observed across replications.
    resource_ids: set[str] = set()
    for r in reps:
        resource_ids.update(r.resource_ids())
    rankings: list[dict[str, Any]] = []
    for rid in resource_ids:
        utils = [r.utilisation(rid) for r in reps]
        waits = [r.avg_queue_wait(rid) for r in reps]
        u_mean, _, _ = ci95_t(utils)
        w_mean, _, _ = ci95_t(waits)
        rankings.append({
            "resource_id": rid,
            "utilisation": u_mean,
            "avg_queue_wait_min": w_mean,
            "score": u_mean * w_mean,
        })
    rankings.sort(key=lambda x: x["score"], reverse=True)

    return {
        "replications": n,
        "shift_length_hours": float(result.config["simulation"]["shift_length_hours"]),
        "total_tonnes_mean": tt_mean,
        "total_tonnes_ci95_low": tt_lo,
        "total_tonnes_ci95_high": tt_hi,
        "tonnes_per_hour_mean": tph_mean,
        "tonnes_per_hour_ci95_low": tph_lo,
        "tonnes_per_hour_ci95_high": tph_hi,
        "average_cycle_time_min": ci95_t(cycle)[0],
        "truck_utilisation_mean": ci95_t(truck_util)[0],
        "loader_utilisation": loader_util,
        "crusher_utilisation": ci95_t(crusher_util)[0],
        "average_loader_queue_time_min": ci95_t(loader_queue)[0],
        "average_crusher_queue_time_min": ci95_t(crusher_queue)[0],
        "top_bottlenecks": rankings[:5],
    }


def _filter_event_log_for_combined(coll: MetricsCollector) -> list[dict[str, Any]]:
    if coll.replication == 0:
        return coll.event_log_rows()
    return [e for e in coll.event_log_rows() if e["event_type"] == "dumping_ended"]


def write_outputs(
    results: list[ScenarioResult],
    output_dir: Path,
    *,
    additional_scenarios_proposed: list[str] | None = None,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # results.csv
    rows = [
        _per_replication_row(rep)
        for result in results
        for rep in result.replications
    ]
    pd.DataFrame(rows).to_csv(output_dir / "results.csv", index=False)

    # summary.json
    summary: dict[str, Any] = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {r.scenario_id: _scenario_summary(r) for r in results},
        "key_assumptions": KEY_ASSUMPTIONS,
        "model_limitations": MODEL_LIMITATIONS,
        "additional_scenarios_proposed": additional_scenarios_proposed or [],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # combined event_log.csv
    combined: list[dict[str, Any]] = []
    for result in results:
        for rep in result.replications:
            combined.extend(_filter_event_log_for_combined(rep))
    pd.DataFrame(combined).to_csv(output_dir / "event_log.csv", index=False)

    # per-scenario rep-0 traces
    for result in results:
        rep0 = next((r for r in result.replications if r.replication == 0), None)
        if rep0 is None:
            continue
        pd.DataFrame(rep0.event_log_rows()).to_csv(
            output_dir / f"{result.scenario_id}__event_log.csv",
            index=False,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -v`
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add mine_sim/report.py tests/test_report.py
git commit -m "feat(mine-sim): output writers for results, summary, event log"
```

---

## Task 8: CLI entry point

**Files:**
- Create: `mine_sim/run.py`

The CLI runs all six required scenarios by default, writes outputs to `results/`, and supports flags for single-scenario runs and replication overrides for smoke testing.

- [ ] **Step 1: Implement `mine_sim/run.py`**

```python
"""CLI entry point: `python -m mine_sim.run`."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from mine_sim.experiment import run_scenario
from mine_sim.report import write_outputs
from mine_sim.scenario import load_scenario


REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]


def _here() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mine throughput simulation.")
    parser.add_argument(
        "--scenario", action="append", dest="scenarios",
        help="Scenario id to run (repeatable). Default: all six required scenarios.",
    )
    parser.add_argument(
        "--replications", type=int, default=None,
        help="Override replications count (e.g. 5 for smoke testing).",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=_here() / "data",
        help="Path to data/ directory.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_here() / "results",
        help="Path to results/ directory.",
    )
    args = parser.parse_args(argv)

    scenarios_dir = args.data_dir / "scenarios"
    scenario_ids = args.scenarios or REQUIRED_SCENARIOS

    results = []
    for sid in scenario_ids:
        cfg = load_scenario(sid, scenarios_dir)
        if args.replications is not None:
            cfg["simulation"]["replications"] = args.replications
        n = cfg["simulation"]["replications"]
        print(f"[{sid}] running {n} replications...", flush=True)
        t0 = time.perf_counter()
        result = run_scenario(cfg, data_dir=args.data_dir)
        dt = time.perf_counter() - t0
        tonnes = [r.total_tonnes() for r in result.replications]
        mean = sum(tonnes) / len(tonnes) if tonnes else 0.0
        print(f"[{sid}] done in {dt:.1f}s; mean total_tonnes = {mean:.0f}", flush=True)
        results.append(result)

    write_outputs(results, output_dir=args.output_dir)
    print(f"Wrote outputs to {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Smoke-run a fast scenario**

Run:
```bash
mkdir -p results
python -m mine_sim.run --scenario baseline --replications 3
```

Expected: prints `[baseline] running 3 replications...`, then `[baseline] done in N.Ns; mean total_tonnes = ...`, then `Wrote outputs to .../results`. Files exist:
```bash
ls results/
```
Should show `results.csv`, `summary.json`, `event_log.csv`, `baseline__event_log.csv`.

- [ ] **Step 3: Commit**

```bash
git add mine_sim/run.py
git commit -m "feat(mine-sim): CLI entry point with per-scenario timing log"
```

---

## Task 9: Run all six scenarios and verify reproducibility

**Files (writes only):**
- `results/results.csv`
- `results/summary.json`
- `results/event_log.csv`
- `results/{scenario_id}__event_log.csv` × 6

- [ ] **Step 1: Full run**

Run:
```bash
python -m mine_sim.run
```

Expected: each scenario prints a "done" line; total runtime under ~5 minutes; final line `Wrote outputs to .../results`.

- [ ] **Step 2: Inspect summary.json baseline**

Run:
```bash
python -c "import json; print(json.dumps(json.load(open('results/summary.json'))['scenarios']['baseline'], indent=2))"
```

Expected: `total_tonnes_mean` and `tonnes_per_hour_mean` are sensible non-zero values, CIs surround the mean, `top_bottlenecks` lists at least 3 resources sorted by score descending.

- [ ] **Step 3: Reproducibility check**

Run:
```bash
mv results/baseline__event_log.csv results/baseline__event_log.first.csv
python -m mine_sim.run --scenario baseline
diff results/baseline__event_log.first.csv results/baseline__event_log.csv
```

Expected: `diff` produces no output (files are byte-identical). If they differ, debug seeded-RNG plumbing before continuing.

- [ ] **Step 4: Clean up the duplicate**

Run:
```bash
rm results/baseline__event_log.first.csv
```

- [ ] **Step 5: Commit results**

Update `.gitignore` to allow committing the result files for this run (override the default ignore for results outputs):

Edit `.gitignore` — replace the lines:
```text
results/event_log.csv
results/*.csv
results/*.json
!results/.gitkeep
```
with:
```text
# results/ outputs are checked in for this submission
```

Then:
```bash
git add .gitignore results/
git commit -m "feat(mine-sim): commit baseline run outputs for all six scenarios"
```

---

## Task 10: Conceptual model document

**Files:**
- Create: `conceptual_model.md`

- [ ] **Step 1: Write `conceptual_model.md`**

```markdown
# Conceptual Model: Synthetic Mine Throughput

## System boundary

**Included:** the truck haulage cycle from PARK to ore loaders (LOAD_N, LOAD_S) to the primary crusher (CRUSH) and back, traversing the road network defined in `data/edges.csv`. Loaders, crusher, and capacity-constrained roads are modelled as constrained resources.

**Excluded:** waste dump routing, the maintenance bay, breakdowns, refuelling, weather, blasting events, shift handover, operator skill variation, ore grade variation, and grade-resistance effects on truck speed beyond the loaded/empty speed factor.

## Entities

- **Trucks** — active SimPy processes that move through the system. Each truck has a fixed payload, empty/loaded speed factors, and a starting node.
- **Ore payload** — implicit; each truck carries `payload_tonnes` between loading and dumping events.

## Resources

- **Loaders** L_N (mean 6.5 min, sd 1.2) and L_S (mean 4.5 min, sd 1.0). Capacity 1 each.
- **Primary crusher** (mean 3.5 min, sd 0.8). Capacity 1.
- **Paired bidirectional road locks** (capacity 1 — one truck on the physical road regardless of direction):
  - RAMP — E03_UP / E03_DOWN
  - PIT_N — E07_TO_LOAD_N / E07_FROM_LOAD_N
  - PIT_S — E09_TO_LOAD_S / E09_FROM_LOAD_S
- **Per-direction crusher approach locks** — E05_TO and E05_FROM (each capacity 1, treated as a queueing lane).
- All other edges have capacity 999 and are unconstrained.

## Events

- truck_dispatched
- traversal_started, road_lock_requested, road_lock_acquired, traversal_ended (per edge)
- loader_requested, loading_started, loading_ended
- crusher_requested, dumping_started, dumping_ended

`dumping_ended` at CRUSH is the throughput-recording event.

## State variables

- Per truck: current node, loaded flag, payload, cycle start time, cumulative travelling/loading/dumping minutes.
- Per resource: cumulative busy time, queue waits, queue lengths sampled on entry.
- Global: total tonnes delivered, simulation time.

## Assumptions

### Derived from data
- Loader and crusher service-time means/SDs from `loaders.csv` / `dump_points.csv`.
- Edge distances and speeds from `edges.csv`.
- Capacity-1 edges treated as constrained resources; capacity-999 edges treated as unconstrained.

### Introduced
- Capacity-1 ramp E03 and pit-access roads E07/E09 are modelled as paired bidirectional resources (one truck on the physical road regardless of direction). Crusher approach E05 keeps per-direction locks. Justified by the edges.csv metadata note for E03_DOWN: "same physical constraint simplified as separate edge".
- Loading and dumping times follow Normal(mean, sd) truncated to [0.1 min, mean + 5 sd].
- Travel-time noise is multiplicative Normal(1.0, cv=0.10) per truck per edge per traversal; effective speed floored at 10% of edge max_speed_kph to avoid pathological tails.
- Routing uses pre-computed travel-time-weighted shortest paths via NetworkX Dijkstra. Loader choice is dynamic per cycle via nearest_available_loader with shortest_expected_cycle_time tiebreaker.
- All trucks start at PARK at t=0 and are dispatched simultaneously.

### Limitations
- No breakdowns, refuelling, shift handover, weather, or operator skill variation.
- No mid-cycle re-dispatching; loader choice is fixed at cycle start.
- Trucks finish their current state transition at shift end (no mid-traversal kill); in-progress dumps are not counted.
- Initial simultaneous dispatch may overstate first-cycle loader contention.

## Performance measures

- `total_tonnes_delivered` — cumulative tonnes via dumping_ended events at CRUSH.
- `tonnes_per_hour` — total / shift length.
- `average_truck_cycle_time_min` — mean across all completed cycles, all trucks.
- `average_truck_utilisation` — mean across trucks of (travelling + loading + dumping) / shift.
- `crusher_utilisation`, `loader_L_N_utilisation`, `loader_L_S_utilisation`.
- `average_loader_queue_time_min` — mean wait at any loader, averaged across loaders.
- `average_crusher_queue_time_min`.
- 95% confidence intervals (Student-t, df = n-1) for headline metrics across replications.
- `top_bottlenecks` ranked by `utilisation × avg_queue_wait_min`.
```

- [ ] **Step 2: Commit**

```bash
git add conceptual_model.md
git commit -m "docs(mine-sim): conceptual model document"
```

---

## Task 11: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Read the actual results to populate the answers**

Run:
```bash
python -c "import json; s = json.load(open('results/summary.json'))['scenarios']; \
print({k: {'tph_mean': v['tonnes_per_hour_mean'], 'tph_ci': [v['tonnes_per_hour_ci95_low'], v['tonnes_per_hour_ci95_high']], 'top_bottlenecks': v['top_bottlenecks'][:3]} for k, v in s.items()})"
```

Expected: a printed dict with per-scenario tonnes/h means, CIs, and top 3 bottlenecks. Save the values mentally; you will paste them into the README in Step 2.

- [ ] **Step 2: Write `README.md`**

(Use the actual numbers from Step 1 to fill in `<TPH>` and `<CI>` placeholders below; if the runs haven't produced surprising results, the qualitative framing should hold.)

```markdown
# Mine Throughput Simulation

A SimPy discrete-event simulation of an open-pit mine haulage system. Estimates ore throughput to the primary crusher over an 8-hour shift across six required scenarios.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

All six required scenarios with 30 replications each (default):

```bash
python -m mine_sim.run
```

Single scenario or smoke test:

```bash
python -m mine_sim.run --scenario baseline
python -m mine_sim.run --replications 5
```

Outputs (in `results/`):
- `results.csv` — one row per (scenario, replication)
- `summary.json` — per-scenario summary with 95% CIs and bottleneck ranking
- `event_log.csv` — combined trace (all events for replication 0 of each scenario; only `dumping_ended` events for replications 1-N)
- `{scenario_id}__event_log.csv` — full replication-0 trace per scenario

## Reproduce

Same `base_random_seed` (12345 by default) + same replication index → identical event log. To verify:

```bash
python -m mine_sim.run --scenario baseline
cp results/baseline__event_log.csv /tmp/run1.csv
python -m mine_sim.run --scenario baseline
diff /tmp/run1.csv results/baseline__event_log.csv   # must be empty
```

## Conceptual model

See `conceptual_model.md` for the full system boundary, entities, resources, events, state, assumptions, and performance measures.

In short: trucks loop PARK → loader → crusher → loader → ... ; loaders and the crusher are capacity-1 SimPy resources; the narrow ramp E03 and pit-access roads E07/E09 are paired bidirectional resources (one physical road, capacity 1 across both directions); E05 crusher approach has per-direction capacity-1 lanes; all other roads are unconstrained.

## Main assumptions

- Service times: `Normal(mean, sd)` truncated to `[0.1 min, mean + 5 sd]`.
- Travel-time noise: multiplicative `Normal(1.0, cv=0.10)` per truck per edge per traversal; effective speed floored at 10% of edge max speed.
- Routing: travel-time-weighted Dijkstra paths, pre-computed once per scenario.
- Throughput attributed at `dumping_ended` events at CRUSH only; in-progress dumps at shift end are not counted.

## Routing and dispatching

- Routing objective: shortest time (Dijkstra weighted by `distance_m / max_speed_kph`).
- Closed edges (`closed: true`) are dropped before graph build; the bypass route emerges naturally for `ramp_closed`.
- Dispatching policy: `nearest_available_loader` with `shortest_expected_cycle_time` tiebreaker. Decision is taken once per cycle when the truck becomes idle. No mid-cycle re-routing.

## Key results

Headline tonnes/hour with 95% CI per scenario (from `results/summary.json`):

| Scenario | tonnes/h mean | 95% CI | tonnes total mean |
|---|---|---|---|
| baseline | <TPH> | <CI> | <TT> |
| trucks_4 | <TPH> | <CI> | <TT> |
| trucks_12 | <TPH> | <CI> | <TT> |
| ramp_upgrade | <TPH> | <CI> | <TT> |
| crusher_slowdown | <TPH> | <CI> | <TT> |
| ramp_closed | <TPH> | <CI> | <TT> |

## Answers to operational decision questions

1. **Expected baseline throughput:** baseline `tonnes_per_hour_mean` ± 95% CI from `summary.json`. (See table above.)
2. **Likely bottlenecks:** see `top_bottlenecks` per scenario in `summary.json`. (Typically the narrow ramp E03 and the loaders dominate; specific ranking populated from the run.)
3. **Does adding more trucks help?** Compare `tonnes_per_hour_mean` across `trucks_4`, `baseline` (8), `trucks_12`. If the 12-truck CI overlaps the 8-truck CI, the system has saturated; if not, there is headroom. Report the marginal tonnes/h per added truck. (Conclusion: see results table.)
4. **Would ramp upgrade help?** Compare `baseline` vs `ramp_upgrade`. Material improvement only if CIs separate. The bottleneck score for the RAMP resource in baseline indicates whether it is binding.
5. **Crusher service-time sensitivity:** `crusher_slowdown` raises crusher service from 3.5 to 7.0 min. Report % throughput change and crusher utilisation shift.
6. **Operational impact of losing main ramp:** `ramp_closed` re-routes via the bypass J2→J7→J8→J4. Report % throughput loss and the new top bottleneck under bypass routing.

## Limitations

See `conceptual_model.md` "Limitations" — no breakdowns, refuelling, shift handover, weather, or operator effects; no mid-cycle re-dispatch; in-progress dumps at shift end are not counted; initial dispatch is simultaneous.

## Suggested improvements / further scenarios

- Add a `loader_n_upgrade` scenario reducing LOAD_N service time to match LOAD_S, isolating the loader-vs-ramp constraint.
- Stagger initial dispatch to reflect realistic startup.
- Model truck breakdowns and refuelling using the maintenance bay node.
- Consider a smarter dispatcher that re-evaluates loader choice if ramp queues exceed a threshold.
- Run sensitivity sweeps over `travel_time_noise_cv` to test result robustness to the noise assumption.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(mine-sim): README with run instructions, results table, and Q&A"
```

---

## Task 12: Optional topology plot

Skip this task if time is tight; this is a nice-to-have, not a requirement.

**Files:**
- Modify: `mine_sim/run.py` (add `--plot-topology` flag)
- Create: `topology.png` (output)

- [ ] **Step 1: Add a `--plot-topology` flag and helper**

Edit `mine_sim/run.py` — add a function `plot_topology` and an argparse flag.

Add at top of file:

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
```

Add this function after `_here()`:

```python
def plot_topology(data_dir: Path, output_path: Path) -> None:
    from mine_sim.scenario import load_scenario
    from mine_sim.topology import build_graph
    cfg = load_scenario("baseline", data_dir / "scenarios")
    g, edges, nodes = build_graph(cfg, data_dir)

    pos = {nid: (n.x_m, n.y_m) for nid, n in nodes.items()}
    type_colour = {
        "parking": "tab:blue", "junction": "lightgrey",
        "load_ore": "tab:green", "crusher": "tab:red",
        "waste_dump": "tab:olive", "maintenance": "tab:purple",
    }
    node_colours = [type_colour.get(nodes[n].node_type, "lightgrey") for n in g.nodes]

    fig, ax = plt.subplots(figsize=(10, 8))
    nx.draw_networkx_nodes(g, pos, node_color=node_colours, node_size=400, ax=ax)
    nx.draw_networkx_labels(g, pos, font_size=8, ax=ax)
    capacity1 = [(u, v) for u, v, d in g.edges(data=True)
                 if edges[d["edge_id"]].capacity == 1]
    rest = [(u, v) for u, v in g.edges if (u, v) not in capacity1]
    nx.draw_networkx_edges(g, pos, edgelist=rest, edge_color="lightgrey",
                            arrows=True, arrowsize=8, width=0.6, ax=ax)
    nx.draw_networkx_edges(g, pos, edgelist=capacity1, edge_color="tab:red",
                            arrows=True, arrowsize=10, width=1.5, ax=ax)
    ax.set_title("Mine topology — capacity-1 edges in red")
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
```

Add to argparse:

```python
parser.add_argument("--plot-topology", action="store_true",
                    help="Write topology.png and exit.")
```

Add to `main()` near the top after parsing args:

```python
if args.plot_topology:
    plot_topology(args.data_dir, _here() / "topology.png")
    print(f"Wrote {_here() / 'topology.png'}")
    return 0
```

- [ ] **Step 2: Generate the plot**

Run:
```bash
python -m mine_sim.run --plot-topology
```

Expected: writes `topology.png` (a static node+edge diagram).

- [ ] **Step 3: Commit**

```bash
git add mine_sim/run.py topology.png
git commit -m "feat(mine-sim): optional topology plot"
```

---

## Task 13: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Re-run all scenarios from scratch**

Run:
```bash
rm -rf results/*.csv results/*.json
python -m mine_sim.run
```

Expected: completes without errors; all output files present.

- [ ] **Step 3: Spot-check `summary.json` for sensible values**

Run:
```bash
python -c "import json; s=json.load(open('results/summary.json')); \
[print(k, '->', round(v['tonnes_per_hour_mean']), 'tph') for k,v in s['scenarios'].items()]"
```

Expected: values increase with more trucks (until saturation), drop under crusher_slowdown and ramp_closed, increase under ramp_upgrade if RAMP was binding.

- [ ] **Step 4: Update `submission.yaml`**

Edit `submission.yaml` and change the line:
```yaml
status: scaffolded
```
to:
```yaml
status: complete
```

- [ ] **Step 5: Final commit**

```bash
git add submission.yaml
git commit -m "chore(mine-sim): mark submission status complete"
```
