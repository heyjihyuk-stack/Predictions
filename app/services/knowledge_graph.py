from __future__ import annotations

"""In-memory knowledge graph that accumulates entity/relationship data from news.

Tracks entities (companies, countries, people, commodities, etc.) and their
relationships over time, enabling impact-chain analysis and ripple-effect
tracing across markets.
"""

import logging
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    """A single entity in the knowledge graph."""

    name: str
    entity_type: str  # COMPANY, COUNTRY, PERSON, COMMODITY, INDEX, SECTOR, EVENT
    attributes: dict = field(default_factory=dict)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    mention_count: int = 1


@dataclass
class GraphEdge:
    """A directed relationship between two entities."""

    source: str
    target: str
    relation_type: str  # AFFECTS, TRADES_WITH, COMPETES, REGULATES, etc.
    weight: float = 1.0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    evidence: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entity extraction helpers
# ---------------------------------------------------------------------------

# Well-known entity mappings for quick recognition in headlines
_KNOWN_ENTITIES: dict[str, str] = {
    # Countries / regions
    "us": "COUNTRY", "usa": "COUNTRY", "united states": "COUNTRY",
    "china": "COUNTRY", "russia": "COUNTRY", "ukraine": "COUNTRY",
    "eu": "REGION", "europe": "REGION", "japan": "COUNTRY",
    "uk": "COUNTRY", "india": "COUNTRY", "germany": "COUNTRY",
    "france": "COUNTRY", "brazil": "COUNTRY", "iran": "COUNTRY",
    "saudi arabia": "COUNTRY", "taiwan": "COUNTRY", "korea": "COUNTRY",
    "israel": "COUNTRY", "mexico": "COUNTRY", "canada": "COUNTRY",
    "australia": "COUNTRY", "turkey": "COUNTRY",
    # Commodities
    "oil": "COMMODITY", "crude": "COMMODITY", "gold": "COMMODITY",
    "silver": "COMMODITY", "natural gas": "COMMODITY", "copper": "COMMODITY",
    "wheat": "COMMODITY", "corn": "COMMODITY", "lithium": "COMMODITY",
    # Indices / sectors
    "s&p": "INDEX", "s&p 500": "INDEX", "nasdaq": "INDEX",
    "dow": "INDEX", "dow jones": "INDEX", "ftse": "INDEX",
    "nikkei": "INDEX", "dax": "INDEX",
    "tech": "SECTOR", "energy": "SECTOR", "healthcare": "SECTOR",
    "financials": "SECTOR", "real estate": "SECTOR",
    # Institutions
    "fed": "INSTITUTION", "federal reserve": "INSTITUTION",
    "ecb": "INSTITUTION", "boj": "INSTITUTION", "imf": "INSTITUTION",
    "world bank": "INSTITUTION", "opec": "INSTITUTION",
    "sec": "INSTITUTION", "treasury": "INSTITUTION",
    # Major companies (commonly appearing in financial news)
    "apple": "COMPANY", "google": "COMPANY", "microsoft": "COMPANY",
    "amazon": "COMPANY", "tesla": "COMPANY", "nvidia": "COMPANY",
    "meta": "COMPANY", "netflix": "COMPANY",
}

# Financial event keywords that become entity-typed EVENT
_EVENT_KEYWORDS: list[str] = [
    "rate hike", "rate cut", "recession", "inflation", "tariff",
    "sanctions", "trade war", "default", "stimulus", "shutdown",
    "earnings", "ipo", "merger", "acquisition", "bankruptcy",
    "election", "summit", "war", "invasion", "ceasefire",
]

_STOP_WORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "because", "but", "and", "or", "if",
    "about", "up", "out", "off", "over", "its", "it", "this", "that",
    "also", "new", "says", "said", "one", "two", "amid", "like", "could",
    "while", "what", "market", "markets", "report", "reports", "news",
}


def _normalize(name: str) -> str:
    """Lowercase and strip a name for consistent keying."""
    return name.strip().lower()


def _extract_entities_from_text(text: str) -> list[tuple[str, str]]:
    """Return (name, entity_type) pairs found in *text*.

    Checks multi-word known entities first, then single-word matches,
    and finally event keywords.
    """
    text_lower = text.lower()
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Multi-word matches (longest first to avoid partial hits)
    sorted_known = sorted(_KNOWN_ENTITIES.keys(), key=len, reverse=True)
    for phrase in sorted_known:
        if " " not in phrase:
            continue
        if phrase in text_lower and phrase not in seen:
            # Use title-cased version as display name
            found.append((phrase.title(), _KNOWN_ENTITIES[phrase]))
            seen.add(phrase)

    # Single-word matches via word boundary regex
    words = re.findall(r"[a-zA-Z&]+(?:'[a-zA-Z]+)?", text_lower)
    for word in words:
        if word in _STOP_WORDS or len(word) < 2:
            continue
        if word in _KNOWN_ENTITIES and word not in seen:
            found.append((word.title(), _KNOWN_ENTITIES[word]))
            seen.add(word)

    # Event keyword detection
    for event_kw in _EVENT_KEYWORDS:
        if event_kw in text_lower and event_kw not in seen:
            found.append((event_kw.title(), "EVENT"))
            seen.add(event_kw)

    return found


# ---------------------------------------------------------------------------
# KnowledgeGraph singleton
# ---------------------------------------------------------------------------

class KnowledgeGraph:
    """Thread-safe in-memory knowledge graph (singleton)."""

    _instance: KnowledgeGraph | None = None
    _init_lock = threading.Lock()

    def __new__(cls) -> KnowledgeGraph:
        with cls._init_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._nodes: dict[str, GraphNode] = {}
                instance._edges: dict[tuple[str, str, str], GraphEdge] = {}
                instance._adjacency: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
                instance._lock = threading.Lock()
                cls._instance = instance
            return cls._instance

    # -- Mutators -----------------------------------------------------------

    def add_entity(
        self,
        name: str,
        entity_type: str,
        attributes: dict | None = None,
    ) -> GraphNode:
        """Upsert an entity node. Increments mention_count on repeat calls."""
        key = _normalize(name)
        now = datetime.utcnow()
        with self._lock:
            if key in self._nodes:
                node = self._nodes[key]
                node.mention_count += 1
                node.last_seen = now
                if attributes:
                    node.attributes.update(attributes)
            else:
                node = GraphNode(
                    name=name,
                    entity_type=entity_type,
                    attributes=attributes or {},
                    first_seen=now,
                    last_seen=now,
                    mention_count=1,
                )
                self._nodes[key] = node
        return node

    def add_relationship(
        self,
        source: str,
        target: str,
        relation_type: str,
        evidence_text: str = "",
    ) -> GraphEdge:
        """Upsert a directed edge. Increments weight and appends evidence."""
        src_key = _normalize(source)
        tgt_key = _normalize(target)
        edge_key = (src_key, tgt_key, relation_type.upper())
        now = datetime.utcnow()
        with self._lock:
            if edge_key in self._edges:
                edge = self._edges[edge_key]
                edge.weight += 1.0
                edge.last_seen = now
                if evidence_text and evidence_text not in edge.evidence:
                    edge.evidence.append(evidence_text)
            else:
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relation_type=relation_type.upper(),
                    weight=1.0,
                    first_seen=now,
                    last_seen=now,
                    evidence=[evidence_text] if evidence_text else [],
                )
                self._edges[edge_key] = edge
                self._adjacency[src_key].add(edge_key)
                self._adjacency[tgt_key].add(edge_key)
        return edge

    def ingest_scored_news(self, scored_articles: list[dict]) -> dict:
        """Extract entities and relationships from scored news articles.

        Each article dict is expected to have (at minimum):
            - title: str
            - affected_markets: list[str]
            - sentiment: str  ('bullish' | 'bearish' | 'neutral')

        Optional fields used when present:
            - impact_score, headline_summary, impact_reasoning, source

        Returns a summary dict with counts of entities and relationships added.
        """
        entities_added = 0
        relationships_added = 0

        for article in scored_articles:
            title = article.get("title", "")
            summary = article.get("headline_summary", title)
            reasoning = article.get("impact_reasoning", "")
            sentiment = article.get("sentiment", "neutral")
            impact = article.get("impact_score", 0)
            affected_markets = article.get("affected_markets", [])
            source = article.get("source", "")

            # -- Extract entities from title + reasoning --
            combined_text = f"{title} {reasoning}"
            extracted = _extract_entities_from_text(combined_text)

            for ename, etype in extracted:
                attrs: dict = {}
                if sentiment:
                    attrs["last_sentiment"] = sentiment
                if impact:
                    attrs["last_impact_score"] = impact
                self.add_entity(ename, etype, attributes=attrs)
                entities_added += 1

            # -- affected_markets become SECTOR / INDEX entities --
            for market in affected_markets:
                self.add_entity(market, "SECTOR", {"source": "affected_markets"})
                entities_added += 1

            # -- Build relationships --
            evidence_snippet = summary[:200] if summary else title[:200]

            # Every extracted entity AFFECTS each affected market
            for ename, _etype in extracted:
                for market in affected_markets:
                    self.add_relationship(
                        ename, market, "AFFECTS", evidence_snippet,
                    )
                    relationships_added += 1

            # Co-occurrence: entities that appear in the same headline are RELATED
            for i, (e1_name, _) in enumerate(extracted):
                for e2_name, _ in extracted[i + 1:]:
                    self.add_relationship(
                        e1_name, e2_name, "RELATED_TO", evidence_snippet,
                    )
                    relationships_added += 1

            # Sentiment-based relationships
            if sentiment == "bearish":
                for market in affected_markets:
                    self.add_relationship(
                        title[:80], market, "PRESSURES", evidence_snippet,
                    )
                    # Treat the headline as a transient event entity
                    self.add_entity(title[:80], "EVENT", {"sentiment": "bearish"})
                    relationships_added += 1
                    entities_added += 1
            elif sentiment == "bullish":
                for market in affected_markets:
                    self.add_relationship(
                        title[:80], market, "SUPPORTS", evidence_snippet,
                    )
                    self.add_entity(title[:80], "EVENT", {"sentiment": "bullish"})
                    relationships_added += 1
                    entities_added += 1

        logger.info(
            "Knowledge graph ingested %d articles -> %d entities, %d relationships",
            len(scored_articles), entities_added, relationships_added,
        )
        return {
            "articles_processed": len(scored_articles),
            "entities_added": entities_added,
            "relationships_added": relationships_added,
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
        }

    # -- Queries ------------------------------------------------------------

    def get_entity(self, name: str) -> GraphNode | None:
        """Look up a node by name (case-insensitive)."""
        with self._lock:
            return self._nodes.get(_normalize(name))

    def get_relationships(self, entity_name: str) -> list[GraphEdge]:
        """Return all edges involving *entity_name* (as source or target)."""
        key = _normalize(entity_name)
        with self._lock:
            edge_keys = self._adjacency.get(key, set())
            return [self._edges[ek] for ek in edge_keys if ek in self._edges]

    def get_most_connected(self, n: int = 10) -> list[tuple[GraphNode, int]]:
        """Return top *n* entities ranked by total connection count."""
        with self._lock:
            counts: dict[str, int] = {}
            for key, edge_keys in self._adjacency.items():
                counts[key] = len(edge_keys)
            sorted_keys = sorted(counts, key=counts.get, reverse=True)[:n]  # type: ignore[arg-type]
            return [
                (self._nodes[k], counts[k])
                for k in sorted_keys
                if k in self._nodes
            ]

    def get_impact_chain(self, entity_name: str) -> dict:
        """Trace relationships two levels deep from *entity_name*.

        Returns::

            {
                "root": "entity_name",
                "level_1": [
                    {
                        "entity": "...",
                        "relation": "AFFECTS",
                        "weight": 3.0,
                        "level_2": [
                            {"entity": "...", "relation": "...", "weight": ...},
                            ...
                        ]
                    },
                    ...
                ]
            }
        """
        root_key = _normalize(entity_name)
        result: dict = {"root": entity_name, "level_1": []}

        with self._lock:
            if root_key not in self._nodes:
                return result

            # Level 1 neighbours
            level_1_edge_keys = self._adjacency.get(root_key, set())
            visited: set[str] = {root_key}

            for ek in level_1_edge_keys:
                edge = self._edges.get(ek)
                if edge is None:
                    continue
                # Determine the "other" end of the edge
                other_key = (
                    _normalize(edge.target)
                    if _normalize(edge.source) == root_key
                    else _normalize(edge.source)
                )
                if other_key in visited:
                    continue
                visited.add(other_key)

                other_node = self._nodes.get(other_key)
                if other_node is None:
                    continue

                l1_entry: dict = {
                    "entity": other_node.name,
                    "entity_type": other_node.entity_type,
                    "relation": edge.relation_type,
                    "weight": edge.weight,
                    "level_2": [],
                }

                # Level 2 neighbours
                level_2_edge_keys = self._adjacency.get(other_key, set())
                for ek2 in level_2_edge_keys:
                    edge2 = self._edges.get(ek2)
                    if edge2 is None:
                        continue
                    other2_key = (
                        _normalize(edge2.target)
                        if _normalize(edge2.source) == other_key
                        else _normalize(edge2.source)
                    )
                    if other2_key in visited:
                        continue
                    visited.add(other2_key)
                    other2_node = self._nodes.get(other2_key)
                    if other2_node is None:
                        continue
                    l1_entry["level_2"].append({
                        "entity": other2_node.name,
                        "entity_type": other2_node.entity_type,
                        "relation": edge2.relation_type,
                        "weight": edge2.weight,
                    })

                result["level_1"].append(l1_entry)

        # Sort level 1 by weight descending
        result["level_1"].sort(key=lambda x: x["weight"], reverse=True)
        for l1 in result["level_1"]:
            l1["level_2"].sort(key=lambda x: x["weight"], reverse=True)

        return result

    def get_graph_summary(self) -> dict:
        """High-level summary of the current graph state."""
        with self._lock:
            node_count = len(self._nodes)
            edge_count = len(self._edges)

            # Top entities by mention count
            top_by_mentions = sorted(
                self._nodes.values(),
                key=lambda n: n.mention_count,
                reverse=True,
            )[:10]

            # Recent entities (last seen)
            recent = sorted(
                self._nodes.values(),
                key=lambda n: n.last_seen,
                reverse=True,
            )[:10]

            # Top entities by connectivity
            connectivity: dict[str, int] = {
                k: len(v) for k, v in self._adjacency.items()
            }
            top_connected_keys = sorted(
                connectivity, key=connectivity.get, reverse=True,  # type: ignore[arg-type]
            )[:10]

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "top_entities_by_mentions": [
                {
                    "name": n.name,
                    "type": n.entity_type,
                    "mentions": n.mention_count,
                }
                for n in top_by_mentions
            ],
            "top_entities_by_connections": [
                {
                    "name": self._nodes[k].name if k in self._nodes else k,
                    "connections": connectivity.get(k, 0),
                }
                for k in top_connected_keys
                if k in self._nodes
            ],
            "recent_entities": [
                {
                    "name": n.name,
                    "type": n.entity_type,
                    "last_seen": n.last_seen.isoformat(),
                }
                for n in recent
            ],
        }

    # -- Utilities ----------------------------------------------------------

    def clear(self) -> None:
        """Reset the graph (useful for testing)."""
        with self._lock:
            self._nodes.clear()
            self._edges.clear()
            self._adjacency.clear()

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(nodes={len(self._nodes)}, edges={len(self._edges)})"
        )
