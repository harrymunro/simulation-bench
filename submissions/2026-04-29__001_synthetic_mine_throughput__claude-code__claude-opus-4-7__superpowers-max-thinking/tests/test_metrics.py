"""Tests for the metrics collector and CI helper."""
import pytest

from mine_sim.metrics import MetricsCollector, ci95_t


def test_ci95_t_known_values():
    values = [100.0] * 15 + [90.0, 110.0] * 7 + [100.0]   # 30 values, mean ~ 100
    mean, lo, hi = ci95_t(values)
    assert mean == pytest.approx(sum(values) / len(values))
    assert lo < mean < hi
    assert (hi - mean) == pytest.approx(mean - lo)


def test_ci95_t_handles_zero_std():
    values = [5.0] * 10
    mean, lo, hi = ci95_t(values)
    assert mean == lo == hi == 5.0


def test_ci95_t_handles_single_value():
    mean, lo, hi = ci95_t([42.0])
    assert mean == lo == hi == 42.0


def test_ci95_t_handles_empty_list():
    mean, lo, hi = ci95_t([])
    assert mean == lo == hi == 0.0


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


def test_avg_queue_wait_no_records_returns_zero():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    assert m.avg_queue_wait("never_used") == 0.0


def test_tonnes_recording_and_throughput():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.record_dump(time_min=10.0, truck_id="T01", payload_tonnes=100.0)
    m.record_dump(time_min=20.0, truck_id="T02", payload_tonnes=100.0)
    assert m.total_tonnes() == 200.0
    assert m.tonnes_per_hour() == pytest.approx(200.0 / 8)


def test_average_cycle_time_min():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    m.truck("T01").cycle_times_min.extend([20.0, 22.0])
    m.truck("T02").cycle_times_min.extend([18.0])
    assert m.average_cycle_time_min() == pytest.approx((20 + 22 + 18) / 3)


def test_average_truck_utilisation():
    m = MetricsCollector(scenario_id="baseline", replication=0, shift_minutes=480)
    t = m.truck("T01")
    t.travelling_minutes = 240.0
    t.loading_minutes = 60.0
    t.dumping_minutes = 60.0
    # truck busy 360/480 = 0.75
    assert m.average_truck_utilisation() == pytest.approx(0.75)


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
