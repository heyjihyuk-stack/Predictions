"""Domain models for the predictions platform."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    url: str
    title: str
    text: str
    source: str
    category: str
    published: datetime | None = None
    fetched: datetime = field(default_factory=datetime.utcnow)

    def summary_context(self, max_chars: int = 1000) -> str:
        """Return a truncated version suitable for LLM context."""
        text = self.text[:max_chars]
        return f"[{self.source} | {self.category}] {self.title}\n{text}"


@dataclass
class Entity:
    name: str
    entity_type: str  # COMPANY, COUNTRY, PERSON, EVENT, COMMODITY, INDEX
    mentions: int = 1
    relationships: list[tuple[str, str]] = field(default_factory=list)

    def __hash__(self):
        return hash((self.name.lower(), self.entity_type))


@dataclass
class AnalystView:
    analyst: str
    stance: str  # bullish, bearish, neutral, cautious, mixed
    prediction: str
    confidence: float  # 0.0 to 1.0
    reasoning: str
    key_factors: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    time_horizon: str = "1-4 weeks"


@dataclass
class Report:
    id: str
    timestamp: datetime
    topic: str
    articles_analyzed: int
    entities: list[Entity]
    views: list[AnalystView]
    synthesis: str
    predictions: list[dict] = field(default_factory=list)
    dissenting_views: str = ""
