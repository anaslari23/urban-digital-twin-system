"""
City Data Model for Urban Transport Digital Twin
Graph-based city model with nodes (intersections), edges (roads), and vehicle agents.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json
import networkx as nx


class VehicleClass(Enum):
    CAR = "car"
    BUS = "bus"
    RESTRICTED = "restricted"


class SignalPhase(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class TurnRule:
    """Turn rules at an intersection"""
    allowed_directions: List[str] = field(default_factory=lambda: ["straight", "left", "right"])
    restricted_classes: List[VehicleClass] = field(default_factory=list)


@dataclass
class Node:
    """Intersection node in the city network"""
    id: str
    x: float
    y: float
    signal_phases: Dict[str, SignalPhase] = field(default_factory=dict)
    signal_timing: Dict[str, int] = field(default_factory=lambda: {"green": 30, "yellow": 5, "red": 25})
    queue_lengths: Dict[str, int] = field(default_factory=dict)
    turn_rules: Dict[str, TurnRule] = field(default_factory=dict)
    is_entry_node: bool = False
    is_exit_node: bool = False
    current_phase_time: int = 0
    
    def get_current_signal(self, direction: str) -> SignalPhase:
        return self.signal_phases.get(direction, SignalPhase.RED)
    
    def update_signal(self, time_step: int) -> None:
        """Update signal phase based on timing"""
        cycle_length = sum(self.signal_timing.values())
        self.current_phase_time = time_step % cycle_length
        
        green_end = self.signal_timing["green"]
        yellow_end = green_end + self.signal_timing["yellow"]
        
        for direction in self.signal_phases:
            if self.current_phase_time < green_end:
                self.signal_phases[direction] = SignalPhase.GREEN
            elif self.current_phase_time < yellow_end:
                self.signal_phases[direction] = SignalPhase.YELLOW
            else:
                self.signal_phases[direction] = SignalPhase.RED
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "signal_timing": self.signal_timing,
            "is_entry_node": self.is_entry_node,
            "is_exit_node": self.is_exit_node
        }


@dataclass
class Edge:
    """Road segment connecting two intersections"""
    id: str
    from_node: str
    to_node: str
    length: float  # meters
    lane_count: int
    speed_limit: float  # m/s
    capacity: int  # vehicles per lane
    current_vehicles: int = 0
    has_bus_lane: bool = False
    restricted_classes: List[VehicleClass] = field(default_factory=list)
    
    @property
    def total_capacity(self) -> int:
        effective_lanes = self.lane_count - (1 if self.has_bus_lane else 0)
        return max(1, effective_lanes) * self.capacity
    
    @property
    def travel_time(self) -> float:
        """Base travel time in seconds"""
        return self.length / self.speed_limit
    
    @property
    def congestion_factor(self) -> float:
        """Congestion multiplier based on current load"""
        if self.total_capacity == 0:
            return 1.0
        load = self.current_vehicles / self.total_capacity
        if load < 0.5:
            return 1.0
        elif load < 0.8:
            return 1.0 + (load - 0.5) * 2
        elif load < 1.0:
            return 1.6 + (load - 0.8) * 5
        else:
            return 2.6 + (load - 1.0) * 10
    
    @property
    def actual_travel_time(self) -> float:
        """Travel time adjusted for congestion"""
        return self.travel_time * self.congestion_factor
    
    def can_accept_vehicle(self, vehicle_class: VehicleClass) -> bool:
        if vehicle_class in self.restricted_classes:
            return False
        if self.has_bus_lane and vehicle_class == VehicleClass.BUS:
            return True
        return self.current_vehicles < self.total_capacity * 1.5
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "length": self.length,
            "lane_count": self.lane_count,
            "speed_limit": self.speed_limit,
            "capacity": self.capacity,
            "has_bus_lane": self.has_bus_lane
        }


@dataclass
class Vehicle:
    """Vehicle agent in the simulation"""
    id: str
    vehicle_class: VehicleClass
    route: List[str]  # List of edge IDs
    current_edge_index: int = 0
    position_on_edge: float = 0.0  # 0.0 to 1.0
    accumulated_delay: float = 0.0
    spawn_time: int = 0
    completion_time: int = 0
    completed: bool = False
    
    @property
    def current_edge(self) -> Optional[str]:
        if self.current_edge_index < len(self.route):
            return self.route[self.current_edge_index]
        return None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_class": self.vehicle_class.value,
            "route": self.route,
            "current_edge_index": self.current_edge_index,
            "position_on_edge": self.position_on_edge,
            "accumulated_delay": self.accumulated_delay,
            "spawn_time": self.spawn_time,
            "completed": self.completed
        }


class CityNetwork:
    """Complete city network model using NetworkX"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}
        self.vehicles: Dict[str, Vehicle] = {}
        self.entry_nodes: List[str] = []
        self.exit_nodes: List[str] = []
    
    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        self.graph.add_node(node.id, x=node.x, y=node.y)
        if node.is_entry_node:
            self.entry_nodes.append(node.id)
        if node.is_exit_node:
            self.exit_nodes.append(node.id)
    
    def add_edge(self, edge: Edge) -> None:
        self.edges[edge.id] = edge
        self.graph.add_edge(
            edge.from_node, 
            edge.to_node, 
            edge_id=edge.id,
            weight=edge.length
        )
    
    def get_shortest_path(self, start: str, end: str) -> List[str]:
        """Get shortest path as list of edge IDs"""
        try:
            node_path = nx.shortest_path(self.graph, start, end, weight='weight')
            edge_path = []
            for i in range(len(node_path) - 1):
                edge_data = self.graph.get_edge_data(node_path[i], node_path[i+1])
                if edge_data:
                    edge_path.append(edge_data['edge_id'])
            return edge_path
        except nx.NetworkXNoPath:
            return []
    
    def get_node_positions(self) -> Dict[str, Tuple[float, float]]:
        """Get node positions for visualization"""
        return {node_id: (node.x, node.y) for node_id, node in self.nodes.items()}
    
    def reset(self) -> None:
        """Reset network state for new simulation"""
        for edge in self.edges.values():
            edge.current_vehicles = 0
        for node in self.nodes.values():
            node.queue_lengths = {}
            node.current_phase_time = 0
        self.vehicles = {}
    
    def to_dict(self) -> dict:
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()]
        }
    
    def save_to_json(self, filepath: str) -> None:
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_json(cls, filepath: str) -> 'CityNetwork':
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        network = cls()
        
        for node_data in data.get("nodes", []):
            node = Node(
                id=node_data["id"],
                x=node_data["x"],
                y=node_data["y"],
                signal_timing=node_data.get("signal_timing", {"green": 30, "yellow": 5, "red": 25}),
                is_entry_node=node_data.get("is_entry_node", False),
                is_exit_node=node_data.get("is_exit_node", False)
            )
            for direction in ["north", "south", "east", "west"]:
                node.signal_phases[direction] = SignalPhase.RED
            network.add_node(node)
        
        for edge_data in data.get("edges", []):
            edge = Edge(
                id=edge_data["id"],
                from_node=edge_data["from_node"],
                to_node=edge_data["to_node"],
                length=edge_data["length"],
                lane_count=edge_data["lane_count"],
                speed_limit=edge_data["speed_limit"],
                capacity=edge_data["capacity"],
                has_bus_lane=edge_data.get("has_bus_lane", False)
            )
            network.add_edge(edge)
        
        return network
