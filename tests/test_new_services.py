"""Tests for new services: trading_signals, fear_greed, scenario_engine,
knowledge_graph, action_logger, personas, and text_processor.

All tests use sample data and avoid external API calls.
"""

import math

import pytest


# ---------------------------------------------------------------------------
# Sample price data (50 floats with a gentle upward trend + noise)
# ---------------------------------------------------------------------------

SAMPLE_PRICES: list[float] = [
    100.0, 101.5, 99.8, 102.3, 103.1, 101.0, 104.2, 105.0, 103.5, 106.1,
    107.0, 105.5, 108.2, 109.0, 107.8, 110.5, 111.0, 109.5, 112.0, 113.2,
    111.8, 114.0, 115.5, 113.0, 116.2, 117.0, 115.8, 118.0, 119.5, 117.5,
    120.0, 121.0, 119.0, 122.5, 123.0, 121.5, 124.0, 125.5, 123.8, 126.0,
    127.0, 125.0, 128.5, 129.0, 127.5, 130.0, 131.5, 129.8, 132.0, 133.0,
]


# ===================================================================
# 1. RSI computation with known values
# ===================================================================

class TestRSI:
    def test_rsi_returns_list_of_correct_length(self):
        from app.services.trading_signals import compute_rsi

        result = compute_rsi(SAMPLE_PRICES, period=14)
        assert isinstance(result, list)
        assert len(result) == len(SAMPLE_PRICES)

    def test_rsi_warmup_values_are_nan(self):
        from app.services.trading_signals import compute_rsi

        result = compute_rsi(SAMPLE_PRICES, period=14)
        # First 14 entries (indices 0-13) should be NaN
        for i in range(14):
            assert math.isnan(result[i]), f"Expected NaN at index {i}"

    def test_rsi_values_in_valid_range(self):
        from app.services.trading_signals import compute_rsi

        result = compute_rsi(SAMPLE_PRICES, period=14)
        for i in range(14, len(result)):
            assert not math.isnan(result[i]), f"Unexpected NaN at index {i}"
            assert 0 <= result[i] <= 100, f"RSI out of range at index {i}: {result[i]}"

    def test_rsi_too_few_prices_returns_all_nan(self):
        from app.services.trading_signals import compute_rsi

        result = compute_rsi([100.0, 101.0, 99.0], period=14)
        assert all(math.isnan(v) for v in result)

    def test_rsi_uptrend_above_50(self):
        """A monotonically rising series should have RSI well above 50."""
        from app.services.trading_signals import compute_rsi

        rising = [100.0 + i * 1.0 for i in range(30)]
        result = compute_rsi(rising, period=14)
        # The final RSI should be high (all gains, no losses)
        assert result[-1] > 80


# ===================================================================
# 2. MACD computation returns correct keys
# ===================================================================

class TestMACD:
    def test_macd_returns_required_keys(self):
        from app.services.trading_signals import compute_macd

        result = compute_macd(SAMPLE_PRICES)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result

    def test_macd_lists_correct_length(self):
        from app.services.trading_signals import compute_macd

        result = compute_macd(SAMPLE_PRICES)
        for key in ("macd", "signal", "histogram"):
            assert len(result[key]) == len(SAMPLE_PRICES)


# ===================================================================
# 3. Bollinger bands contain upper/middle/lower
# ===================================================================

class TestBollinger:
    def test_bollinger_returns_required_keys(self):
        from app.services.trading_signals import compute_bollinger

        result = compute_bollinger(SAMPLE_PRICES)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result

    def test_bollinger_band_ordering(self):
        """Where values are not NaN, upper >= middle >= lower."""
        from app.services.trading_signals import compute_bollinger

        result = compute_bollinger(SAMPLE_PRICES, period=20)
        for i in range(len(SAMPLE_PRICES)):
            u, m, lo = result["upper"][i], result["middle"][i], result["lower"][i]
            if not (math.isnan(u) or math.isnan(m) or math.isnan(lo)):
                assert u >= m >= lo, f"Band ordering violated at index {i}"


# ===================================================================
# 4. Trading summary has all required fields
# ===================================================================

class TestTradingSummary:
    def test_summary_has_required_fields(self):
        from app.services.trading_signals import generate_trading_summary

        summary = generate_trading_summary(SAMPLE_PRICES)
        assert "current_price" in summary
        assert "trend" in summary
        assert "rsi_value" in summary
        assert "overall_bias" in summary
        assert "suggested_action" in summary

    def test_summary_current_price_matches_last(self):
        from app.services.trading_signals import generate_trading_summary

        summary = generate_trading_summary(SAMPLE_PRICES)
        assert summary["current_price"] == SAMPLE_PRICES[-1]

    def test_summary_trend_is_valid_value(self):
        from app.services.trading_signals import generate_trading_summary

        summary = generate_trading_summary(SAMPLE_PRICES)
        assert summary["trend"] in ("up", "down", "sideways")

    def test_summary_suggested_action_has_action_key(self):
        from app.services.trading_signals import generate_trading_summary

        summary = generate_trading_summary(SAMPLE_PRICES)
        action = summary["suggested_action"]
        assert "action" in action
        assert action["action"] in ("BUY", "SELL", "HOLD")

    def test_summary_with_minimal_prices(self):
        from app.services.trading_signals import generate_trading_summary

        summary = generate_trading_summary([100.0])
        assert summary["current_price"] == 100.0
        assert summary["trend"] == "sideways"


# ===================================================================
# 5. detect_signals returns list with proper structure
# ===================================================================

class TestDetectSignals:
    def test_returns_list(self):
        from app.services.trading_signals import detect_signals

        result = detect_signals(SAMPLE_PRICES)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_signal_has_required_keys(self):
        from app.services.trading_signals import detect_signals

        result = detect_signals(SAMPLE_PRICES)
        required_keys = {"type", "signal_name", "strength", "price_at_signal", "reasoning"}
        for signal in result:
            assert required_keys.issubset(signal.keys()), (
                f"Missing keys: {required_keys - signal.keys()}"
            )

    def test_signal_type_is_valid(self):
        from app.services.trading_signals import detect_signals

        result = detect_signals(SAMPLE_PRICES)
        valid_types = {"BUY", "SELL", "HOLD"}
        for signal in result:
            assert signal["type"] in valid_types

    def test_empty_prices_returns_empty(self):
        from app.services.trading_signals import detect_signals

        assert detect_signals([]) == []
        assert detect_signals([100.0]) == []


# ===================================================================
# 6. fear_greed computation returns score 0-100 with label
# ===================================================================

class TestFearGreed:
    def test_returns_score_and_label(self):
        from app.services.fear_greed import compute_fear_greed

        market_data = [
            {"current_price": 100, "previous_close": 98, "change_pct": 2.0},
            {"current_price": 50, "previous_close": 52, "change_pct": -3.8},
        ]
        news = {"bullish_pct": 40, "bearish_pct": 30, "neutral_pct": 30}

        result = compute_fear_greed(market_data, news)
        assert "score" in result
        assert "label" in result
        assert 0 <= result["score"] <= 100

    def test_label_is_valid(self):
        from app.services.fear_greed import compute_fear_greed

        market_data = [
            {"current_price": 100, "previous_close": 95, "change_pct": 5.0},
        ]
        news = {"bullish_pct": 80, "bearish_pct": 10, "neutral_pct": 10}
        result = compute_fear_greed(market_data, news)
        valid_labels = {"Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"}
        assert result["label"] in valid_labels

    def test_components_present(self):
        from app.services.fear_greed import compute_fear_greed

        market_data = [
            {"current_price": 100, "previous_close": 100, "change_pct": 0.0},
        ]
        news = {"bullish_pct": 33, "bearish_pct": 33, "neutral_pct": 34}
        result = compute_fear_greed(market_data, news)
        assert "components" in result
        assert isinstance(result["components"], dict)

    def test_extreme_fear_scenario(self):
        from app.services.fear_greed import compute_fear_greed

        market_data = [
            {"current_price": 80, "previous_close": 100, "change_pct": -20.0},
            {"current_price": 70, "previous_close": 100, "change_pct": -30.0},
        ]
        news = {"bullish_pct": 5, "bearish_pct": 90, "neutral_pct": 5}
        result = compute_fear_greed(market_data, news)
        assert result["score"] < 40  # should be fearful


# ===================================================================
# 7. get_preset_scenarios returns non-empty list
# ===================================================================

class TestPresetScenarios:
    def test_returns_non_empty_list(self):
        from app.services.scenario_engine import get_preset_scenarios

        scenarios = get_preset_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0

    def test_each_scenario_has_id_and_description(self):
        from app.services.scenario_engine import get_preset_scenarios

        for s in get_preset_scenarios():
            assert "id" in s
            assert "description" in s
            assert "category" in s

    def test_returns_copies(self):
        """Modifying returned list should not affect internal data."""
        from app.services.scenario_engine import get_preset_scenarios

        s1 = get_preset_scenarios()
        s1.pop()
        s2 = get_preset_scenarios()
        assert len(s2) > len(s1)


# ===================================================================
# 8. Heuristic scenario fallback works
# ===================================================================

class TestScenarioFallback:
    def test_known_keyword_triggers_heuristic(self):
        from app.services.scenario_engine import _fallback_scenario

        result = _fallback_scenario("Fed raises rates by 50 bps")
        assert "scenario" in result
        assert "market_impacts" in result
        assert len(result["market_impacts"]) > 0
        assert "risk_level" in result

    def test_unknown_scenario_returns_generic(self):
        from app.services.scenario_engine import _fallback_scenario

        result = _fallback_scenario("Aliens land on Earth")
        assert result["scenario"] == "Aliens land on Earth"
        assert result["probability"] == 0.5
        assert len(result["market_impacts"]) >= 1

    def test_tariff_keyword_match(self):
        from app.services.scenario_engine import _fallback_scenario

        result = _fallback_scenario("Trump tariff on China escalation")
        assert result["risk_level"] in ("low", "medium", "high", "extreme")
        assert len(result["recommended_actions"]) > 0

    def test_fallback_has_all_required_keys(self):
        from app.services.scenario_engine import _fallback_scenario

        result = _fallback_scenario("Oil supply shock due to OPEC cuts")
        required = {
            "scenario", "probability", "market_impacts", "forex_impacts",
            "crypto_impacts", "chain_effects", "recommended_actions", "risk_level",
        }
        assert required.issubset(result.keys())


# ===================================================================
# 9. Knowledge graph add_entity and get_entity
# ===================================================================

class TestKnowledgeGraphEntities:
    def setup_method(self):
        from app.services.knowledge_graph import KnowledgeGraph
        self.kg = KnowledgeGraph()
        self.kg.clear()

    def test_add_and_get_entity(self):
        self.kg.add_entity("Apple", "COMPANY", {"sector": "tech"})
        node = self.kg.get_entity("Apple")
        assert node is not None
        assert node.name == "Apple"
        assert node.entity_type == "COMPANY"
        assert node.attributes["sector"] == "tech"
        assert node.mention_count == 1

    def test_upsert_increments_mention_count(self):
        self.kg.add_entity("Tesla", "COMPANY")
        self.kg.add_entity("Tesla", "COMPANY")
        self.kg.add_entity("Tesla", "COMPANY")
        node = self.kg.get_entity("Tesla")
        assert node is not None
        assert node.mention_count == 3

    def test_get_entity_case_insensitive(self):
        self.kg.add_entity("NVIDIA", "COMPANY")
        assert self.kg.get_entity("nvidia") is not None
        assert self.kg.get_entity("Nvidia") is not None

    def test_get_nonexistent_entity_returns_none(self):
        assert self.kg.get_entity("Nonexistent") is None


# ===================================================================
# 10. Knowledge graph add_relationship and get_relationships
# ===================================================================

class TestKnowledgeGraphRelationships:
    def setup_method(self):
        from app.services.knowledge_graph import KnowledgeGraph
        self.kg = KnowledgeGraph()
        self.kg.clear()

    def test_add_and_get_relationship(self):
        self.kg.add_entity("Fed", "INSTITUTION")
        self.kg.add_entity("S&P 500", "INDEX")
        self.kg.add_relationship("Fed", "S&P 500", "AFFECTS", "Rate hike impacts equities")

        rels = self.kg.get_relationships("Fed")
        assert len(rels) >= 1
        edge = rels[0]
        assert edge.source == "Fed"
        assert edge.target == "S&P 500"
        assert edge.relation_type == "AFFECTS"
        assert "Rate hike impacts equities" in edge.evidence

    def test_relationship_weight_increments(self):
        self.kg.add_entity("Oil", "COMMODITY")
        self.kg.add_entity("Energy", "SECTOR")
        self.kg.add_relationship("Oil", "Energy", "AFFECTS", "evidence 1")
        self.kg.add_relationship("Oil", "Energy", "AFFECTS", "evidence 2")

        rels = self.kg.get_relationships("Oil")
        affects_edges = [r for r in rels if r.relation_type == "AFFECTS"]
        assert len(affects_edges) == 1
        assert affects_edges[0].weight == 2.0
        assert len(affects_edges[0].evidence) == 2

    def test_get_relationships_for_target(self):
        """get_relationships returns edges for both source and target."""
        self.kg.add_entity("China", "COUNTRY")
        self.kg.add_entity("Gold", "COMMODITY")
        self.kg.add_relationship("China", "Gold", "AFFECTS")

        rels = self.kg.get_relationships("Gold")
        assert len(rels) >= 1


# ===================================================================
# 11. Action logger log_action and get_audit_trail
# ===================================================================

class TestActionLogger:
    def setup_method(self):
        from app.services.action_logger import ActionLogger
        self.logger = ActionLogger()
        self.logger.clear()

    def test_log_action_returns_entry(self):
        from app.services.action_logger import ActionType

        entry = self.logger.log_action(
            agent_name="momentum_trader",
            action_type=ActionType.PREDICTION,
            details={"direction": "up", "confidence": 0.8},
            result="BTC predicted to rise",
            asset_id="BTC",
        )
        assert entry.agent_name == "momentum_trader"
        assert entry.action_type == "PREDICTION"
        assert entry.asset_id == "BTC"

    def test_get_audit_trail(self):
        self.logger.log_action("agent_a", "THOUGHT", {"note": "analyzing"}, "ok", asset_id="ETH")
        self.logger.log_action("agent_b", "PREDICTION", {"dir": "up"}, "bullish", asset_id="ETH")
        self.logger.log_action("agent_a", "THOUGHT", {"note": "other"}, "ok", asset_id="BTC")

        trail = self.logger.get_audit_trail("ETH")
        assert len(trail) == 2
        assert all(e.asset_id == "ETH" for e in trail)

    def test_audit_trail_empty_for_unknown_asset(self):
        trail = self.logger.get_audit_trail("UNKNOWN")
        assert trail == []

    def test_size_property(self):
        assert self.logger.size == 0
        self.logger.log_action("a", "THOUGHT", {}, "r", asset_id="X")
        assert self.logger.size == 1


# ===================================================================
# 12. Persona get_weighted_consensus
# ===================================================================

class TestWeightedConsensus:
    def test_empty_predictions_returns_neutral(self):
        from app.agents.personas import get_weighted_consensus

        result = get_weighted_consensus([])
        assert result["direction"] == "neutral"
        assert result["confidence"] == 0

    def test_bullish_consensus(self):
        from app.agents.personas import get_weighted_consensus

        predictions = [
            {"persona_id": "momentum_trader", "direction": "up", "confidence": 0.9, "target_mid": 150},
            {"persona_id": "value_investor", "direction": "up", "confidence": 0.8, "target_mid": 145},
            {"persona_id": "macro_strategist", "direction": "up", "confidence": 0.7, "target_mid": 148},
        ]
        result = get_weighted_consensus(predictions)
        assert result["direction"] == "up"
        assert result["confidence"] > 0
        assert result["target_mid"] > 0
        assert result["persona_count"] == 3

    def test_bearish_consensus(self):
        from app.agents.personas import get_weighted_consensus

        predictions = [
            {"persona_id": "risk_manager", "direction": "down", "confidence": 0.9, "target_mid": 90},
            {"persona_id": "geopolitical_analyst", "direction": "down", "confidence": 0.85, "target_mid": 88},
            {"persona_id": "quant_analyst", "direction": "down", "confidence": 0.8, "target_mid": 91},
        ]
        result = get_weighted_consensus(predictions)
        assert result["direction"] == "down"

    def test_mixed_predictions_may_yield_sideways(self):
        from app.agents.personas import get_weighted_consensus

        predictions = [
            {"persona_id": "momentum_trader", "direction": "up", "confidence": 0.7, "target_mid": 110},
            {"persona_id": "risk_manager", "direction": "down", "confidence": 0.7, "target_mid": 90},
        ]
        result = get_weighted_consensus(predictions)
        # With roughly equal weights and confidence, result could be sideways
        assert result["direction"] in ("up", "down", "sideways")
        assert "bullish_weight" in result
        assert "bearish_weight" in result
        assert "agreement_score" in result


# ===================================================================
# 13. text_processor chunk_text returns proper chunks
# ===================================================================

class TestChunkText:
    def test_short_text_single_chunk(self):
        from app.services.text_processor import chunk_text

        text = "This is a short sentence."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_multiple_chunks(self):
        from app.services.text_processor import chunk_text

        # Build a text longer than 500 chars
        text = "The Federal Reserve raised interest rates. " * 30
        chunks = chunk_text(text, chunk_size=200, overlap=30)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) > 0

    def test_empty_text_returns_empty_list(self):
        from app.services.text_processor import chunk_text

        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunks_cover_full_text(self):
        """All content from the original text should appear in at least one chunk."""
        from app.services.text_processor import chunk_text

        sentences = [
            "Apple reported record earnings.",
            "The Fed raised rates by 25bps.",
            "Oil prices surged on OPEC cuts.",
            "Gold hit new highs amid uncertainty.",
            "Tech stocks rallied on AI optimism.",
        ]
        text = " ".join(sentences)
        chunks = chunk_text(text, chunk_size=80, overlap=10)
        combined = " ".join(chunks)
        # Each sentence should appear somewhere in the combined output
        for sentence in sentences:
            assert sentence in combined, f"Missing sentence: {sentence}"

    def test_overlap_creates_repeated_content(self):
        from app.services.text_processor import chunk_text

        text = "First sentence here. Second sentence here. Third sentence here. Fourth one now."
        chunks = chunk_text(text, chunk_size=40, overlap=10)
        if len(chunks) >= 2:
            # With overlap, the end of chunk N should appear at the start of chunk N+1
            # (at least partially)
            tail = chunks[0][-10:]
            assert tail in chunks[1], "Expected overlap content in next chunk"
