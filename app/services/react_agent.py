from __future__ import annotations

"""ReACT (Reasoning + Acting) agent engine.

Replaces simple 1-shot LLM calls with a multi-step Thought -> Action ->
Observation loop, inspired by MiroFish's report_agent pattern.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from app.services import llm
from app.services.action_logger import ActionLogger, ActionType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool registry helpers
# ---------------------------------------------------------------------------

_GLOBAL_TOOLS: dict[str, dict[str, Any]] = {}


def tool(name: str, description: str) -> Callable:
    """Decorator that registers a callable as an agent tool.

    Usage::

        @tool("search_news", "Search recent news for a query string.")
        def search_news(query: str) -> str:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        _GLOBAL_TOOLS[name] = {
            "name": name,
            "description": description,
            "fn": fn,
        }
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------


@tool("search_news", "Search recent news articles for a given query.")
def search_news(query: str) -> str:
    """Use the LLM to synthesize a news summary for *query*."""
    messages = [
        {"role": "system", "content": "You are a financial news research assistant."},
        {
            "role": "user",
            "content": (
                f"Summarize the most important recent news about: {query}. "
                "Focus on market-moving events. Be concise."
            ),
        },
    ]
    return llm.chat(messages, temperature=0.3)


@tool("analyze_technicals", "Analyze technical indicators for an asset.")
def analyze_technicals(asset_id: str) -> str:
    """Return a technical-analysis summary for *asset_id*."""
    messages = [
        {"role": "system", "content": "You are a technical analysis expert."},
        {
            "role": "user",
            "content": (
                f"Provide a brief technical analysis for {asset_id}. "
                "Cover trend direction, key support/resistance levels, "
                "momentum indicators, and volume patterns."
            ),
        },
    ]
    return llm.chat(messages, temperature=0.3)


@tool("check_correlations", "Check correlations between a list of assets.")
def check_correlations(assets: str) -> str:
    """Describe known correlations among the comma-separated *assets*."""
    messages = [
        {"role": "system", "content": "You are a quantitative analyst."},
        {
            "role": "user",
            "content": (
                f"Analyze the correlations between these assets: {assets}. "
                "Describe historical correlation patterns and any recent "
                "divergences that could signal opportunity or risk."
            ),
        },
    ]
    return llm.chat(messages, temperature=0.3)


@tool("assess_risk", "Assess risk for a given scenario description.")
def assess_risk(scenario: str) -> str:
    """Provide a risk assessment for *scenario*."""
    messages = [
        {"role": "system", "content": "You are a risk management specialist."},
        {
            "role": "user",
            "content": (
                f"Assess the risks in this scenario: {scenario}. "
                "Rate overall risk (low/medium/high), identify the top 3 risk "
                "factors, and suggest mitigation approaches."
            ),
        },
    ]
    return llm.chat(messages, temperature=0.3)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReasoningStep:
    """One iteration of the Thought -> Action -> Observation loop."""

    step: int
    thought: str
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None


@dataclass
class AgentResult:
    """Final output produced by the ReACT agent."""

    conclusion: str
    confidence: float
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)
    tool_calls_made: list[str] = field(default_factory=list)
    evidence_collected: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ReACT Agent
# ---------------------------------------------------------------------------

_MIN_TOOL_CALLS = 2
_MAX_TOOL_CALLS = 5
_MAX_RETRIES = 3  # forced completion after this many fruitless loops


class ReACTAgent:
    """Multi-step Reasoning + Acting agent.

    Parameters
    ----------
    name:
        Human-readable agent name (used in logging).
    extra_tools:
        Optional mapping of ``{name: {"description": str, "fn": callable}}``
        merged with globally registered tools.
    """

    def __init__(self, name: str = "ReACTAgent", extra_tools: dict[str, dict[str, Any]] | None = None):
        self.name = name
        self._action_logger = ActionLogger()

        # Merge global tools with any extras supplied at construction time.
        self.tools: dict[str, dict[str, Any]] = dict(_GLOBAL_TOOLS)
        if extra_tools:
            for tname, tdef in extra_tools.items():
                self.tools[tname] = tdef

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
        context: str = "",
        tools: dict[str, dict[str, Any]] | None = None,
    ) -> AgentResult:
        """Execute the ReACT loop for *task* and return an ``AgentResult``.

        Parameters
        ----------
        task:
            Plain-English description of what the agent should figure out.
        context:
            Optional background information the agent should consider.
        tools:
            Per-call tool overrides.  Merged on top of instance tools.
        """
        active_tools = dict(self.tools)
        if tools:
            active_tools.update(tools)

        tool_descriptions = "\n".join(
            f"- {t['name']}: {t['description']}" for t in active_tools.values()
        )

        reasoning_steps: list[ReasoningStep] = []
        tool_calls_made: list[str] = []
        evidence_collected: list[str] = []
        conversation: list[dict[str, str]] = self._build_initial_messages(
            task, context, tool_descriptions,
        )

        retries_without_progress = 0
        step_num = 0

        while step_num < _MAX_TOOL_CALLS + _MAX_RETRIES:
            step_num += 1

            # ---- Ask the LLM for the next Thought / Action ----
            raw = self._think(conversation, active_tools, tool_calls_made)

            thought = raw.get("thought", "")
            action = raw.get("action")
            action_input = raw.get("action_input", "")
            is_final = raw.get("final_answer") is not None

            rs = ReasoningStep(
                step=step_num,
                thought=thought,
                action=action,
                action_input=action_input,
            )

            # Log the thought
            self._action_logger.log_action(
                agent_name=self.name,
                action_type=ActionType.THOUGHT,
                details={"thought": thought, "step": step_num},
                result=thought,
            )

            # ---- Final answer path ----
            if is_final and len(tool_calls_made) >= _MIN_TOOL_CALLS:
                rs.observation = "Agent reached final answer."
                reasoning_steps.append(rs)
                return self._build_result(
                    raw, reasoning_steps, tool_calls_made, evidence_collected,
                )

            # ---- Tool call path ----
            if action and action in active_tools and len(tool_calls_made) < _MAX_TOOL_CALLS:
                observation = self._execute_tool(
                    active_tools[action], action_input,
                )
                rs.observation = observation
                reasoning_steps.append(rs)
                tool_calls_made.append(action)
                evidence_collected.append(
                    f"[{action}] {observation[:300]}"
                )

                # Feed observation back into the conversation
                conversation.append(
                    {"role": "assistant", "content": json.dumps(raw)},
                )
                conversation.append(
                    {
                        "role": "user",
                        "content": (
                            f"Observation from {action}: {observation}\n\n"
                            "Continue your reasoning. If you have gathered enough "
                            "evidence, provide your final_answer."
                        ),
                    },
                )
                retries_without_progress = 0
                continue

            # ---- No useful action taken -- count as a retry ----
            reasoning_steps.append(rs)
            retries_without_progress += 1

            if retries_without_progress >= _MAX_RETRIES:
                logger.warning(
                    "%s: forcing completion after %d retries without progress",
                    self.name,
                    _MAX_RETRIES,
                )
                return self._force_completion(
                    task, context, reasoning_steps, tool_calls_made, evidence_collected,
                )

            # Nudge the LLM to pick a tool or give a final answer
            nudge = self._build_nudge(
                tool_calls_made, active_tools, is_final, retries_without_progress,
            )
            conversation.append({"role": "assistant", "content": json.dumps(raw)})
            conversation.append({"role": "user", "content": nudge})

        # Absolute safety net
        return self._force_completion(
            task, context, reasoning_steps, tool_calls_made, evidence_collected,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_initial_messages(
        self, task: str, context: str, tool_descriptions: str,
    ) -> list[dict[str, str]]:
        system = (
            "You are a ReACT (Reasoning + Acting) agent. You solve tasks by "
            "iterating through Thought -> Action -> Observation loops.\n\n"
            "Available tools:\n"
            f"{tool_descriptions}\n\n"
            "Respond ONLY with a JSON object. On each step choose ONE of:\n"
            "1. Call a tool:\n"
            '   {"thought": "...", "action": "<tool_name>", "action_input": "..."}\n'
            "2. Provide a final answer (only after calling at least 2 tools):\n"
            '   {"thought": "...", "final_answer": "...", "confidence": 0.0-1.0}\n\n'
            "Rules:\n"
            "- You MUST call at least 2 different tools before giving a final answer.\n"
            "- You may call at most 5 tools total.\n"
            "- Each thought should build on previous observations.\n"
            "- Your final confidence should reflect evidence quality.\n"
        )
        user = f"Task: {task}"
        if context:
            user += f"\n\nContext:\n{context}"

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _think(
        self,
        conversation: list[dict[str, str]],
        active_tools: dict[str, dict[str, Any]],
        tool_calls_made: list[str],
    ) -> dict[str, Any]:
        """Ask the LLM for the next step and return the parsed JSON."""
        try:
            result = llm.chat_json(conversation, temperature=0.4)
        except Exception as exc:
            logger.error("%s: LLM call failed: %s", self.name, exc)
            result = {
                "thought": f"LLM call failed ({exc}). Attempting recovery.",
                "action": None,
                "action_input": "",
            }
        return result

    def _execute_tool(self, tool_def: dict[str, Any], tool_input: str) -> str:
        """Call the tool function and return its string output."""
        fn: Callable = tool_def["fn"]
        name: str = tool_def["name"]
        try:
            result = fn(tool_input)
            observation = str(result)
        except Exception as exc:
            logger.error("Tool %s raised: %s", name, exc)
            observation = f"Tool error: {exc}"

        # Log the tool call
        self._action_logger.log_action(
            agent_name=self.name,
            action_type=ActionType.TOOL_CALL,
            details={"tool": name, "input": tool_input},
            result=observation[:500],
        )

        # Log the observation
        self._action_logger.log_action(
            agent_name=self.name,
            action_type=ActionType.OBSERVATION,
            details={"tool": name},
            result=observation[:500],
        )

        return observation

    def _build_nudge(
        self,
        tool_calls_made: list[str],
        active_tools: dict[str, dict[str, Any]],
        is_final: bool,
        retries: int,
    ) -> str:
        if len(tool_calls_made) < _MIN_TOOL_CALLS:
            unused = [n for n in active_tools if n not in tool_calls_made]
            return (
                f"You must call at least {_MIN_TOOL_CALLS} tools before concluding. "
                f"Tools already used: {tool_calls_made}. "
                f"Remaining options: {unused}. "
                "Please pick one and provide a valid JSON response."
            )
        return (
            "Please provide your final_answer now as a JSON object with "
            '"thought", "final_answer", and "confidence" keys. '
            f"(retry {retries}/{_MAX_RETRIES})"
        )

    def _build_result(
        self,
        raw: dict[str, Any],
        reasoning_steps: list[ReasoningStep],
        tool_calls_made: list[str],
        evidence_collected: list[str],
    ) -> AgentResult:
        conclusion = raw.get("final_answer", "No conclusion reached.")
        confidence = float(raw.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        # Log the prediction
        self._action_logger.log_action(
            agent_name=self.name,
            action_type=ActionType.PREDICTION,
            details={
                "conclusion": conclusion,
                "confidence": confidence,
                "tools_used": tool_calls_made,
            },
            result=conclusion,
        )

        return AgentResult(
            conclusion=conclusion,
            confidence=confidence,
            reasoning_steps=reasoning_steps,
            tool_calls_made=tool_calls_made,
            evidence_collected=evidence_collected,
        )

    def _force_completion(
        self,
        task: str,
        context: str,
        reasoning_steps: list[ReasoningStep],
        tool_calls_made: list[str],
        evidence_collected: list[str],
    ) -> AgentResult:
        """Force the agent to produce a final answer via a dedicated LLM call."""
        evidence_text = "\n".join(evidence_collected) if evidence_collected else "No evidence gathered."
        messages = [
            {
                "role": "system",
                "content": (
                    "You must provide a final conclusion based on the evidence below. "
                    "Respond with JSON: {\"final_answer\": \"...\", \"confidence\": 0.0-1.0}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task: {task}\n\nContext: {context}\n\n"
                    f"Evidence collected:\n{evidence_text}\n\n"
                    "Provide your best conclusion now."
                ),
            },
        ]
        try:
            raw = llm.chat_json(messages, temperature=0.3)
        except Exception:
            raw = {"final_answer": "Unable to reach conclusion due to repeated failures.", "confidence": 0.1}

        return self._build_result(
            raw, reasoning_steps, tool_calls_made, evidence_collected,
        )
