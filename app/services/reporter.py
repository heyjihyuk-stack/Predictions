from __future__ import annotations

"""Report generation from simulation results."""

import logging
import uuid
from datetime import datetime
from pathlib import Path

from app.models.domain import AnalystView, Entity, Report
from app.services.llm import chat
from config.settings import get_settings

logger = logging.getLogger(__name__)


def _load_prompt() -> str:
    settings = get_settings()
    path = Path(settings.PROMPTS_DIR) / "report.txt"
    return path.read_text()


def generate_report(
    topic: str,
    articles_count: int,
    entities: list[Entity],
    views: list[AnalystView],
    synthesis: str,
) -> Report:
    """Generate a structured prediction report from analyst views."""
    prompt = _load_prompt()

    # Build entity summary
    entity_summary = "\n".join(
        f"- {e.name} ({e.entity_type}, {e.mentions} mentions)" for e in entities[:20]
    )

    # Build analyst views summary
    views_text = ""
    for v in views:
        views_text += f"\n### {v.analyst} ({v.stance}, confidence: {v.confidence:.0%})\n"
        views_text += f"**Prediction:** {v.prediction}\n"
        views_text += f"**Reasoning:** {v.reasoning}\n"
        views_text += f"**Key Factors:** {', '.join(v.key_factors)}\n"
        views_text += f"**Risks:** {', '.join(v.risks)}\n"
        views_text += f"**Time Horizon:** {v.time_horizon}\n"

    user_content = (
        f"Topic: {topic}\n\n"
        f"Articles Analyzed: {articles_count}\n\n"
        f"Key Entities:\n{entity_summary}\n\n"
        f"Analyst Views:\n{views_text}\n\n"
        f"Moderator Synthesis:\n{synthesis}"
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]

    report_text = chat(messages, temperature=0.5)

    # Extract predictions from views
    predictions = []
    for v in views:
        predictions.append(
            {
                "analyst": v.analyst,
                "stance": v.stance,
                "prediction": v.prediction,
                "confidence": v.confidence,
                "time_horizon": v.time_horizon,
            }
        )

    # Identify dissenting views
    stances = [v.stance for v in views]
    has_dissent = len(set(stances)) > 1
    dissenting = ""
    if has_dissent:
        minority_stance = min(set(stances), key=stances.count)
        dissenters = [v for v in views if v.stance == minority_stance]
        dissenting = "\n".join(
            f"- {v.analyst}: {v.prediction} (confidence: {v.confidence:.0%})"
            for v in dissenters
        )

    return Report(
        id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        topic=topic,
        articles_analyzed=articles_count,
        entities=entities,
        views=views,
        synthesis=report_text,
        predictions=predictions,
        dissenting_views=dissenting,
    )
