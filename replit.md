# Urban Transport Digital Twin

## Overview
A decision support system that simulates urban transport network policy and infrastructure changes to observe their system-level impacts BEFORE real-world deployment.

## Architecture

### Core Modules
- **models/city_model.py**: Graph-based city network with Node (intersections), Edge (roads), and Vehicle classes
- **simulation/demand_generator.py**: Vehicle spawning with peak/off-peak demand patterns
- **simulation/simulation_engine.py**: Discrete-event traffic simulation engine
- **simulation/metrics_collector.py**: Metrics tracking and comparison utilities
- **policy/intervention_engine.py**: Policy intervention management (bus lanes, signal timing, restrictions)
- **ai/explanation_engine.py**: Azure OpenAI integration for causal explanation generation

### Key Features
- 25-node, 63-edge transport network simulation
- Discrete time-step simulation (1-second resolution)
- Vehicle demand generation with peak/off-peak patterns
- Policy interventions: bus lanes, signal timing, vehicle restrictions, speed limits
- Congestion, queue spillback, and bottleneck detection
- Baseline vs intervention comparison
- AI-powered explanation of simulation results

### Data Files
- **data/sample_network.json**: Sample city network configuration

## Running the Application
```bash
streamlit run app.py --server.port 5000
```

## Environment Variables
For AI-powered explanations, set:
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API key
- `AZURE_OPENAI_DEPLOYMENT`: Model deployment name (default: gpt-4)

Or alternatively:
- `OPENAI_API_KEY`: Standard OpenAI API key

If no AI keys are configured, the system uses rule-based fallback analysis.

## Technical Notes
- Simulation uses seeded random number generation for reproducibility
- Traffic flow uses capacity-based congestion modeling
- Signal phases cycle through green/yellow/red timing
- Queue spillback propagates upstream when capacity is exceeded
