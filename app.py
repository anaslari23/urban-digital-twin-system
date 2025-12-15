"""
Urban Transport Digital Twin - Main Application
A decision support system for simulating traffic policy and infrastructure changes.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List, Optional

from models.city_model import CityNetwork, Node, Edge, VehicleClass
from simulation.simulation_engine import SimulationEngine, SimulationConfig
from simulation.metrics_collector import compare_metrics
from policy.intervention_engine import InterventionEngine, InterventionType
from ai.explanation_engine import AIExplanationEngine

st.set_page_config(
    page_title="Urban Transport Digital Twin",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables"""
    if 'network' not in st.session_state:
        st.session_state.network = load_network()
    if 'baseline_results' not in st.session_state:
        st.session_state.baseline_results = None
    if 'intervention_results' not in st.session_state:
        st.session_state.intervention_results = None
    if 'comparison' not in st.session_state:
        st.session_state.comparison = None
    if 'ai_explanation' not in st.session_state:
        st.session_state.ai_explanation = None
    if 'interventions' not in st.session_state:
        st.session_state.interventions = []
    if 'simulation_states' not in st.session_state:
        st.session_state.simulation_states = []
    if 'current_playback_step' not in st.session_state:
        st.session_state.current_playback_step = 0


def load_network() -> CityNetwork:
    """Load the sample city network"""
    network_path = "data/sample_network.json"
    if os.path.exists(network_path):
        return CityNetwork.load_from_json(network_path)
    else:
        return create_default_network()


def create_default_network() -> CityNetwork:
    """Create a default network if file doesn't exist"""
    network = CityNetwork()
    
    for i in range(5):
        for j in range(5):
            node_id = f"N{i*5+j+1}"
            is_entry = (i == 0 or j == 0)
            is_exit = (i == 4 or j == 4)
            node = Node(
                id=node_id,
                x=j * 150,
                y=i * 150,
                is_entry_node=is_entry and not is_exit,
                is_exit_node=is_exit and not is_entry
            )
            for direction in ["north", "south", "east", "west"]:
                node.signal_phases[direction] = node.signal_phases.get(direction, "red")
            network.add_node(node)
    
    edge_id = 1
    for i in range(5):
        for j in range(4):
            from_id = f"N{i*5+j+1}"
            to_id = f"N{i*5+j+2}"
            edge = Edge(
                id=f"E{edge_id}",
                from_node=from_id,
                to_node=to_id,
                length=150,
                lane_count=2,
                speed_limit=13.9,
                capacity=20
            )
            network.add_edge(edge)
            edge_id += 1
    
    for i in range(4):
        for j in range(5):
            from_id = f"N{i*5+j+1}"
            to_id = f"N{(i+1)*5+j+1}"
            edge = Edge(
                id=f"E{edge_id}",
                from_node=from_id,
                to_node=to_id,
                length=150,
                lane_count=2,
                speed_limit=13.9,
                capacity=20
            )
            network.add_edge(edge)
            edge_id += 1
    
    return network


def create_network_visualization(network: CityNetwork, edge_loads: Optional[Dict] = None, 
                                  bottlenecks: Optional[List] = None) -> go.Figure:
    """Create interactive network visualization using Plotly"""
    
    fig = go.Figure()
    
    positions = network.get_node_positions()
    
    for edge_id, edge in network.edges.items():
        if edge.from_node in positions and edge.to_node in positions:
            x0, y0 = positions[edge.from_node]
            x1, y1 = positions[edge.to_node]
            
            if edge_loads and edge_id in edge_loads:
                load = edge_loads[edge_id]
                load_ratio = load / max(1, edge.total_capacity)
                if load_ratio < 0.5:
                    color = 'green'
                elif load_ratio < 0.8:
                    color = 'orange'
                else:
                    color = 'red'
                width = 2 + load_ratio * 4
            else:
                color = 'gray'
                width = 2
            
            if bottlenecks and edge_id in bottlenecks:
                color = 'darkred'
                width = 5
            
            if edge.has_bus_lane:
                color = 'blue'
            
            fig.add_trace(go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode='lines',
                line=dict(color=color, width=width),
                hoverinfo='text',
                text=f"Edge: {edge_id}<br>Length: {edge.length}m<br>Lanes: {edge.lane_count}<br>Speed: {edge.speed_limit:.1f} m/s",
                showlegend=False
            ))
    
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []
    
    for node_id, node in network.nodes.items():
        x, y = positions[node_id]
        node_x.append(x)
        node_y.append(y)
        
        if node.is_entry_node:
            node_colors.append('green')
            node_sizes.append(20)
        elif node.is_exit_node:
            node_colors.append('red')
            node_sizes.append(20)
        else:
            node_colors.append('lightblue')
            node_sizes.append(15)
        
        node_text.append(f"Node: {node_id}<br>Entry: {node.is_entry_node}<br>Exit: {node.is_exit_node}")
    
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=node_sizes, color=node_colors, line=dict(width=2, color='black')),
        text=[n for n in network.nodes.keys()],
        textposition="top center",
        hoverinfo='text',
        hovertext=node_text,
        showlegend=False
    ))
    
    fig.update_layout(
        title="City Transport Network",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        hovermode='closest',
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        plot_bgcolor='white'
    )
    
    return fig


def create_metrics_charts(results: Dict, title_prefix: str = "") -> Dict[str, go.Figure]:
    """Create metric visualization charts"""
    charts = {}
    
    time_series = results.get('time_series', {})
    
    if time_series.get('time'):
        fig_vehicles = go.Figure()
        fig_vehicles.add_trace(go.Scatter(
            x=time_series['time'],
            y=time_series['active_vehicles'],
            mode='lines',
            name='Active Vehicles',
            line=dict(color='blue')
        ))
        fig_vehicles.add_trace(go.Scatter(
            x=time_series['time'],
            y=time_series['completed_vehicles'],
            mode='lines',
            name='Completed Vehicles',
            line=dict(color='green')
        ))
        fig_vehicles.update_layout(
            title=f"{title_prefix}Vehicle Count Over Time",
            xaxis_title="Time (seconds)",
            yaxis_title="Vehicles",
            height=300
        )
        charts['vehicles'] = fig_vehicles
        
        fig_congestion = go.Figure()
        fig_congestion.add_trace(go.Scatter(
            x=time_series['time'],
            y=time_series['congestion'],
            mode='lines',
            name='Average Congestion',
            fill='tozeroy',
            line=dict(color='orange')
        ))
        fig_congestion.update_layout(
            title=f"{title_prefix}Network Congestion Over Time",
            xaxis_title="Time (seconds)",
            yaxis_title="Congestion Factor",
            height=300
        )
        charts['congestion'] = fig_congestion
        
        fig_queue = go.Figure()
        fig_queue.add_trace(go.Scatter(
            x=time_series['time'],
            y=time_series['queue_length'],
            mode='lines',
            name='Total Queue Length',
            fill='tozeroy',
            line=dict(color='red')
        ))
        fig_queue.update_layout(
            title=f"{title_prefix}Queue Length Over Time",
            xaxis_title="Time (seconds)",
            yaxis_title="Total Vehicles in Queues",
            height=300
        )
        charts['queue'] = fig_queue
    
    return charts


def create_comparison_chart(comparison: Dict) -> go.Figure:
    """Create comparison bar chart between baseline and intervention"""
    
    metrics = []
    baseline_values = []
    intervention_values = []
    
    display_names = {
        'average_travel_time': 'Avg Travel Time (s)',
        'average_delay': 'Avg Delay (s)',
        'max_queue_length': 'Max Queue Length',
        'throughput': 'Throughput (veh/hr)'
    }
    
    for key, name in display_names.items():
        if key in comparison:
            metrics.append(name)
            baseline_values.append(comparison[key]['baseline'])
            intervention_values.append(comparison[key]['intervention'])
    
    fig = go.Figure(data=[
        go.Bar(name='Baseline', x=metrics, y=baseline_values, marker_color='steelblue'),
        go.Bar(name='Intervention', x=metrics, y=intervention_values, marker_color='darkorange')
    ])
    
    fig.update_layout(
        title='Baseline vs Intervention Comparison',
        barmode='group',
        height=400,
        yaxis_title='Value'
    )
    
    return fig


def run_simulation(network: CityNetwork, config: SimulationConfig, 
                   interventions: List = None, progress_bar=None) -> Dict:
    """Run traffic simulation with optional interventions"""
    
    if interventions:
        intervention_engine = InterventionEngine(network)
        for intervention in interventions:
            intervention_engine.add_intervention(intervention)
        modified_network = intervention_engine.apply_interventions(network)
        engine = SimulationEngine(modified_network, config)
    else:
        engine = SimulationEngine(network, config)
    
    def update_progress(step, total):
        if progress_bar:
            progress_bar.progress(step / total)
    
    results = engine.run(progress_callback=update_progress)
    
    st.session_state.simulation_states = engine.states
    
    return results


def main():
    """Main application entry point"""
    
    init_session_state()
    
    st.markdown('<p class="main-header">Urban Transport Digital Twin</p>', unsafe_allow_html=True)
    st.markdown("*Simulate policy and infrastructure changes to observe system-level impacts*")
    
    with st.sidebar:
        st.header("Simulation Controls")
        
        duration_minutes = st.slider("Simulation Duration (minutes)", 5, 60, 15)
        duration_seconds = duration_minutes * 60
        
        demand_multiplier = st.slider("Demand Multiplier", 0.5, 2.0, 1.0, 0.1)
        
        seed = st.number_input("Random Seed", min_value=1, max_value=9999, value=42)
        
        st.divider()
        st.header("Policy Interventions")
        
        edge_options = list(st.session_state.network.edges.keys())
        node_options = list(st.session_state.network.nodes.keys())
        
        intervention_type = st.selectbox(
            "Intervention Type",
            ["None", "Add Bus Lane", "Remove Bus Lane", "Modify Signal Timing", 
             "Restrict Vehicle Class", "Change Speed Limit"]
        )
        
        if intervention_type == "Add Bus Lane":
            target_edge = st.selectbox("Select Edge", edge_options, key="bus_lane_edge")
            if st.button("Add Bus Lane Intervention"):
                from policy.intervention_engine import Intervention
                intervention = Intervention(
                    id=f"bus_lane_{target_edge}",
                    intervention_type=InterventionType.BUS_LANE_ADD,
                    target_id=target_edge,
                    description=f"Add bus lane on edge {target_edge}"
                )
                st.session_state.interventions.append(intervention)
                st.success(f"Added bus lane intervention on {target_edge}")
        
        elif intervention_type == "Remove Bus Lane":
            target_edge = st.selectbox("Select Edge", edge_options, key="remove_bus_lane_edge")
            if st.button("Remove Bus Lane Intervention"):
                from policy.intervention_engine import Intervention
                intervention = Intervention(
                    id=f"remove_bus_lane_{target_edge}",
                    intervention_type=InterventionType.BUS_LANE_REMOVE,
                    target_id=target_edge,
                    description=f"Remove bus lane on edge {target_edge}"
                )
                st.session_state.interventions.append(intervention)
                st.success(f"Added remove bus lane intervention on {target_edge}")
        
        elif intervention_type == "Modify Signal Timing":
            target_node = st.selectbox("Select Intersection", node_options, key="signal_node")
            green_time = st.slider("Green Phase (seconds)", 10, 60, 30)
            red_time = st.slider("Red Phase (seconds)", 10, 60, 25)
            if st.button("Add Signal Timing Intervention"):
                from policy.intervention_engine import Intervention
                intervention = Intervention(
                    id=f"signal_{target_node}",
                    intervention_type=InterventionType.SIGNAL_TIMING,
                    target_id=target_node,
                    parameters={"green": green_time, "yellow": 5, "red": red_time},
                    description=f"Change signal timing at {target_node}: Green={green_time}s, Red={red_time}s"
                )
                st.session_state.interventions.append(intervention)
                st.success(f"Added signal timing intervention at {target_node}")
        
        elif intervention_type == "Restrict Vehicle Class":
            target_edge = st.selectbox("Select Edge", edge_options, key="restrict_edge")
            restricted = st.multiselect("Restrict Vehicle Types", ["car", "bus", "restricted"])
            if st.button("Add Restriction Intervention") and restricted:
                from policy.intervention_engine import Intervention
                intervention = Intervention(
                    id=f"restrict_{target_edge}",
                    intervention_type=InterventionType.VEHICLE_RESTRICTION,
                    target_id=target_edge,
                    parameters={"restricted_classes": restricted},
                    description=f"Restrict {', '.join(restricted)} on edge {target_edge}"
                )
                st.session_state.interventions.append(intervention)
                st.success(f"Added restriction intervention on {target_edge}")
        
        elif intervention_type == "Change Speed Limit":
            target_edge = st.selectbox("Select Edge", edge_options, key="speed_edge")
            speed_kmh = st.slider("Speed Limit (km/h)", 20, 80, 50)
            speed_ms = speed_kmh / 3.6
            if st.button("Add Speed Limit Intervention"):
                from policy.intervention_engine import Intervention
                intervention = Intervention(
                    id=f"speed_{target_edge}",
                    intervention_type=InterventionType.SPEED_LIMIT_CHANGE,
                    target_id=target_edge,
                    parameters={"speed_limit": speed_ms},
                    description=f"Change speed limit on {target_edge} to {speed_kmh} km/h"
                )
                st.session_state.interventions.append(intervention)
                st.success(f"Added speed limit intervention on {target_edge}")
        
        if st.session_state.interventions:
            st.divider()
            st.subheader("Active Interventions")
            for i, intervention in enumerate(st.session_state.interventions):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{i+1}. {intervention.description}")
                with col2:
                    if st.button("X", key=f"remove_{i}"):
                        st.session_state.interventions.pop(i)
                        st.rerun()
            
            if st.button("Clear All Interventions"):
                st.session_state.interventions = []
                st.rerun()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Network Map", "Run Simulation", "Results & Comparison", "AI Explanation"])
    
    with tab1:
        st.subheader("City Transport Network")
        
        edge_loads = None
        bottlenecks = None
        if st.session_state.baseline_results:
            bottlenecks = list(st.session_state.baseline_results.get('bottleneck_frequency', {}).keys())
        
        fig = create_network_visualization(
            st.session_state.network,
            edge_loads=edge_loads,
            bottlenecks=bottlenecks
        )
        st.plotly_chart(fig, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Nodes", len(st.session_state.network.nodes))
        with col2:
            st.metric("Total Edges", len(st.session_state.network.edges))
        with col3:
            entry_count = len(st.session_state.network.entry_nodes)
            exit_count = len(st.session_state.network.exit_nodes)
            st.metric("Entry/Exit Nodes", f"{entry_count}/{exit_count}")
        
        st.markdown("""
        **Legend:**
        - Green nodes: Entry points
        - Red nodes: Exit points
        - Blue nodes: Internal intersections
        - Edge colors indicate traffic load (green=low, orange=medium, red=high)
        """)
    
    with tab2:
        st.subheader("Run Traffic Simulation")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Baseline Simulation")
            st.write("Run simulation without any interventions to establish baseline metrics.")
            
            if st.button("Run Baseline Simulation", key="run_baseline"):
                config = SimulationConfig(
                    duration_seconds=duration_seconds,
                    time_step_seconds=1,
                    seed=seed,
                    demand_multiplier=demand_multiplier
                )
                
                progress_bar = st.progress(0)
                st.info("Running baseline simulation...")
                
                results = run_simulation(
                    st.session_state.network, 
                    config,
                    progress_bar=progress_bar
                )
                
                st.session_state.baseline_results = results
                progress_bar.progress(100)
                st.success("Baseline simulation complete!")
            
            if st.session_state.baseline_results:
                st.markdown("**Baseline Results:**")
                results = st.session_state.baseline_results
                st.metric("Avg Travel Time", f"{results.get('average_travel_time', 0):.1f}s")
                st.metric("Avg Delay", f"{results.get('average_delay', 0):.1f}s")
                st.metric("Throughput", f"{results.get('throughput', 0):.0f} veh/hr")
        
        with col2:
            st.markdown("### Intervention Simulation")
            
            if st.session_state.interventions:
                st.write(f"**{len(st.session_state.interventions)} intervention(s) configured:**")
                for intervention in st.session_state.interventions:
                    st.write(f"- {intervention.description}")
            else:
                st.warning("No interventions configured. Add interventions from the sidebar.")
            
            run_button_disabled = not st.session_state.interventions or not st.session_state.baseline_results
            
            if st.button("Run Intervention Simulation", key="run_intervention", disabled=run_button_disabled):
                config = SimulationConfig(
                    duration_seconds=duration_seconds,
                    time_step_seconds=1,
                    seed=seed,
                    demand_multiplier=demand_multiplier
                )
                
                progress_bar = st.progress(0)
                st.info("Running intervention simulation...")
                
                results = run_simulation(
                    st.session_state.network,
                    config,
                    interventions=st.session_state.interventions,
                    progress_bar=progress_bar
                )
                
                st.session_state.intervention_results = results
                
                st.session_state.comparison = compare_metrics(
                    st.session_state.baseline_results,
                    st.session_state.intervention_results
                )
                
                progress_bar.progress(100)
                st.success("Intervention simulation complete!")
            
            if st.session_state.intervention_results:
                st.markdown("**Intervention Results:**")
                results = st.session_state.intervention_results
                st.metric("Avg Travel Time", f"{results.get('average_travel_time', 0):.1f}s")
                st.metric("Avg Delay", f"{results.get('average_delay', 0):.1f}s")
                st.metric("Throughput", f"{results.get('throughput', 0):.0f} veh/hr")
    
    with tab3:
        st.subheader("Results & Comparison")
        
        if st.session_state.baseline_results:
            st.markdown("### Baseline Metrics Over Time")
            charts = create_metrics_charts(st.session_state.baseline_results, "Baseline: ")
            
            col1, col2 = st.columns(2)
            with col1:
                if 'vehicles' in charts:
                    st.plotly_chart(charts['vehicles'], use_container_width=True)
            with col2:
                if 'congestion' in charts:
                    st.plotly_chart(charts['congestion'], use_container_width=True)
            
            if 'queue' in charts:
                st.plotly_chart(charts['queue'], use_container_width=True)
        
        if st.session_state.comparison:
            st.markdown("### Baseline vs Intervention Comparison")
            
            comparison_fig = create_comparison_chart(st.session_state.comparison)
            st.plotly_chart(comparison_fig, use_container_width=True)
            
            st.markdown("### Detailed Changes")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if 'average_travel_time' in st.session_state.comparison:
                    data = st.session_state.comparison['average_travel_time']
                    delta = f"{data['percent_change']:+.1f}%"
                    st.metric("Avg Travel Time Change", f"{data['absolute_change']:+.1f}s", delta)
            
            with col2:
                if 'average_delay' in st.session_state.comparison:
                    data = st.session_state.comparison['average_delay']
                    delta = f"{data['percent_change']:+.1f}%"
                    st.metric("Avg Delay Change", f"{data['absolute_change']:+.1f}s", delta)
            
            with col3:
                if 'throughput' in st.session_state.comparison:
                    data = st.session_state.comparison['throughput']
                    delta = f"{data['percent_change']:+.1f}%"
                    st.metric("Throughput Change", f"{data['absolute_change']:+.0f} veh/hr", delta)
            
            st.markdown("### Bottleneck Analysis")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                new_bottlenecks = st.session_state.comparison.get('new_bottlenecks', [])
                st.markdown(f"**New Bottlenecks:** {len(new_bottlenecks)}")
                for b in new_bottlenecks[:5]:
                    st.write(f"- {b}")
            
            with col2:
                resolved = st.session_state.comparison.get('resolved_bottlenecks', [])
                st.markdown(f"**Resolved Bottlenecks:** {len(resolved)}")
                for b in resolved[:5]:
                    st.write(f"- {b}")
            
            with col3:
                persistent = st.session_state.comparison.get('persistent_bottlenecks', [])
                st.markdown(f"**Persistent Bottlenecks:** {len(persistent)}")
                for b in persistent[:5]:
                    st.write(f"- {b}")
        
        if not st.session_state.baseline_results:
            st.info("Run a baseline simulation first to see results.")
    
    with tab4:
        st.subheader("AI-Powered Analysis")
        
        ai_engine = AIExplanationEngine()
        
        if ai_engine.is_available():
            st.success("AI Explanation Engine connected")
        else:
            st.warning("Azure OpenAI not configured. Using rule-based analysis. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables for AI-powered explanations.")
        
        if st.session_state.comparison and st.session_state.baseline_results and st.session_state.intervention_results:
            
            if st.button("Generate AI Explanation"):
                with st.spinner("Analyzing simulation results..."):
                    interventions_dict = [i.to_dict() for i in st.session_state.interventions]
                    
                    explanation = ai_engine.generate_explanation(
                        st.session_state.baseline_results,
                        st.session_state.intervention_results,
                        st.session_state.comparison,
                        interventions_dict
                    )
                    
                    st.session_state.ai_explanation = explanation
            
            if st.session_state.ai_explanation:
                explanation = st.session_state.ai_explanation
                
                st.markdown("### Analysis Results")
                
                if explanation.get('success'):
                    st.markdown("#### Explanation")
                    st.markdown(explanation.get('explanation', 'No explanation available'))
                    
                    if explanation.get('risk_flags'):
                        st.markdown("#### Risk Flags")
                        for flag in explanation['risk_flags']:
                            st.warning(flag)
                    
                    if explanation.get('key_findings'):
                        st.markdown("#### Key Findings")
                        for finding in explanation['key_findings']:
                            st.info(finding)
                    
                    st.caption(f"Analysis model: {explanation.get('ai_model', 'unknown')}")
                else:
                    st.error(f"AI analysis failed: {explanation.get('error', 'Unknown error')}")
                    if explanation.get('fallback'):
                        st.markdown("### Fallback Analysis")
                        st.markdown(explanation['fallback'].get('explanation', ''))
        else:
            st.info("Run both baseline and intervention simulations to enable AI analysis.")
        
        st.divider()
        st.markdown("""
        ### About the AI Explanation Engine
        
        The AI engine provides:
        - **Causal Analysis**: Explains WHY changes occurred, not just what changed
        - **Second-Order Effects**: Identifies cascading impacts of interventions
        - **Risk Flags**: Highlights potential concerns for decision-makers
        - **Pattern Detection**: Identifies congestion trends and anomalies
        
        **Note**: The AI does NOT:
        - Make deployment recommendations
        - Override simulation data
        - Control traffic directly
        """)


if __name__ == "__main__":
    main()
