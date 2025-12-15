"""
AI Explanation Engine for Urban Transport Digital Twin
Integrates with Azure OpenAI for causal explanation generation.
"""

import os
import json
from typing import Dict, List, Optional
from openai import AzureOpenAI


class AIExplanationEngine:
    """AI-powered explanation engine using Azure OpenAI"""
    
    def __init__(self):
        self.client = None
        self.model = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize Azure OpenAI client from environment variables"""
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        azure_key = os.environ.get("AZURE_OPENAI_API_KEY")
        azure_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        
        if azure_endpoint and azure_key:
            self.client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_key,
                api_version="2024-02-01"
            )
            self.model = azure_deployment
        else:
            openai_key = os.environ.get("OPENAI_API_KEY")
            if openai_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=openai_key)
                self.model = "gpt-4o"
    
    def is_available(self) -> bool:
        """Check if AI client is properly configured"""
        return self.client is not None
    
    def generate_explanation(
        self,
        baseline_metrics: Dict,
        intervention_metrics: Dict,
        comparison: Dict,
        interventions: List[Dict]
    ) -> Dict:
        """Generate AI explanation comparing baseline vs intervention results"""
        
        if not self.is_available():
            return self._generate_fallback_explanation(comparison, interventions)
        
        prompt = self._build_prompt(baseline_metrics, intervention_metrics, comparison, interventions)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an urban transport analyst AI. Your role is to:
1. Analyze traffic simulation results comparing baseline and intervention scenarios
2. Identify causal relationships between policy changes and observed effects
3. Detect second-order effects and unintended consequences
4. Generate clear, actionable explanations for decision-makers
5. Flag potential risks or concerns

Important constraints:
- You must NOT recommend deployment decisions
- You must NOT override or modify simulation data
- You must base all analysis strictly on the provided metrics
- Focus on explaining WHY changes occurred, not just WHAT changed

Provide your analysis in a structured format with clear sections."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            explanation_text = response.choices[0].message.content
            
            return {
                "success": True,
                "explanation": explanation_text,
                "key_findings": self._extract_key_findings(explanation_text),
                "risk_flags": self._extract_risk_flags(comparison),
                "ai_model": self.model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fallback": self._generate_fallback_explanation(comparison, interventions)
            }
    
    def _build_prompt(
        self,
        baseline: Dict,
        intervention: Dict,
        comparison: Dict,
        interventions: List[Dict]
    ) -> str:
        """Build the analysis prompt for the AI"""
        
        interventions_desc = "\n".join([
            f"- {i.get('description', i.get('type', 'Unknown'))}" 
            for i in interventions
        ])
        
        prompt = f"""Analyze the following traffic simulation results:

## Applied Interventions
{interventions_desc}

## Baseline Metrics
- Average Travel Time: {baseline.get('average_travel_time', 0):.1f} seconds
- Average Delay: {baseline.get('average_delay', 0):.1f} seconds
- Max Queue Length: {baseline.get('max_queue_length', 0)} vehicles
- Max Congestion Factor: {baseline.get('max_congestion', 0):.2f}
- Throughput: {baseline.get('throughput', 0):.0f} vehicles/hour
- Vehicles Completed: {baseline.get('total_vehicles_completed', 0)}

## Intervention Metrics
- Average Travel Time: {intervention.get('average_travel_time', 0):.1f} seconds
- Average Delay: {intervention.get('average_delay', 0):.1f} seconds
- Max Queue Length: {intervention.get('max_queue_length', 0)} vehicles
- Max Congestion Factor: {intervention.get('max_congestion', 0):.2f}
- Throughput: {intervention.get('throughput', 0):.0f} vehicles/hour
- Vehicles Completed: {intervention.get('total_vehicles_completed', 0)}

## Key Changes
"""
        
        for key, data in comparison.items():
            if isinstance(data, dict) and 'percent_change' in data:
                prompt += f"- {key}: {data['percent_change']:+.1f}% change\n"
        
        if comparison.get('new_bottlenecks'):
            prompt += f"\nNew bottlenecks emerged: {', '.join(comparison['new_bottlenecks'])}\n"
        if comparison.get('resolved_bottlenecks'):
            prompt += f"Bottlenecks resolved: {', '.join(comparison['resolved_bottlenecks'])}\n"
        
        prompt += """

Please provide:
1. A summary of the primary effects of the intervention
2. Analysis of any second-order or cascading effects
3. Identification of any unintended consequences
4. Explanation of the causal mechanisms behind the observed changes
5. Risk flags or concerns for decision-makers (if any)
"""
        
        return prompt
    
    def _extract_key_findings(self, explanation: str) -> List[str]:
        """Extract key findings from the AI explanation"""
        findings = []
        
        lines = explanation.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('• ') or line.startswith('* '):
                if len(line) > 10:
                    findings.append(line[2:])
        
        return findings[:5]
    
    def _extract_risk_flags(self, comparison: Dict) -> List[str]:
        """Extract risk flags from the comparison data"""
        flags = []
        
        avg_delay_change = comparison.get('average_delay', {}).get('percent_change', 0)
        if avg_delay_change > 20:
            flags.append(f"Significant delay increase ({avg_delay_change:.1f}%)")
        
        max_queue_change = comparison.get('max_queue_length', {}).get('percent_change', 0)
        if max_queue_change > 30:
            flags.append(f"Queue lengths increased substantially ({max_queue_change:.1f}%)")
        
        throughput_change = comparison.get('throughput', {}).get('percent_change', 0)
        if throughput_change < -10:
            flags.append(f"Throughput decreased ({throughput_change:.1f}%)")
        
        new_bottlenecks = comparison.get('new_bottlenecks', [])
        if len(new_bottlenecks) > 2:
            flags.append(f"Multiple new bottlenecks emerged ({len(new_bottlenecks)} locations)")
        
        return flags
    
    def _generate_fallback_explanation(self, comparison: Dict, interventions: List[Dict]) -> Dict:
        """Generate a rule-based explanation when AI is unavailable"""
        
        explanation_parts = []
        
        interventions_desc = ", ".join([
            i.get('description', i.get('type', 'policy change')) 
            for i in interventions
        ])
        explanation_parts.append(f"Analysis of applied interventions: {interventions_desc}")
        
        effects = []
        for key, data in comparison.items():
            if isinstance(data, dict) and 'percent_change' in data:
                change = data['percent_change']
                if abs(change) > 5:
                    direction = "increased" if change > 0 else "decreased"
                    effects.append(f"{key.replace('_', ' ').title()} {direction} by {abs(change):.1f}%")
        
        if effects:
            explanation_parts.append("\nPrimary Effects:\n" + "\n".join(f"- {e}" for e in effects))
        
        new_bottlenecks = comparison.get('new_bottlenecks', [])
        resolved_bottlenecks = comparison.get('resolved_bottlenecks', [])
        
        if new_bottlenecks:
            explanation_parts.append(f"\nNew bottlenecks detected at: {', '.join(new_bottlenecks)}")
        if resolved_bottlenecks:
            explanation_parts.append(f"\nBottlenecks resolved at: {', '.join(resolved_bottlenecks)}")
        
        risk_flags = self._extract_risk_flags(comparison)
        if risk_flags:
            explanation_parts.append("\nRisk Flags:\n" + "\n".join(f"⚠️ {f}" for f in risk_flags))
        
        return {
            "success": True,
            "explanation": "\n".join(explanation_parts),
            "key_findings": effects[:5],
            "risk_flags": risk_flags,
            "ai_model": "rule-based-fallback"
        }
    
    def detect_patterns(self, time_series: Dict) -> Dict:
        """Detect patterns in time series data"""
        patterns = {
            "congestion_trend": "stable",
            "peak_detection": [],
            "anomalies": []
        }
        
        congestion = time_series.get('congestion', [])
        if len(congestion) > 10:
            first_half_avg = sum(congestion[:len(congestion)//2]) / (len(congestion)//2)
            second_half_avg = sum(congestion[len(congestion)//2:]) / (len(congestion)//2)
            
            if second_half_avg > first_half_avg * 1.2:
                patterns["congestion_trend"] = "increasing"
            elif second_half_avg < first_half_avg * 0.8:
                patterns["congestion_trend"] = "decreasing"
            
            threshold = sum(congestion) / len(congestion) * 1.5
            for i, c in enumerate(congestion):
                if c > threshold:
                    patterns["peak_detection"].append(time_series['time'][i])
        
        return patterns
