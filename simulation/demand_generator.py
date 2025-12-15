"""
Demand Generator for Urban Transport Digital Twin
Handles vehicle spawning with peak/off-peak patterns and reproducible randomization.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import random
import numpy as np
from models.city_model import Vehicle, VehicleClass, CityNetwork


@dataclass
class DemandProfile:
    """Defines demand pattern for a time period"""
    start_time: int  # seconds from simulation start
    end_time: int
    vehicles_per_minute: float
    vehicle_class_distribution: Dict[VehicleClass, float] = field(
        default_factory=lambda: {
            VehicleClass.CAR: 0.85,
            VehicleClass.BUS: 0.10,
            VehicleClass.RESTRICTED: 0.05
        }
    )
    entry_node_weights: Dict[str, float] = field(default_factory=dict)
    exit_node_weights: Dict[str, float] = field(default_factory=dict)


class DemandGenerator:
    """Generates vehicle demand based on time-varying profiles"""
    
    def __init__(self, network: CityNetwork, seed: int = 42):
        self.network = network
        self.seed = seed
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.profiles: List[DemandProfile] = []
        self.vehicle_counter = 0
        self.spawn_accumulator = 0.0
    
    def add_profile(self, profile: DemandProfile) -> None:
        """Add a demand profile"""
        if not profile.entry_node_weights:
            profile.entry_node_weights = {
                node_id: 1.0 for node_id in self.network.entry_nodes
            }
        if not profile.exit_node_weights:
            profile.exit_node_weights = {
                node_id: 1.0 for node_id in self.network.exit_nodes
            }
        self.profiles.append(profile)
    
    def get_active_profile(self, time_step: int) -> Optional[DemandProfile]:
        """Get the active demand profile for current time"""
        for profile in self.profiles:
            if profile.start_time <= time_step < profile.end_time:
                return profile
        return None
    
    def _select_weighted(self, weights: Dict[str, float]) -> str:
        """Select an item based on weights"""
        items = list(weights.keys())
        probs = np.array(list(weights.values()))
        probs = probs / probs.sum()
        return self.np_rng.choice(items, p=probs)
    
    def _select_vehicle_class(self, distribution: Dict[VehicleClass, float]) -> VehicleClass:
        """Select vehicle class based on distribution"""
        classes = list(distribution.keys())
        probs = np.array(list(distribution.values()))
        probs = probs / probs.sum()
        idx = self.np_rng.choice(len(classes), p=probs)
        return classes[idx]
    
    def generate_vehicles(self, time_step: int, dt: int = 1) -> List[Vehicle]:
        """Generate vehicles for the current time step"""
        profile = self.get_active_profile(time_step)
        if profile is None:
            return []
        
        spawn_rate = profile.vehicles_per_minute / 60.0 * dt
        self.spawn_accumulator += spawn_rate
        
        vehicles = []
        while self.spawn_accumulator >= 1.0:
            self.spawn_accumulator -= 1.0
            
            entry_node = self._select_weighted(profile.entry_node_weights)
            exit_node = self._select_weighted(profile.exit_node_weights)
            
            while exit_node == entry_node and len(self.network.exit_nodes) > 1:
                exit_node = self._select_weighted(profile.exit_node_weights)
            
            route = self.network.get_shortest_path(entry_node, exit_node)
            if not route:
                continue
            
            vehicle_class = self._select_vehicle_class(profile.vehicle_class_distribution)
            
            self.vehicle_counter += 1
            vehicle = Vehicle(
                id=f"v_{self.vehicle_counter}",
                vehicle_class=vehicle_class,
                route=route,
                spawn_time=time_step
            )
            vehicles.append(vehicle)
        
        return vehicles
    
    def reset(self) -> None:
        """Reset generator state"""
        self.rng = random.Random(self.seed)
        self.np_rng = np.random.default_rng(self.seed)
        self.vehicle_counter = 0
        self.spawn_accumulator = 0.0
    
    def set_seed(self, seed: int) -> None:
        """Set new random seed"""
        self.seed = seed
        self.reset()


def create_default_profiles(duration_seconds: int) -> List[DemandProfile]:
    """Create default peak/off-peak demand profiles"""
    profiles = []
    
    if duration_seconds <= 3600:
        peak_start = int(duration_seconds * 0.2)
        peak_end = int(duration_seconds * 0.6)
        
        profiles.append(DemandProfile(
            start_time=0,
            end_time=peak_start,
            vehicles_per_minute=20
        ))
        
        profiles.append(DemandProfile(
            start_time=peak_start,
            end_time=peak_end,
            vehicles_per_minute=60
        ))
        
        profiles.append(DemandProfile(
            start_time=peak_end,
            end_time=duration_seconds,
            vehicles_per_minute=25
        ))
    else:
        hour = 3600
        for h in range(duration_seconds // hour):
            start = h * hour
            end = min((h + 1) * hour, duration_seconds)
            
            if h in [7, 8, 17, 18]:
                rate = 60
            elif h in [6, 9, 16, 19]:
                rate = 40
            elif h in [0, 1, 2, 3, 4, 5, 22, 23]:
                rate = 10
            else:
                rate = 25
            
            profiles.append(DemandProfile(
                start_time=start,
                end_time=end,
                vehicles_per_minute=rate
            ))
    
    return profiles
