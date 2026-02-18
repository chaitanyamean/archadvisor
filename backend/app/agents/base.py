"""Base agent class with LLM integration, retry logic, and cost tracking."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Optional
from datetime import datetime
import json
import re
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.models.events import AgentStartedEvent, AgentThinkingEvent, AgentCompletedEvent, ErrorEvent

logger = structlog.get_logger()

# Approximate token costs (USD per 1K tokens)
MODEL_COSTS = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}


class BaseAgent(ABC):
    """Abstract base class for all ArchAdvisor agents."""

    def __init__(
        self,
        name: str,
        role: str,
        model_name: Optional[str] = None,
        temperature: float = 0.5,
        max_output_tokens: int = 4096,
        json_mode: bool = False,
    ):
        self.name = name
        self.role = role
        self.model_name = model_name or get_settings().ARCHITECT_MODEL
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.json_mode = json_mode
        self._llm = None

    @property
    def llm(self):
        """Lazy-initialize the LLM client."""
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _create_llm(self):
        """Create the OpenAI LLM client."""
        settings = get_settings()

        kwargs = {
            "model": self.model_name,
            "api_key": settings.OPENAI_API_KEY,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        if self.json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

        return ChatOpenAI(**kwargs)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        ...

    @abstractmethod
    def build_user_message(self, state: dict) -> str:
        """Build the user message from current workflow state."""
        ...

    @abstractmethod
    def parse_response(self, raw_response: str) -> dict:
        """Parse the LLM response into structured output."""
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost of an LLM call."""
        costs = MODEL_COSTS.get(self.model_name, {"input": 0.003, "output": 0.015})
        return (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=lambda retry_state: logger.warning(
            "llm_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    async def _call_llm(self, system_prompt: str, user_message: str) -> dict:
        """Call the LLM with retry logic. Returns response + usage metadata."""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        response = await self.llm.ainvoke(messages)

        # Extract token usage from response metadata
        usage = getattr(response, "usage_metadata", {}) or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)

        return {
            "content": response.content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": self.estimate_cost(input_tokens, output_tokens),
        }

    async def run(self, state: dict, event_callback=None) -> dict:
        """
        Execute the agent: build prompt, call LLM, parse response, emit events.

        Args:
            state: Current workflow state
            event_callback: Async function to emit WebSocket events

        Returns:
            Dict with parsed output, metadata, and state updates
        """
        start_time = time.time()

        # Emit: agent started
        if event_callback:
            await event_callback(
                AgentStartedEvent(
                    agent=self.name,
                    agent_label=self.role,
                    message=f"{self.role} is analyzing the architecture...",
                ).model_dump()
            )

        try:
            # Build prompts
            system_prompt = self.get_system_prompt()
            user_message = self.build_user_message(state)

            # Emit: thinking
            if event_callback:
                await event_callback(
                    AgentThinkingEvent(
                        agent=self.name,
                        message=f"{self.role} is processing...",
                    ).model_dump()
                )

            # Call LLM
            llm_result = await self._call_llm(system_prompt, user_message)

            # Parse response
            parsed = self.parse_response(llm_result["content"])

            duration = time.time() - start_time

            # Emit: completed
            if event_callback:
                await event_callback(
                    AgentCompletedEvent(
                        agent=self.name,
                        summary=self._generate_summary(parsed),
                        duration_seconds=round(duration, 2),
                        cost_usd=round(llm_result["cost"], 4),
                    ).model_dump()
                )

            logger.info(
                "agent_completed",
                agent=self.name,
                model=self.model_name,
                duration_seconds=round(duration, 2),
                input_tokens=llm_result["input_tokens"],
                output_tokens=llm_result["output_tokens"],
                cost_usd=round(llm_result["cost"], 4),
            )

            return {
                "output": parsed,
                "raw_response": llm_result["content"],
                "metadata": {
                    "agent": self.name,
                    "model": self.model_name,
                    "duration_seconds": round(duration, 2),
                    "input_tokens": llm_result["input_tokens"],
                    "output_tokens": llm_result["output_tokens"],
                    "cost_usd": round(llm_result["cost"], 4),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            }

        except Exception as e:
            duration = time.time() - start_time
            logger.error("agent_failed", agent=self.name, error=str(e), duration_seconds=round(duration, 2))

            if event_callback:
                await event_callback(
                    ErrorEvent(
                        message=f"{self.role} encountered an error: {str(e)}",
                        recoverable=False,
                    ).model_dump()
                )
            raise

    def _generate_summary(self, parsed_output: dict) -> str:
        """Generate a brief summary from parsed output. Override in subclasses."""
        return f"{self.role} completed analysis."

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Remove markdown code fences from LLM output."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    @staticmethod
    def _fix_llm_json(text: str) -> str:
        """Fix common JSON formatting issues produced by LLMs."""
        # Remove trailing commas before } or ]
        return re.sub(r",\s*([}\]])", r"\1", text)

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        """Find and extract the first complete JSON object from text."""
        match = re.search(r"\{", text)
        if not match:
            return None
        # Walk through characters tracking brace depth outside of strings
        depth, in_string, escape_next = 0, False, False
        start = match.start()
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = not in_string
            elif not in_string and ch == "{":
                depth += 1
            elif not in_string and ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    def _safe_parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response, handling common LLM formatting issues."""
        cleaned = self._strip_code_fences(text)

        # First attempt: parse as-is
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_attempt_1_failed", agent=self.name, error=str(e))

        # Second attempt: fix trailing commas, comments
        try:
            result = json.loads(self._fix_llm_json(cleaned))
            logger.info("json_parse_recovered", agent=self.name, method="fix_llm_json")
            return result
        except json.JSONDecodeError as e:
            logger.warning("json_parse_attempt_2_failed", agent=self.name, error=str(e))

        # Third attempt: extract the first JSON object from surrounding text
        extracted = self._extract_json_object(cleaned)
        if extracted:
            try:
                result = json.loads(self._fix_llm_json(extracted))
                logger.info("json_parse_recovered", agent=self.name, method="extract_object")
                return result
            except json.JSONDecodeError as e:
                logger.warning("json_parse_attempt_3_failed", agent=self.name, error=str(e))

        # All attempts failed — log raw response snippet for debugging
        logger.error(
            "json_parse_all_attempts_failed",
            agent=self.name,
            response_length=len(text),
            response_preview=cleaned[:500],
        )
        return json.loads(cleaned)
