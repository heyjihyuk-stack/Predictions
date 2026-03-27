from __future__ import annotations

"""Entity and relationship extraction from news articles."""

import logging
from pathlib import Path

from app.models.domain import Article, Entity
from app.services.llm import chat_json
from config.settings import get_settings

logger = logging.getLogger(__name__)


def _load_prompt() -> str:
    settings = get_settings()
    path = Path(settings.PROMPTS_DIR) / "extractor.txt"
    return path.read_text()


def extract_entities(articles: list[Article]) -> list[Entity]:
    """Extract entities and relationships from a batch of articles using LLM."""
    if not articles:
        return []

    # Build context from articles
    context_parts = []
    for i, article in enumerate(articles[:30], 1):  # Cap to avoid token limits
        context_parts.append(f"Article {i}: {article.summary_context(800)}")
    context = "\n\n".join(context_parts)

    prompt = _load_prompt()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Extract entities and relationships from these articles:\n\n{context}"},
    ]

    result = chat_json(messages, temperature=0.3)

    entities = []
    for e in result.get("entities", []):
        relationships = []
        for rel in e.get("relationships", []):
            if isinstance(rel, dict):
                relationships.append((rel.get("type", ""), rel.get("target", "")))
            elif isinstance(rel, (list, tuple)) and len(rel) >= 2:
                relationships.append((rel[0], rel[1]))
        entities.append(
            Entity(
                name=e.get("name", "Unknown"),
                entity_type=e.get("type", "UNKNOWN"),
                mentions=e.get("mentions", 1),
                relationships=relationships,
            )
        )

    logger.info("Extracted %d entities from %d articles", len(entities), len(articles))
    return entities
