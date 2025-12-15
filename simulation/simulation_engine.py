"""
Simulation Engine for Urban Transport Digital Twin
Discrete-event traffic simulation with congestion, queues, and bottleneck emergence.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
import copy
from models.city_model import CityNetwork, Vehicle, Edge, Node, VehicleClass, SignalPhase
from simulation.demand_generator import DemandGenerator, DemandProfile, create_default_profiles
from simulation.metrics_collector import MetricsCollector


@dataclass
class SimulationConfig:
    """Configuration for simulation run"""
    duration_seconds: int = 3600
    time_step_seconds: int = 1
    seed: int = 42
    demand_multiplier: float = 1.0
    custom_profiles: Optional[List[DemandProfile]] = None


@dataclass
class SimulationState:
    """Snapshot of simulation state at a time step"""
    time_step: int
    vehicles: Dict[str, dict]
    edge_loads: Dict[str, int]
    edge_congestion: Dict[str, float]
    queue_lengths: Dict[str, Dict[str, int]]
    signal_phases: Dict[str, Dict[str, str]]
    
    def to_dict(self) -> dict:
        return {
            "time_step": self.time_step,
            "vehicles": self.vehicles,
            "edge_loads": self.edge_loads,
            "edge_congestion": self.edge_congestion,
            "queue_lengths": self.queue_lengths,
            "signal_phases": self.signal_phases
        }


class SimulationEngine:
    """Discrete-event simulation engine for traffic"""
    
    def __init__(self, network: CityNetwork, config: SimulationConfig):
        self.original_network = network
        self.network = self._deep_copy_network(network)
        self.config = config
        self.demand_generator = DemandGenerator(self.network, config.seed)
        self.metrics = MetricsCollector()
        self.current_time = 0
        self.states: List[SimulationState] = []
        self.active_vehicles: Dict[str, Vehicle] = {}
        self.completed_vehicles: List[Vehicle] = []
        self._setup_demand()
    
    def _deep_copy_network(self, network: CityNetwork) -> CityNetwork:
        """Create a deep copy of network for simulation"""
        new_network = CityNetwork()
        for node in network.nodes.values():
            new_node = copy.deepcopy(node)
            new_network.add_node(new_node)
        for edge in network.edges.values():
            new_edge = copy.deepcopy(edge)
            new_network.add_edge(new_edge)
        return new_network
    
    def _setup_demand(self) -> None:
        """Setup demand profiles"""
        if self.config.custom_profiles:
            for profile in self.config.custom_profiles:
                adjusted_profile = copy.deepcopy(profile)
                adjusted_profile.vehicles_per_minute *= self.config.demand_multiplier
                self.demand_generator.add_profile(adjusted_profile)
        else:
            profiles = create_default_profiles(self.config.duration_seconds)
            for profile in profiles:
                profile.vehicles_per_minute *= self.config.demand_multiplier
                self.demand_generator.add_profile(profile)
    
    def reset(self) -> None:
        """Reset simulation to initial state"""
        self.network = self._deep_copy_network(self.original_network)
        self.demand_generator = DemandGenerator(self.network, self.config.seed)
        self._setup_demand()
        self.metrics = MetricsCollector()
        self.current_time = 0
        self.states = []
        self.active_vehicles = {}
        self.completed_vehicles = []
    
    def step(self) -> SimulationState:
        """Execute one simulation time step"""
        dt = self.config.time_step_seconds
        
        self._update_signals()
        
        new_vehicles = self.demand_generator.generate_vehicles(self.current_time, dt)
        for vehicle in new_vehicles:
            self._spawn_vehicle(vehicle)
        
        self._move_vehicles(dt)
        
        self._update_queues()
        
        state = self._capture_state()
        self.states.append(state)
        
        self._record_metrics()
        
        self.current_time += dt
        
        return state
    
    def _update_signals(self) -> None:
        """Update traffic signals at all intersections"""
        for node in self.network.nodes.values():
            node.update_signal(self.current_time)
    
    def _spawn_vehicle(self, vehicle: Vehicle) -> None:
        """Spawn a vehicle into the network"""
        if vehicle.route:
            first_edge_id = vehicle.route[0]
            edge = self.network.edges.get(first_edge_id)
            if edge and edge.can_accept_vehicle(vehicle.vehicle_class):
                edge.current_vehicles += 1
                self.active_vehicles[vehicle.id] = vehicle
                self.network.vehicles[vehicle.id] = vehicle
    
    def _move_vehicles(self, dt: int) -> None:
        """Move all active vehicles"""
        vehicles_to_remove = []
        
        for vehicle_id, vehicle in list(self.active_vehicles.items()):
            if vehicle.completed:
                vehicles_to_remove.append(vehicle_id)
                continue
            
            current_edge_id = vehicle.current_edge
            if not current_edge_id:
                vehicle.completed = True
                vehicle.completion_time = self.current_time
                vehicles_to_remove.append(vehicle_id)
                continue
            
            edge = self.network.edges.get(current_edge_id)
            if not edge:
                continue
            
            actual_travel_time = edge.actual_travel_time
            progress = dt / actual_travel_time if actual_travel_time > 0 else 1.0
            
            base_travel_time = edge.travel_time
            delay_this_step = max(0, dt - (base_travel_time * progress))
            vehicle.accumulated_delay += delay_this_step
            
            vehicle.position_on_edge += progress
            
            if vehicle.position_on_edge >= 1.0:
                self._try_advance_vehicle(vehicle, edge)
                if vehicle.completed:
                    vehicle.completion_time = self.current_time
                    vehicles_to_remove.append(vehicle_id)
        
        for vehicle_id in vehicles_to_remove:
            if vehicle_id in self.active_vehicles:
                vehicle = self.active_vehicles.pop(vehicle_id)
                self.completed_vehicles.append(vehicle)
                if vehicle_id in self.network.vehicles:
                    del self.network.vehicles[vehicle_id]
                travel_time = vehicle.completion_time - vehicle.spawn_time
                self.metrics.record_vehicle_completion(
                    vehicle_id=vehicle.id,
                    travel_time=travel_time,
                    accumulated_delay=vehicle.accumulated_delay
                )
    
    def _try_advance_vehicle(self, vehicle: Vehicle, current_edge: Edge) -> None:
        """Try to move vehicle to next edge"""
        to_node_id = current_edge.to_node
        to_node = self.network.nodes.get(to_node_id)
        
        if to_node and to_node.is_exit_node:
            current_edge.current_vehicles = max(0, current_edge.current_vehicles - 1)
            vehicle.completed = True
            vehicle.current_edge_index = len(vehicle.route)
            return
        
        can_pass = True
        if to_node:
            for direction, phase in to_node.signal_phases.items():
                if phase == SignalPhase.RED:
                    can_pass = False
                    break
        
        if not can_pass:
            vehicle.position_on_edge = 1.0
            queue_key = current_edge.id
            to_node.queue_lengths[queue_key] = to_node.queue_lengths.get(queue_key, 0) + 1
            return
        
        next_edge_index = vehicle.current_edge_index + 1
        if next_edge_index >= len(vehicle.route):
            current_edge.current_vehicles = max(0, current_edge.current_vehicles - 1)
            vehicle.completed = True
            vehicle.current_edge_index = len(vehicle.route)
            return
        
        next_edge_id = vehicle.route[next_edge_index]
        next_edge = self.network.edges.get(next_edge_id)
        
        if next_edge and next_edge.can_accept_vehicle(vehicle.vehicle_class):
            current_edge.current_vehicles = max(0, current_edge.current_vehicles - 1)
            next_edge.current_vehicles += 1
            vehicle.current_edge_index = next_edge_index
            vehicle.position_on_edge = 0.0
            
            if to_node:
                queue_key = current_edge.id
                to_node.queue_lengths[queue_key] = max(0, to_node.queue_lengths.get(queue_key, 0) - 1)
        else:
            vehicle.position_on_edge = 1.0
            if to_node:
                queue_key = current_edge.id
                to_node.queue_lengths[queue_key] = to_node.queue_lengths.get(queue_key, 0) + 1
    
    def _update_queues(self) -> None:
        """Update queue lengths at intersections"""
        for node_id, node in self.network.nodes.items():
            for edge_id, queue_length in node.queue_lengths.items():
                if queue_length > 0:
                    edge = self.network.edges.get(edge_id)
                    if edge:
                        spillback_threshold = edge.total_capacity * 0.8
                        if queue_length > spillback_threshold:
                            upstream_edge = self._find_upstream_edge(edge.from_node)
                            if upstream_edge:
                                upstream_edge.current_vehicles = min(
                                    upstream_edge.current_vehicles + 1,
                                    int(upstream_edge.total_capacity * 1.5)
                                )
    
    def _find_upstream_edge(self, node_id: str) -> Optional[Edge]:
        """Find an upstream edge leading to a node"""
        for edge in self.network.edges.values():
            if edge.to_node == node_id:
                return edge
        return None
    
    def _capture_state(self) -> SimulationState:
        """Capture current simulation state"""
        vehicles = {v_id: v.to_dict() for v_id, v in self.active_vehicles.items()}
        edge_loads = {e_id: e.current_vehicles for e_id, e in self.network.edges.items()}
        edge_congestion = {e_id: e.congestion_factor for e_id, e in self.network.edges.items()}
        queue_lengths = {n_id: dict(n.queue_lengths) for n_id, n in self.network.nodes.items()}
        signal_phases = {
            n_id: {d: p.value for d, p in n.signal_phases.items()}
            for n_id, n in self.network.nodes.items()
        }
        
        return SimulationState(
            time_step=self.current_time,
            vehicles=vehicles,
            edge_loads=edge_loads,
            edge_congestion=edge_congestion,
            queue_lengths=queue_lengths,
            signal_phases=signal_phases
        )
    
    def _record_metrics(self) -> None:
        """Record metrics for current time step"""
        total_queue = sum(
            sum(q.values()) for q in 
            [n.queue_lengths for n in self.network.nodes.values()]
        )
        avg_congestion = sum(e.congestion_factor for e in self.network.edges.values()) / max(1, len(self.network.edges))
        
        bottlenecks = [
            e_id for e_id, e in self.network.edges.items()
            if e.congestion_factor > 1.5
        ]
        
        self.metrics.record_step(
            time_step=self.current_time,
            active_vehicles=len(self.active_vehicles),
            completed_vehicles=len(self.completed_vehicles),
            total_queue_length=total_queue,
            average_congestion=avg_congestion,
            bottleneck_edges=bottlenecks,
            edge_loads={e_id: e.current_vehicles for e_id, e in self.network.edges.items()}
        )
    
    def run(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict:
        """Run complete simulation"""
        self.reset()
        total_steps = self.config.duration_seconds // self.config.time_step_seconds
        
        for step in range(total_steps):
            self.step()
            if progress_callback and step % 10 == 0:
                progress_callback(step, total_steps)
        
        return self.metrics.get_summary()
    
    def get_state_at(self, time_step: int) -> Optional[SimulationState]:
        """Get simulation state at specific time"""
        step_index = time_step // self.config.time_step_seconds
        if 0 <= step_index < len(self.states):
            return self.states[step_index]
        return None
