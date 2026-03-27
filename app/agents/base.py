from __future__ import annotations

"""Base analyst agent class."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from app.models.domain import AnalystView, Article, Entity
from app.services.llm import chat_json
from config.settings import get_settings

logger = logging.getLogger(__name__)


class BaseAnalyst(ABC):
    """Base class for all analyst agents."""

    name: str = "Analyst"
    prompt_file: str = "analyst_system.txt"

    def __init__(self):
        self._system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        settings = get_settings()
        path = Path(settings.PROMPTS_DIR) / self.prompt_file
        if path.exists():
            return path.read_text()
        logger.warning("Prompt file not found: %s, using default", path)
        return f"You are {self.name}. Analyze the provided news and data."

    def analyze(self, articles: list[Article], entities: list[Entity]) -> AnalystView:
        """Analyze articles and entities, returning a structured view."""
        # Build context
        article_context = "\n\n".join(a.summary_context(600) for a in articles[:20])
        entity_context = "\n".join(
            f"- {e.name} ({e.entity_type})" for e in entities[:15]
        )

        user_content = (
            f"Based on the following recent news and identified entities, provide your analysis.\n\n"
            f"KEY ENTITIES:\n{entity_context}\n\n"
            f"RECENT NEWS:\n{article_context}\n\n"
            "Respond with a JSON object containing:\n"
            '- "stance": one of "bullish", "bearish", "neutral", "cautious", "mixed"\n'
            '- "prediction": your main prediction (1-2 sentences)\n'
            '- "confidence": a float between 0.0 and 1.0\n'
            '- "reasoning": detailed reasoning (2-4 sentences)\n'
            '- "key_factors": list of 3-5 key factors driving your view\n'
            '- "risks": list of 2-3 main risks to your prediction\n'
            '- "time_horizon": e.g. "1-2 weeks", "1-3 months"\n'
        )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = chat_json(messages, temperature=0.7)

        return AnalystView(
            analyst=self.name,
            stance=result.get("stance", "neutral"),
            prediction=result.get("prediction", "No prediction available"),
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning", ""),
            key_factors=result.get("key_factors", []),
            risks=result.get("risks", []),
            time_horizon=result.get("time_horizon", "1-4 weeks"),
        )
