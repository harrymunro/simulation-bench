import pandas as pd

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
