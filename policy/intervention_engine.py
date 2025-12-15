"""
Policy & Intervention Engine for Urban Transport Digital Twin
Implements controlled, reversible interventions for traffic policy simulation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import copy
from models.city_model import CityNetwork, VehicleClass


class InterventionType(Enum):
    BUS_LANE_ADD = "bus_lane_add"
    BUS_LANE_REMOVE = "bus_lane_remove"
    SIGNAL_TIMING = "signal_timing"
    VEHICLE_RESTRICTION = "vehicle_restriction"
    DEMAND_CHANGE = "demand_change"
    SPEED_LIMIT_CHANGE = "speed_limit_change"
    LANE_COUNT_CHANGE = "lane_count_change"


@dataclass
class Intervention:
    """Represents a single policy intervention"""
    id: str
    intervention_type: InterventionType
    target_id: str  # Edge or node ID
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.intervention_type.value,
            "target_id": self.target_id,
            "parameters": self.parameters,
            "description": self.description
        }


class InterventionEngine:
    """Manages and applies policy interventions to the network"""
    
    def __init__(self, network: CityNetwork):
        self.original_network = network
        self.interventions: List[Intervention] = []
        self.applied_changes: Dict[str, Dict] = {}
    
    def add_intervention(self, intervention: Intervention) -> None:
        """Add an intervention to the queue"""
        self.interventions.append(intervention)
    
    def clear_interventions(self) -> None:
        """Clear all interventions"""
        self.interventions = []
        self.applied_changes = {}
    
    def apply_interventions(self, network: CityNetwork) -> CityNetwork:
        """Apply all interventions to a network copy and return modified network"""
        modified_network = self._deep_copy_network(network)
        
        for intervention in self.interventions:
            self._apply_single_intervention(modified_network, intervention)
        
        return modified_network
    
    def _deep_copy_network(self, network: CityNetwork) -> CityNetwork:
        """Create a deep copy of the network"""
        new_network = CityNetwork()
        for node in network.nodes.values():
            new_node = copy.deepcopy(node)
            new_network.add_node(new_node)
        for edge in network.edges.values():
            new_edge = copy.deepcopy(edge)
            new_network.add_edge(new_edge)
        return new_network
    
    def _apply_single_intervention(self, network: CityNetwork, intervention: Intervention) -> None:
        """Apply a single intervention to the network"""
        
        if intervention.intervention_type == InterventionType.BUS_LANE_ADD:
            self._apply_bus_lane(network, intervention.target_id, add=True)
        
        elif intervention.intervention_type == InterventionType.BUS_LANE_REMOVE:
            self._apply_bus_lane(network, intervention.target_id, add=False)
        
        elif intervention.intervention_type == InterventionType.SIGNAL_TIMING:
            self._apply_signal_timing(network, intervention.target_id, intervention.parameters)
        
        elif intervention.intervention_type == InterventionType.VEHICLE_RESTRICTION:
            self._apply_vehicle_restriction(network, intervention.target_id, intervention.parameters)
        
        elif intervention.intervention_type == InterventionType.SPEED_LIMIT_CHANGE:
            self._apply_speed_limit_change(network, intervention.target_id, intervention.parameters)
        
        elif intervention.intervention_type == InterventionType.LANE_COUNT_CHANGE:
            self._apply_lane_count_change(network, intervention.target_id, intervention.parameters)
        
        self.applied_changes[intervention.id] = {
            "type": intervention.intervention_type.value,
            "target": intervention.target_id,
            "params": intervention.parameters
        }
    
    def _apply_bus_lane(self, network: CityNetwork, edge_id: str, add: bool) -> None:
        """Add or remove a bus lane on an edge"""
        edge = network.edges.get(edge_id)
        if edge:
            edge.has_bus_lane = add
    
    def _apply_signal_timing(self, network: CityNetwork, node_id: str, params: Dict) -> None:
        """Modify signal timing at a node"""
        node = network.nodes.get(node_id)
        if node:
            if "green" in params:
                node.signal_timing["green"] = params["green"]
            if "yellow" in params:
                node.signal_timing["yellow"] = params["yellow"]
            if "red" in params:
                node.signal_timing["red"] = params["red"]
    
    def _apply_vehicle_restriction(self, network: CityNetwork, edge_id: str, params: Dict) -> None:
        """Apply vehicle class restriction to an edge"""
        edge = network.edges.get(edge_id)
        if edge:
            restricted_classes = params.get("restricted_classes", [])
            edge.restricted_classes = [
                VehicleClass(vc) if isinstance(vc, str) else vc 
                for vc in restricted_classes
            ]
    
    def _apply_speed_limit_change(self, network: CityNetwork, edge_id: str, params: Dict) -> None:
        """Change speed limit on an edge"""
        edge = network.edges.get(edge_id)
        if edge and "speed_limit" in params:
            edge.speed_limit = params["speed_limit"]
    
    def _apply_lane_count_change(self, network: CityNetwork, edge_id: str, params: Dict) -> None:
        """Change lane count on an edge"""
        edge = network.edges.get(edge_id)
        if edge and "lane_count" in params:
            edge.lane_count = max(1, params["lane_count"])
    
    def get_intervention_summary(self) -> List[Dict]:
        """Get summary of all interventions"""
        return [i.to_dict() for i in self.interventions]
    
    def create_bus_lane_intervention(self, edge_id: str, add: bool = True) -> Intervention:
        """Helper to create a bus lane intervention"""
        int_type = InterventionType.BUS_LANE_ADD if add else InterventionType.BUS_LANE_REMOVE
        action = "Add" if add else "Remove"
        return Intervention(
            id=f"bus_lane_{edge_id}",
            intervention_type=int_type,
            target_id=edge_id,
            description=f"{action} bus lane on edge {edge_id}"
        )
    
    def create_signal_timing_intervention(
        self, 
        node_id: str, 
        green: Optional[int] = None,
        yellow: Optional[int] = None,
        red: Optional[int] = None
    ) -> Intervention:
        """Helper to create a signal timing intervention"""
        params = {}
        if green is not None:
            params["green"] = green
        if yellow is not None:
            params["yellow"] = yellow
        if red is not None:
            params["red"] = red
        
        return Intervention(
            id=f"signal_{node_id}",
            intervention_type=InterventionType.SIGNAL_TIMING,
            target_id=node_id,
            parameters=params,
            description=f"Modify signal timing at node {node_id}: {params}"
        )
    
    def create_restriction_intervention(
        self, 
        edge_id: str, 
        restricted_classes: List[str]
    ) -> Intervention:
        """Helper to create a vehicle restriction intervention"""
        return Intervention(
            id=f"restrict_{edge_id}",
            intervention_type=InterventionType.VEHICLE_RESTRICTION,
            target_id=edge_id,
            parameters={"restricted_classes": restricted_classes},
            description=f"Restrict {restricted_classes} on edge {edge_id}"
        )
    
    def create_speed_limit_intervention(self, edge_id: str, speed_limit: float) -> Intervention:
        """Helper to create a speed limit change intervention"""
        return Intervention(
            id=f"speed_{edge_id}",
            intervention_type=InterventionType.SPEED_LIMIT_CHANGE,
            target_id=edge_id,
            parameters={"speed_limit": speed_limit},
            description=f"Change speed limit on edge {edge_id} to {speed_limit} m/s"
        )
