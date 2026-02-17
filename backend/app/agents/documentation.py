"""Documentation Agent — produces polished architecture documents."""

import json

from app.agents.base import BaseAgent
from app.config import get_settings

SYSTEM_PROMPT = """You are a Senior Technical Writer specializing in software architecture documentation. You create clear, comprehensive, and well-structured architecture documents that serve both executives and engineers.

Given the final architecture design, debate history, and cost analysis, produce a complete architecture document in Markdown format.

Your output should be a JSON object with the document sections:

{
  "title": "Architecture document title",
  "executive_summary": "3-5 sentence summary for leadership — what, why, and key metrics",
  "sections": [
    {
      "heading": "Section heading",
      "level": 1,
      "content": "Markdown content for this section"
    }
  ],
  "diagrams": [
    {
      "type": "component | sequence | deployment | er",
      "title": "Diagram title",
      "mermaid_code": "Valid Mermaid diagram code"
    }
  ],
  "decision_log": [
    {
      "id": "ADR-001",
      "title": "Decision title",
      "status": "accepted | revised | deferred",
      "context": "Why this decision was needed",
      "decision": "What was decided",
      "consequences": "Positive and negative consequences"
    }
  ]
}

Required sections (in order) — EVERY section is MANDATORY and must have substantial content:

1. **Executive Summary** — 3-5 sentences for leadership with key metrics (users, throughput, cost range)
2. **Architecture Overview** — Style justification, high-level description, include component diagram reference
3. **Component Deep Dive** — For EACH component include:
   - For custom services: at least 3 API endpoints with method, path, request/response schemas; data models with field names and types; scaling strategy with specific numbers; technology justification
   - For third-party managed services (SES, Twilio, FCM, Stripe, etc.): integration pattern, failure handling strategy, cost per unit, and SLA
4. **Data Flow** — Sequence diagrams for at least 2 key user flows with step-by-step descriptions
5. **Infrastructure & Deployment** — Regions, containerization, CI/CD, deployment strategy details
6. **Cost Analysis** — Present costs in TWO tables:
   (a) Summary table by provider and tier: | Tier | AWS | GCP | Azure |
   (b) Detailed breakdown table by service category: | Category | Service | Specs | Monthly USD |
   Include the top 3 cost optimization tips with estimated savings percentages.
   A pre-formatted cost table is provided in the input — include it directly.
7. **Security Architecture** — Authentication method, authorization model, encryption (at rest + in transit), secrets management, network security (VPC, security groups), compliance considerations
8. **Tradeoff Log** — For EACH debate round: what the Devil's Advocate found, how the Architect responded, and the outcome. Use the debate history provided.
9. **Reliability & Validation** — Include the design validation score, composite availability calculation (show the math: ServiceA(99.99%) x ServiceB(99.9%) = X%), SLA targets, and any unresolved validation findings
10. **Risk Register** — Markdown table with columns: Risk, Severity, Likelihood, Mitigation, Owner. At least 5 risks.
11. **Architecture Decision Records** — At least 3 ADRs in the decision_log array

CRITICAL RULES:
- ALL 11 SECTIONS ARE MANDATORY. If you skip a section, the document fails review. If running low on space, make each section briefer rather than dropping sections entirely.
- ALWAYS generate a deployment Mermaid diagram showing regions, AZs, and traffic routing — infer it from the deployment config even if the architecture design doesn't include one.
- You MUST produce at least 3 diagrams: component, sequence, and deployment.

Use Mermaid syntax for all diagrams. Make the document professional and ready for engineering review.
Respond ONLY with the JSON object — no markdown wrapping."""


class DocumentationAgent(BaseAgent):
    """Produces polished HLD/LLD architecture documents."""

    def __init__(self):
        settings = get_settings()
        super().__init__(
            name="documentation",
            role="Documentation",
            model_name=settings.DOCUMENTATION_MODEL,
            temperature=0.4,
            max_output_tokens=16000,
        )

    def get_system_prompt(self) -> str:
        return SYSTEM_PROMPT

    def build_user_message(self, state: dict) -> str:
        """Build documentation prompt with all context."""
        requirements = state["requirements"]
        design = state.get("current_design", "")
        review = state.get("review_findings", "")
        cost = state.get("cost_analysis", "")

        # Collect debate history with raw_output for detail
        debate_history = ""
        messages = state.get("messages", [])
        if messages:
            debate_entries = []
            for msg in messages:
                agent = msg.get("agent", "unknown")
                role = msg.get("role", agent)
                summary = msg.get("summary", "")
                raw = msg.get("raw_output", "")
                if agent in ("devils_advocate", "validator") and raw:
                    debate_entries.append(f"### {role}\n**Summary**: {summary}\n**Full Output**:\n{raw}")
                else:
                    debate_entries.append(f"### {role}\n{summary}")
            debate_history = "\n\n## Debate History\n" + "\n\n".join(debate_entries)

        # Pre-format cost data as Markdown tables
        cost_section = self._preformat_cost_table(cost)

        # Validation info with composite availability math
        validation_info = ""
        validation_score = state.get("validation_score")
        validation_report = state.get("validation_report", "")
        if validation_score is not None:
            passed = state.get("validation_passed", False)
            composite_math = self._extract_composite_availability(validation_report)
            validation_info = (
                f"\n\n## Design Validation\n"
                f"Score: {validation_score}/100 | {'PASSED' if passed else 'FAILED'}\n"
                f"{composite_math}\n"
                f"Full report: {validation_report}\n"
                f"IMPORTANT: Include a 'Reliability & Validation' section with this score, "
                f"the composite availability math shown above, and any unresolved findings."
            )

        return (
            f"## Original Requirements\n{requirements}\n\n"
            f"## Final Architecture Design\n{design}\n\n"
            f"## Devil's Advocate Review\n{review}\n\n"
            f"{cost_section}\n"
            f"{validation_info}"
            f"{debate_history}\n\n"
            f"Produce a comprehensive architecture document covering ALL 11 required sections with substantial detail. "
            f"Include Mermaid diagrams for component, sequence, AND deployment views. "
            f"Respond ONLY with the JSON object — no markdown wrapping."
        )

    def _preformat_cost_table(self, cost_json_str: str) -> str:
        """Pre-format cost JSON into Markdown tables so the LLM just includes them."""
        if not cost_json_str:
            return "## Cost Analysis Data\n\nNo cost data available."

        try:
            cost_data = json.loads(cost_json_str)
        except (json.JSONDecodeError, TypeError):
            return f"## Cost Analysis Data\n\n```json\n{cost_json_str}\n```"

        lines = ["## Cost Analysis Data (include BOTH tables in the document)\n"]
        tiers = cost_data.get("scale_tiers", [])

        if tiers:
            lines.extend(self._format_summary_table(tiers))
            lines.extend(self._format_breakdown_table(tiers))

        lines.extend(self._format_tips_and_recommendation(cost_data))
        lines.append(f"\nFull raw cost data for reference:\n```json\n{cost_json_str[:3000]}\n```")

        return "\n".join(lines)

    @staticmethod
    def _format_cost_cell(value):
        """Format a cost value as a dollar string."""
        if isinstance(value, (int, float)):
            return f"${value:,}"
        return str(value)

    def _format_summary_table(self, tiers: list) -> list:
        """Build the summary-by-provider Markdown table."""
        lines = [
            "### Summary by Provider and Tier\n",
            "| Tier | AWS | GCP | Azure |",
        ]
        for tier in tiers:
            name = tier.get("tier_name", "?")
            aws = self._format_cost_cell(tier.get("aws", {}).get("total_monthly_usd", "N/A"))
            gcp = self._format_cost_cell(tier.get("gcp", {}).get("total_monthly_usd", "N/A"))
            azure = self._format_cost_cell(tier.get("azure", {}).get("total_monthly_usd", "N/A"))
            lines.append(f"| {name} | {aws} | {gcp} | {azure} |")
        return lines

    @staticmethod
    def _format_breakdown_table(tiers: list) -> list:
        """Build the per-service breakdown Markdown table from the first tier."""
        lines = ["\n### Detailed Breakdown (Startup Tier — AWS)\n"]
        startup = tiers[0] if tiers else {}
        aws_breakdown = startup.get("aws", {}).get("breakdown", [])
        if not aws_breakdown:
            return lines

        lines.append("| Category | Service | Specs | Monthly USD |")
        lines.append("|----------|---------|-------|-------------|")
        for item in aws_breakdown:
            lines.append(
                f"| {item.get('category', '')} | {item.get('service', '')} "
                f"| {item.get('specs', '')} | ${item.get('monthly_usd', 'N/A')} |"
            )
        return lines

    @staticmethod
    def _format_tips_and_recommendation(cost_data: dict) -> list:
        """Format optimization tips and cheapest-path recommendation."""
        lines = []
        tips = cost_data.get("cost_optimization_tips", [])
        if tips:
            lines.append("\n### Cost Optimization Tips\n")
            for i, tip in enumerate(tips, 1):
                savings = tip.get("estimated_savings_percent", "?")
                tradeoff = tip.get("tradeoff", "N/A")
                lines.append(f"{i}. **{tip.get('tip', '')}** — ~{savings}% savings (Tradeoff: {tradeoff})")

        cheapest = cost_data.get("cheapest_path", {})
        if cheapest:
            provider = cheapest.get("provider", "N/A").upper()
            reasoning = cheapest.get("reasoning", "")
            cost_range = cheapest.get("estimated_monthly_range", "N/A")
            lines.append(f"\n**Recommended Provider**: {provider} — {reasoning}")
            lines.append(f"**Estimated Range**: {cost_range}")

        return lines

    def _extract_composite_availability(self, validation_report_str: str) -> str:
        """Extract composite availability math from the validation report."""
        if not validation_report_str:
            return ""
        try:
            report = json.loads(validation_report_str)
            errors = report.get("errors", [])
            for error in errors:
                if error.get("code") == "AVAIL_COMPOSITE_BELOW_TARGET":
                    msg = error.get("message", "")
                    evidence = error.get("evidence", "")
                    return (
                        f"**Composite Availability Calculation**: {msg}\n"
                        f"Evidence: {evidence}\n"
                        f"IMPORTANT: Include this exact calculation in the Reliability & Validation section."
                    )
            # If no composite error, check score breakdown
            breakdown = report.get("score_breakdown", {})
            if breakdown:
                return f"**Score Breakdown**: Reliability={breakdown.get('reliability', '?')}/30, Scalability={breakdown.get('scalability', '?')}/25, Consistency={breakdown.get('consistency', '?')}/15, Security={breakdown.get('security', '?')}/15, Operational={breakdown.get('operational', '?')}/15"
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    def parse_response(self, raw_response: str) -> dict:
        """Parse documentation JSON response."""
        return self._safe_parse_json(raw_response)

    def render_markdown(self, parsed_output: dict) -> str:
        """Render the structured output into a complete Markdown document."""
        lines = []
        title = parsed_output.get("title", "Architecture Document")
        lines.append(f"# {title}\n")

        # Executive Summary
        exec_summary = parsed_output.get("executive_summary", "")
        if exec_summary:
            lines.append(f"## Executive Summary\n\n{exec_summary}\n")

        # Main sections
        for section in parsed_output.get("sections", []):
            level = section.get("level", 2)
            heading = "#" * (level + 1) + " " + section["heading"]
            lines.append(f"{heading}\n\n{section['content']}\n")

        self._render_diagrams(lines, parsed_output)
        self._render_validation(lines, parsed_output)
        self._render_adrs(lines, parsed_output)

        return "\n".join(lines)
      
    @staticmethod
    def _render_diagrams(lines: list[str], parsed_output: dict) -> None:
        """Render architecture diagrams section."""
        diagrams = parsed_output.get("diagrams", [])
        if not diagrams:
            return
        lines.append("## Architecture Diagrams\n")
        for diagram in diagrams:
            lines.append(f"### {diagram['title']}\n")
            lines.append(f"```mermaid\n{diagram['mermaid_code']}\n```\n")

    @staticmethod
    def _render_validation(lines: list[str], parsed_output: dict) -> None:
        """Render validation score, severity breakdown, and critical/high findings."""
        validation_score = parsed_output.get("validation_score")
        if validation_score is None:
            return

        passed = parsed_output.get("validation_passed", False)
        summary = parsed_output.get("validation_summary", {})
        verdict = parsed_output.get("validation_verdict", "")
        findings = parsed_output.get("validation_findings", [])

        lines.append("## Design Validation\n")
        lines.append(f"**Score**: {validation_score}/100 | **Status**: {'PASSED' if passed else 'FAILED'}\n")

        # Severity breakdown table
        if summary:
            lines.append("### Severity Breakdown\n")
            lines.append("| Severity | Count |")
            lines.append("|----------|-------|")
            for sev in ("critical", "high", "medium", "low"):
                count = summary.get(sev, 0)
                if count > 0:
                    lines.append(f"| {sev.upper()} | {count} |")
            lines.append("")

        # Critical and high findings table
        if findings:
            lines.append("### Critical & High Findings\n")
            lines.append("| Severity | Finding | Source |")
            lines.append("|----------|---------|--------|")
            for f in findings:
                sev = f["severity"].upper()
                msg = f["message"][:120]
                source = f.get("evidence", "—") if f.get("category") == "domain_pattern" else "General"
                lines.append(f"| {sev} | {msg} | {source} |")
            lines.append("")

        if verdict:
            lines.append(f"> {verdict}\n")

    @staticmethod
    def _render_adrs(lines: list[str], parsed_output: dict) -> None:
        """Render Architecture Decision Records if not already in a section."""
        decisions = parsed_output.get("decision_log", [])
        if not decisions:
            return
        sections_text = " ".join(s.get("content", "") for s in parsed_output.get("sections", []))
        if "ADR-" in sections_text:
            return
        lines.append("## Architecture Decision Records\n")
        for adr in decisions:
            lines.append(f"### {adr['id']}: {adr['title']}\n")
            lines.append(f"**Status**: {adr['status']}\n")
            lines.append(f"**Context**: {adr['context']}\n")
            lines.append(f"**Decision**: {adr['decision']}\n")
            lines.append(f"**Consequences**: {adr['consequences']}\n")


    def _generate_summary(self, parsed_output: dict) -> str:
        n_sections = len(parsed_output.get("sections", []))
        n_diagrams = len(parsed_output.get("diagrams", []))
        n_adrs = len(parsed_output.get("decision_log", []))
        return f"Generated document with {n_sections} sections, {n_diagrams} diagrams, {n_adrs} ADRs."
