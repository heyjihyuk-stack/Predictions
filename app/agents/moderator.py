"""Moderator agent — synthesizes all analyst views into a unified assessment."""

import logging
from pathlib import Path

from app.models.domain import AnalystView
from app.services.llm import chat
from config.settings import get_settings

logger = logging.getLogger(__name__)


class Moderator:
    name = "Moderator"

    def __init__(self):
        settings = get_settings()
        path = Path(settings.PROMPTS_DIR) / "moderator.txt"
        if path.exists():
            self._system_prompt = path.read_text()
        else:
            self._system_prompt = (
                "You are a senior investment strategist and moderator. "
                "Synthesize multiple analyst perspectives into a balanced assessment."
            )

    def synthesize(self, views: list[AnalystView]) -> str:
        """Synthesize multiple analyst views into a unified assessment."""
        views_text = ""
        for v in views:
            views_text += (
                f"\n## {v.analyst} — {v.stance} (confidence: {v.confidence:.0%})\n"
                f"**Prediction:** {v.prediction}\n"
                f"**Reasoning:** {v.reasoning}\n"
                f"**Key Factors:** {', '.join(v.key_factors)}\n"
                f"**Risks:** {', '.join(v.risks)}\n"
                f"**Time Horizon:** {v.time_horizon}\n"
            )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": (
                    "Synthesize the following analyst views into a unified market assessment. "
                    "Identify areas of agreement, disagreement, and the overall weight of evidence. "
                    "Provide a clear, actionable summary with confidence-weighted predictions.\n\n"
                    f"{views_text}"
                ),
            },
        ]

        return chat(messages, temperature=0.5)
