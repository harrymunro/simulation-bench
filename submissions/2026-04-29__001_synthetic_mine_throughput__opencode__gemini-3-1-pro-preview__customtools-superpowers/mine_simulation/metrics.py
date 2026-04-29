import pandas as pd

def calculate_advanced_metrics(events_df: pd.DataFrame, shift_hours: int, replications: int = 1):
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
        metrics['crusher_utilisation'] = total_crush_time / (replications * shift_hours * 60)

    # Calculate queues
    queue_crush = []
    starts = events_df[events_df['event_type'] == 'queue_dump_start']
    ends = events_df[events_df['event_type'] == 'dump_start']
    for _, s in starts.iterrows():
        e = ends[(ends['truck_id'] == s['truck_id']) & (ends['time_min'] >= s['time_min'])].head(1)
        if not e.empty:
            queue_crush.append(e.iloc[0]['time_min'] - s['time_min'])
    metrics['average_crusher_queue_time_min'] = sum(queue_crush)/len(queue_crush) if queue_crush else 0

    # Add similar logic for loader utilisation and queues
    loader_starts = events_df[events_df['event_type'] == 'load_start']
    loader_ends = events_df[events_df['event_type'] == 'load_end']
    
    loader_util = {}
    for l_id in loader_starts['resource_id'].unique():
        l_starts = loader_starts[loader_starts['resource_id'] == l_id]
        l_ends = loader_ends[loader_ends['resource_id'] == l_id]
        total_l_time = 0
        for _, s in l_starts.iterrows():
            e = l_ends[(l_ends['truck_id'] == s['truck_id']) & (l_ends['time_min'] >= s['time_min'])].head(1)
            if not e.empty:
                total_l_time += (e.iloc[0]['time_min'] - s['time_min'])
        loader_util[str(l_id)] = total_l_time / (replications * shift_hours * 60)
    metrics['loader_utilisation'] = loader_util

    queue_load = []
    l_q_starts = events_df[events_df['event_type'] == 'queue_load_start']
    l_q_ends = events_df[events_df['event_type'] == 'load_start']
    for _, s in l_q_starts.iterrows():
        e = l_q_ends[(l_q_ends['truck_id'] == s['truck_id']) & (l_q_ends['time_min'] >= s['time_min'])].head(1)
        if not e.empty:
            queue_load.append(e.iloc[0]['time_min'] - s['time_min'])
    metrics['average_loader_queue_time_min'] = sum(queue_load)/len(queue_load) if queue_load else 0

    return metrics