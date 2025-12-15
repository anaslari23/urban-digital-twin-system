"""
Metrics Collector for Urban Transport Digital Twin
Tracks simulation metrics and exports structured data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json
import statistics


@dataclass
class StepMetrics:
    """Metrics for a single simulation step"""
    time_step: int
    active_vehicles: int
    completed_vehicles: int
    total_queue_length: int
    average_congestion: float
    bottleneck_edges: List[str]
    edge_loads: Dict[str, int]


@dataclass
class VehicleMetrics:
    """Metrics for a completed vehicle"""
    vehicle_id: str
    travel_time: float
    accumulated_delay: float


@dataclass
class SimulationMetrics:
    """Complete simulation metrics"""
    total_duration: int
    total_vehicles_spawned: int
    total_vehicles_completed: int
    average_travel_time: float
    average_delay: float
    max_queue_length: int
    max_congestion: float
    bottleneck_frequency: Dict[str, int]
    throughput: float
    time_series: Dict[str, List]


class MetricsCollector:
    """Collects and aggregates simulation metrics"""
    
    def __init__(self):
        self.step_metrics: List[StepMetrics] = []
        self.vehicle_metrics: List[VehicleMetrics] = []
        self.bottleneck_counts: Dict[str, int] = {}
    
    def record_step(
        self,
        time_step: int,
        active_vehicles: int,
        completed_vehicles: int,
        total_queue_length: int,
        average_congestion: float,
        bottleneck_edges: List[str],
        edge_loads: Dict[str, int]
    ) -> None:
        """Record metrics for a simulation step"""
        metrics = StepMetrics(
            time_step=time_step,
            active_vehicles=active_vehicles,
            completed_vehicles=completed_vehicles,
            total_queue_length=total_queue_length,
            average_congestion=average_congestion,
            bottleneck_edges=bottleneck_edges,
            edge_loads=edge_loads
        )
        self.step_metrics.append(metrics)
        
        for edge_id in bottleneck_edges:
            self.bottleneck_counts[edge_id] = self.bottleneck_counts.get(edge_id, 0) + 1
    
    def record_vehicle_completion(
        self,
        vehicle_id: str,
        travel_time: float,
        accumulated_delay: float
    ) -> None:
        """Record metrics for a completed vehicle"""
        metrics = VehicleMetrics(
            vehicle_id=vehicle_id,
            travel_time=travel_time,
            accumulated_delay=accumulated_delay
        )
        self.vehicle_metrics.append(metrics)
    
    def get_summary(self) -> Dict:
        """Get summary of all collected metrics"""
        if not self.step_metrics:
            return {}
        
        travel_times = [v.travel_time for v in self.vehicle_metrics]
        delays = [v.accumulated_delay for v in self.vehicle_metrics]
        
        avg_travel_time = statistics.mean(travel_times) if travel_times else 0
        avg_delay = statistics.mean(delays) if delays else 0
        
        max_queue = max(m.total_queue_length for m in self.step_metrics)
        max_congestion = max(m.average_congestion for m in self.step_metrics)
        
        duration = self.step_metrics[-1].time_step if self.step_metrics else 0
        throughput = len(self.vehicle_metrics) / (duration / 3600) if duration > 0 else 0
        
        time_series = {
            "time": [m.time_step for m in self.step_metrics],
            "active_vehicles": [m.active_vehicles for m in self.step_metrics],
            "completed_vehicles": [m.completed_vehicles for m in self.step_metrics],
            "queue_length": [m.total_queue_length for m in self.step_metrics],
            "congestion": [m.average_congestion for m in self.step_metrics]
        }
        
        total_spawned = max(m.active_vehicles + m.completed_vehicles for m in self.step_metrics) if self.step_metrics else 0
        
        return {
            "total_duration": duration,
            "total_vehicles_spawned": total_spawned,
            "total_vehicles_completed": len(self.vehicle_metrics),
            "average_travel_time": avg_travel_time,
            "average_delay": avg_delay,
            "max_queue_length": max_queue,
            "max_congestion": max_congestion,
            "bottleneck_frequency": dict(sorted(
                self.bottleneck_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]),
            "throughput": throughput,
            "time_series": time_series
        }
    
    def get_edge_statistics(self) -> Dict[str, Dict]:
        """Get per-edge statistics"""
        edge_stats = {}
        
        for metrics in self.step_metrics:
            for edge_id, load in metrics.edge_loads.items():
                if edge_id not in edge_stats:
                    edge_stats[edge_id] = {"loads": [], "bottleneck_count": 0}
                edge_stats[edge_id]["loads"].append(load)
                if edge_id in metrics.bottleneck_edges:
                    edge_stats[edge_id]["bottleneck_count"] += 1
        
        result = {}
        for edge_id, stats in edge_stats.items():
            loads = stats["loads"]
            result[edge_id] = {
                "avg_load": statistics.mean(loads) if loads else 0,
                "max_load": max(loads) if loads else 0,
                "bottleneck_frequency": stats["bottleneck_count"] / len(self.step_metrics) if self.step_metrics else 0
            }
        
        return result
    
    def export_json(self, filepath: str) -> None:
        """Export metrics to JSON file"""
        data = {
            "summary": self.get_summary(),
            "edge_statistics": self.get_edge_statistics(),
            "step_count": len(self.step_metrics),
            "vehicle_count": len(self.vehicle_metrics)
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def reset(self) -> None:
        """Reset all collected metrics"""
        self.step_metrics = []
        self.vehicle_metrics = []
        self.bottleneck_counts = {}


def compare_metrics(baseline: Dict, intervention: Dict) -> Dict:
    """Compare baseline and intervention metrics"""
    comparison = {}
    
    keys_to_compare = [
        "average_travel_time",
        "average_delay", 
        "max_queue_length",
        "max_congestion",
        "throughput",
        "total_vehicles_completed"
    ]
    
    for key in keys_to_compare:
        baseline_val = baseline.get(key, 0)
        intervention_val = intervention.get(key, 0)
        
        if baseline_val != 0:
            change_percent = ((intervention_val - baseline_val) / baseline_val) * 100
        else:
            change_percent = 0 if intervention_val == 0 else 100
        
        comparison[key] = {
            "baseline": baseline_val,
            "intervention": intervention_val,
            "absolute_change": intervention_val - baseline_val,
            "percent_change": change_percent
        }
    
    baseline_bottlenecks = set(baseline.get("bottleneck_frequency", {}).keys())
    intervention_bottlenecks = set(intervention.get("bottleneck_frequency", {}).keys())
    
    comparison["new_bottlenecks"] = list(intervention_bottlenecks - baseline_bottlenecks)
    comparison["resolved_bottlenecks"] = list(baseline_bottlenecks - intervention_bottlenecks)
    comparison["persistent_bottlenecks"] = list(baseline_bottlenecks & intervention_bottlenecks)
    
    return comparison
