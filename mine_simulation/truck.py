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
