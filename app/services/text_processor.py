from __future__ import annotations

"""Text processing utilities for the predictions platform.

Provides chunking, key-sentence extraction, and context summarisation
optimised for feeding financial news into LLM prompts.
"""

import re
from datetime import datetime

from app.models.domain import Article

# ---------------------------------------------------------------------------
# Financial keyword lexicon
# ---------------------------------------------------------------------------

FINANCIAL_KEYWORDS: list[str] = [
    # Monetary policy
    "fed", "federal reserve", "rate", "interest rate", "rate hike", "rate cut",
    "monetary policy", "quantitative easing", "tightening", "dovish", "hawkish",
    "central bank", "ecb", "boj",
    # Economic indicators
    "inflation", "cpi", "ppi", "gdp", "unemployment", "nonfarm", "payroll",
    "jobs", "housing", "retail sales", "consumer confidence", "pmi",
    # Earnings / corporate
    "earnings", "revenue", "profit", "loss", "guidance", "forecast",
    "beat", "miss", "eps", "dividend", "buyback", "ipo", "merger",
    "acquisition", "bankruptcy", "restructuring",
    # Trade & geopolitics
    "trade", "tariff", "sanctions", "embargo", "export", "import",
    "trade war", "trade deal", "supply chain",
    # Geopolitical / conflict
    "war", "invasion", "conflict", "ceasefire", "nato", "military",
    "nuclear", "missile", "escalation", "tensions",
    # Commodities / energy
    "oil", "crude", "brent", "wti", "natural gas", "opec",
    "gold", "silver", "copper", "lithium", "commodities",
    # Risk / crisis
    "recession", "crisis", "default", "collapse", "crash", "volatility",
    "bear market", "correction", "bubble", "contagion", "systemic",
    # Regions (contextually significant)
    "china", "russia", "ukraine", "europe", "asia", "emerging markets",
    # Crypto (increasingly relevant)
    "bitcoin", "crypto", "stablecoin",
    # Fiscal policy
    "stimulus", "spending", "debt ceiling", "deficit", "treasury",
    "bond", "yield", "yield curve",
]

# Pre-compile a set of lower-cased keywords for fast membership checks, plus
# individual words for single-token matching.
_KEYWORD_SET: set[str] = {kw.lower() for kw in FINANCIAL_KEYWORDS}
_KEYWORD_SINGLES: set[str] = set()
for _kw in FINANCIAL_KEYWORDS:
    for _w in _kw.lower().split():
        if len(_w) >= 3:
            _KEYWORD_SINGLES.add(_w)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split *text* into overlapping chunks of roughly *chunk_size* characters.

    Splits prefer sentence boundaries when possible so that chunks remain
    coherent.  The *overlap* parameter controls how many characters from the
    end of the previous chunk are repeated at the start of the next.

    Returns an empty list for blank input.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If the whole text fits in one chunk, return it directly.
    if len(text) <= chunk_size:
        return [text]

    # Split into sentences first for cleaner boundaries.
    sentences = _split_sentences(text)

    chunks: list[str] = []
    current_chunk = ""

    for sentence in sentences:
        # If adding the next sentence would exceed chunk_size, finalise chunk.
        if current_chunk and len(current_chunk) + len(sentence) + 1 > chunk_size:
            chunks.append(current_chunk.strip())
            # Start next chunk with overlap from the end of the previous one.
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + " " + sentence
            else:
                current_chunk = sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence

    # Don't forget the last chunk.
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def extract_key_sentences(text: str, max_sentences: int = 5) -> list[str]:
    """Return up to *max_sentences* sentences ranked by financial keyword density.

    Sentences are returned in their original document order so that the
    output reads naturally.
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)
    if not sentences:
        return []

    scored: list[tuple[int, float, str]] = []  # (original_index, score, text)
    for idx, sent in enumerate(sentences):
        score = _score_sentence(sent)
        scored.append((idx, score, sent))

    # Sort by score descending, pick top N
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:max_sentences]

    # Re-sort by original position so the output reads in order
    top.sort(key=lambda x: x[0])
    return [s[2] for s in top]


def summarize_for_context(
    articles: list[Article],
    max_chars: int = 3000,
) -> str:
    """Build a compact context string from a list of Article objects.

    The result is designed to be injected directly into an LLM prompt.
    Articles are sorted by recency, and each one is truncated so the total
    stays within *max_chars*.

    Format per article::

        [SOURCE | CATEGORY] Title
        Key sentences...
        ---
    """
    if not articles:
        return ""

    # Sort newest first
    sorted_articles = sorted(
        articles,
        key=lambda a: a.published or datetime.min,
        reverse=True,
    )

    # Budget per article (leave room for separators)
    separator = "\n---\n"
    sep_budget = len(separator) * len(sorted_articles)
    available = max(max_chars - sep_budget, len(sorted_articles) * 100)
    per_article = max(available // len(sorted_articles), 100)

    parts: list[str] = []
    chars_used = 0

    for article in sorted_articles:
        header = f"[{article.source} | {article.category}] {article.title}"

        # Extract key sentences from the article body
        key_sents = extract_key_sentences(article.text, max_sentences=3)
        body = " ".join(key_sents) if key_sents else article.text[:per_article]

        # Truncate body to fit per-article budget
        body_budget = per_article - len(header) - 1  # -1 for newline
        if body_budget > 0:
            body = body[:body_budget]
        else:
            body = ""

        block = f"{header}\n{body}" if body else header

        # Check if adding this block would exceed total budget
        if chars_used + len(block) + len(separator) > max_chars:
            # Try to fit a truncated version
            remaining = max_chars - chars_used - len(separator)
            if remaining > 80:
                parts.append(block[:remaining])
            break

        parts.append(block)
        chars_used += len(block) + len(separator)

    return separator.join(parts)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z"])|(?<=[.!?])$',
)


def _split_sentences(text: str) -> list[str]:
    """Heuristic sentence splitter that handles common abbreviations."""
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Split on sentence-ending punctuation followed by a space + capital letter
    raw = _SENTENCE_RE.split(text)
    sentences = [s.strip() for s in raw if s and s.strip()]
    return sentences


def _score_sentence(sentence: str) -> float:
    """Score a sentence by financial keyword density.

    The score is the number of keyword hits normalised by sentence length
    (in words) to avoid penalising short but keyword-dense sentences.
    """
    lower = sentence.lower()
    hits = 0

    # Check multi-word keywords first
    for kw in _KEYWORD_SET:
        if " " in kw and kw in lower:
            hits += 2  # multi-word match is worth more

    # Single-word matches
    words = re.findall(r"[a-z]+", lower)
    for w in words:
        if w in _KEYWORD_SINGLES:
            hits += 1

    # Normalise: keywords per word, but give a small bonus to longer sentences
    # so that a 3-word sentence with 1 keyword doesn't always beat a 20-word
    # sentence with 5 keywords.
    word_count = max(len(words), 1)
    density = hits / word_count
    length_bonus = min(word_count / 20.0, 1.0)  # caps at 1.0 for 20+ words

    return hits + density + length_bonus
