"""Cost Analyzer Agent — estimates infrastructure costs across cloud providers."""

from app.agents.base import BaseAgent
from app.config import get_settings

SYSTEM_PROMPT = """You are a Cloud Infrastructure Cost Specialist with deep knowledge of pricing for AWS, GCP, and Azure. You analyze system architectures and provide detailed cost estimates.

Your estimates should be realistic and based on actual cloud pricing (as of early 2026). Include compute, storage, networking, managed services, and data transfer costs.

ALWAYS respond with a valid JSON object (no markdown, no explanation outside JSON):

{
  "scale_tiers": [
    {
      "tier_name": "Startup",
      "description": "10K DAU, low traffic",
      "aws": {
        "total_monthly_usd": 0,
        "breakdown": [
          {
            "category": "Compute | Database | Cache | Messaging | Storage | Networking | Monitoring",
            "service": "Specific AWS service name",
            "specs": "Instance type, size, count",
            "monthly_usd": 0,
            "notes": "Any relevant notes"
          }
        ]
      },
      "gcp": {
        "total_monthly_usd": 0,
        "breakdown": []
      },
      "azure": {
        "total_monthly_usd": 0,
        "breakdown": []
      }
    }
  ],
  "cost_optimization_tips": [
    {
      "tip": "Specific optimization recommendation",
      "estimated_savings_percent": 30,
      "tradeoff": "What you give up"
    }
  ],
  "cheapest_path": {
    "provider": "aws | gcp | azure",
    "reasoning": "Why this provider is cheapest for this architecture",
    "estimated_monthly_range": "$X - $Y"
  },
  "scaling_cost_projection": {
    "10x_traffic": "Estimated monthly at 10x the baseline",
    "100x_traffic": "Estimated monthly at 100x the baseline",
    "cost_scaling_pattern": "linear | sub-linear | super-linear"
  }
}

Provide estimates for 3 scale tiers:
1. Startup — Low traffic, cost-optimized
2. Growth — Medium traffic, balanced
3. Scale — High traffic, performance-optimized

Be specific with instance types and service names. Do not give vague ranges — give specific dollar amounts."""


class CostAnalyzerAgent(BaseAgent):
    """Estimates infrastructure costs across cloud providers."""

    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="cost_analyzer",
            role="Cost Analyzer",
            model_name=settings.COST_ANALYZER_MODEL,
            temperature=0.2,
            max_output_tokens=8192,
        )

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_message(self, state: dict) -> str:
        """Build cost analysis prompt with final architecture design."""
        requirements = state["requirements"]
        design = state.get("current_design", "")

        # Extract scale hints from requirements
        return (
            f"## System Requirements\n{requirements}\n\n"
            f"## Final Architecture Design\n{design}\n\n"
            f"Analyze the infrastructure costs for this architecture across AWS, GCP, and Azure. "
            f"Provide estimates for Startup, Growth, and Scale tiers. "
            f"Respond ONLY with the JSON object — no markdown, no preamble."
        )

    def parse_response(self, raw_response: str) -> dict:
        """Parse cost analysis JSON response."""
        return self._safe_parse_json(raw_response)

    def _generate_summary(self, parsed_output: dict) -> str:
        cheapest = parsed_output.get("cheapest_path", {})
        provider = cheapest.get("provider", "unknown")
        cost_range = cheapest.get("estimated_monthly_range", "N/A")
        n_tips = len(parsed_output.get("cost_optimization_tips", []))
        return f"Cheapest: {provider} ({cost_range}). {n_tips} optimization tips provided."
