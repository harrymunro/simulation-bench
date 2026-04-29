import pandas as pd
from mine_simulation.metrics import calculate_advanced_metrics

def test_calculate_advanced_metrics_empty():
    df = pd.DataFrame(columns=['time_min', 'truck_id', 'event_type', 'resource_id'])
    metrics = calculate_advanced_metrics(df, 12)
    
    assert metrics['average_cycle_time_min'] == 0
    assert metrics['truck_utilisation_mean'] == 0
    assert metrics['loader_utilisation'] == {}
    assert metrics['crusher_utilisation'] == 0
    assert metrics['average_loader_queue_time_min'] == 0
    assert metrics['average_crusher_queue_time_min'] == 0
    assert metrics['top_bottlenecks'] == []

def test_calculate_advanced_metrics_with_data():
    data = [
        {'time_min': 10, 'truck_id': 'T1', 'event_type': 'queue_load_start', 'resource_id': None},
        {'time_min': 15, 'truck_id': 'T1', 'event_type': 'load_start', 'resource_id': 'L1'},
        {'time_min': 20, 'truck_id': 'T1', 'event_type': 'load_end', 'resource_id': 'L1'},
        
        {'time_min': 30, 'truck_id': 'T1', 'event_type': 'queue_dump_start', 'resource_id': None},
        {'time_min': 32, 'truck_id': 'T1', 'event_type': 'dump_start', 'resource_id': 'C1'},
        {'time_min': 35, 'truck_id': 'T1', 'event_type': 'dump_end', 'resource_id': 'C1'},
        
        # Second cycle for T1
        {'time_min': 50, 'truck_id': 'T1', 'event_type': 'queue_load_start', 'resource_id': None},
        {'time_min': 52, 'truck_id': 'T1', 'event_type': 'load_start', 'resource_id': 'L1'},
        {'time_min': 55, 'truck_id': 'T1', 'event_type': 'load_end', 'resource_id': 'L1'},
    ]
    df = pd.DataFrame(data)
    shift_hours = 1 # 60 minutes
    
    metrics = calculate_advanced_metrics(df, shift_hours)
    
    # Load queue times: (15-10) + (52-50) = 5 + 2 = 7. Avg = 3.5
    assert metrics['average_loader_queue_time_min'] == 3.5
    
    # Load utilisation: L1 active (20-15) + (55-52) = 5 + 3 = 8.
    # Utilisation = 8 / (1 * 60) = 8 / 60 ≈ 0.1333
    assert abs(metrics['loader_utilisation']['L1'] - (8.0 / 60)) < 0.001
    
    # Crusher queue times: (32-30) = 2. Avg = 2
    assert metrics['average_crusher_queue_time_min'] == 2.0
    
    # Crusher utilisation: (35-32) = 3.
    # Utilisation = 3 / (1 * 60) = 3 / 60 = 0.05
    assert abs(metrics['crusher_utilisation'] - (3.0 / 60)) < 0.001
