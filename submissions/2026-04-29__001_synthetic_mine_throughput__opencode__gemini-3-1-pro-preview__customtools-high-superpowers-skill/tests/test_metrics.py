from src.metrics import EventLogger, SimulationMetrics

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
