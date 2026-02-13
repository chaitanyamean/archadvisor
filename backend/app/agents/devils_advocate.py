"""Devil's Advocate Agent — reviews architecture designs and identifies weaknesses."""

from app.agents.base import BaseAgent
from app.config import get_settings

SYSTEM_PROMPT = """You are a Senior Site Reliability Engineer and Security Architect with deep expertise in:
- Failure mode analysis (FMEA)
- Security threat modeling (STRIDE)
- Performance bottleneck identification
- Distributed systems failure patterns
- Operational complexity assessment
- Cost efficiency analysis

Your job is to CHALLENGE the proposed architecture. Find every weakness, gap, and risk.
Be thorough but fair — acknowledge strengths while being ruthless about weaknesses.

ALWAYS respond with a valid JSON object (no markdown, no explanation outside JSON):

{
  "severity_summary": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "findings": [
    {
      "id": "F001",
      "severity": "critical | high | medium | low",
      "category": "single_point_of_failure | security | scalability | data_consistency | operational_complexity | cost_inefficiency | missing_requirement | over_engineering",
      "component": "Which component is affected",
      "issue": "Clear description of the problem",
      "impact": "What happens if this isn't addressed",
      "recommendation": "Specific fix or mitigation",
      "question_for_architect": "A pointed question the architect must answer"
    }
  ],
  "missing_considerations": [
    "Things the architect didn't address at all"
  ],
  "strengths": [
    "What the architect got right — be fair"
  ],
  "overall_assessment": "2-3 sentence overall verdict",
  "proceed_recommendation": "proceed | revise_critical | revise_recommended"
}

Review categories to check:
1. Single Points of Failure — What breaks the entire system?
2. Security — Auth, encryption, injection, DDOS, data exposure
3. Scalability — Hotspots, bottlenecks, thundering herd
4. Data Consistency — Race conditions, split brain, stale reads
5. Operational Complexity — Too many services? Debugging difficulty?
6. Cost — Over-provisioned? Expensive managed services where cheaper alternatives exist?
7. Missing Requirements — Anything in the requirements not addressed?
8. Over-Engineering — Unnecessary complexity for the scale?"""


class DevilsAdvocateAgent(BaseAgent):
    """Reviews architecture designs and identifies weaknesses."""

    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="devils_advocate",
            role="Devil's Advocate",
            model_name=settings.DEVILS_ADVOCATE_MODEL,
            temperature=0.3,
            max_output_tokens=4096,
        )

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_message(self, state: dict) -> str:
        """Build review prompt with the current architecture design."""
        requirements = state["requirements"]
        design = state.get("current_design", "")
        debate_round = state.get("debate_round", 1)

        revision_context = ""
        if debate_round > 1:
            revision_context = (
                f"\n\n## Context\n"
                f"This is debate round {debate_round}. The architect has revised the design "
                f"based on your previous findings. Focus on:\n"
                f"1. Whether previous critical findings were adequately addressed\n"
                f"2. Any NEW issues introduced by the revisions\n"
                f"3. Remaining unresolved concerns"
            )

        return (
            f"## Original Requirements\n{requirements}\n\n"
            f"## Proposed Architecture (Round {debate_round})\n{design}\n"
            f"{revision_context}\n\n"
            f"Review this architecture thoroughly. "
            f"Respond ONLY with the JSON object — no markdown, no preamble."
        )

    def parse_response(self, raw_response: str) -> dict:
        """Parse DA's JSON response."""
        return self._safe_parse_json(raw_response)

    def _generate_summary(self, parsed_output: dict) -> str:
        summary = parsed_output.get("severity_summary", {})
        critical = summary.get("critical", 0)
        high = summary.get("high", 0)
        total = sum(summary.values())
        recommendation = parsed_output.get("proceed_recommendation", "unknown")
        return (
            f"Found {total} issues ({critical} critical, {high} high). "
            f"Recommendation: {recommendation}"
        )
