"""Market data fetching for stock indices, forex pairs, and crypto.

Uses free APIs (Yahoo Finance chart API, CoinGecko, Deribit) to get
historical and current market data without heavy dependencies.
"""

import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# Major stock indices with Yahoo Finance tickers
STOCK_INDICES = {
    "sp500": {"ticker": "^GSPC", "name": "S&P 500", "country": "US", "currency": "USD"},
    "nasdaq": {"ticker": "^IXIC", "name": "NASDAQ", "country": "US", "currency": "USD"},
    "dow": {"ticker": "^DJI", "name": "Dow Jones", "country": "US", "currency": "USD"},
    "kospi": {"ticker": "^KS11", "name": "KOSPI", "country": "KR", "currency": "KRW"},
    "shanghai": {"ticker": "000001.SS", "name": "Shanghai Composite", "country": "CN", "currency": "CNY"},
    "nikkei": {"ticker": "^N225", "name": "Nikkei 225", "country": "JP", "currency": "JPY"},
    "ftse": {"ticker": "^FTSE", "name": "FTSE 100", "country": "UK", "currency": "GBP"},
    "dax": {"ticker": "^GDAXI", "name": "DAX", "country": "DE", "currency": "EUR"},
    "eurostoxx": {"ticker": "^STOXX50E", "name": "Euro Stoxx 50", "country": "EU", "currency": "EUR"},
}

# Major forex pairs
FOREX_PAIRS = {
    "usd_krw": {"ticker": "KRW=X", "name": "USD/KRW", "base": "USD", "quote": "KRW"},
    "usd_cny": {"ticker": "CNY=X", "name": "USD/CNY", "base": "USD", "quote": "CNY"},
    "usd_jpy": {"ticker": "JPY=X", "name": "USD/JPY", "base": "USD", "quote": "JPY"},
    "eur_usd": {"ticker": "EURUSD=X", "name": "EUR/USD", "base": "EUR", "quote": "USD"},
    "gbp_usd": {"ticker": "GBPUSD=X", "name": "GBP/USD", "base": "GBP", "quote": "USD"},
}

# Crypto assets
CRYPTO_ASSETS = {
    "btc": {"id": "bitcoin", "ticker": "BTC-USD", "name": "Bitcoin", "symbol": "BTC"},
    "eth": {"id": "ethereum", "ticker": "ETH-USD", "name": "Ethereum", "symbol": "ETH"},
}

# Period mapping for Yahoo Finance API
PERIOD_MAP = {
    "1w": {"range": "5d", "interval": "1h"},
    "1m": {"range": "1mo", "interval": "1d"},
    "3m": {"range": "3mo", "interval": "1d"},
    "1y": {"range": "1y", "interval": "1wk"},
    "5y": {"range": "5y", "interval": "1mo"},
}

# CoinGecko period mapping
CRYPTO_PERIOD_MAP = {
    "1w": {"days": "7"},
    "1m": {"days": "30"},
    "3m": {"days": "90"},
    "1y": {"days": "365"},
    "5y": {"days": "max"},
}


# ── Yahoo Finance ────────────────────────────────────────────────────

def _fetch_yahoo_chart(ticker: str, period: str = "1m") -> dict:
    """Fetch chart data from Yahoo Finance's public chart API."""
    params = PERIOD_MAP.get(period, PERIOD_MAP["1m"])
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(
            url,
            params={"range": params["range"], "interval": params["interval"]},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [])
        if not result:
            return {"timestamps": [], "prices": [], "error": "No data available"}

        chart = result[0]
        timestamps = chart.get("timestamp", [])
        indicators = chart.get("indicators", {}).get("quote", [{}])[0]
        closes = indicators.get("close", [])
        opens = indicators.get("open", [])
        highs = indicators.get("high", [])
        lows = indicators.get("low", [])
        volumes = indicators.get("volume", [])

        meta = chart.get("meta", {})

        return {
            "timestamps": timestamps,
            "prices": closes,
            "opens": opens,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "current_price": meta.get("regularMarketPrice"),
            "previous_close": meta.get("chartPreviousClose"),
            "currency": meta.get("currency", ""),
        }
    except Exception as e:
        logger.warning("Yahoo Finance fetch failed for %s: %s", ticker, e)
        return {"timestamps": [], "prices": [], "error": str(e)}


# ── Stock Indices ────────────────────────────────────────────────────

def get_index_data(index_id: str, period: str = "1m") -> dict:
    """Get historical data for a stock index."""
    if index_id not in STOCK_INDICES:
        return {"error": f"Unknown index: {index_id}"}

    info = STOCK_INDICES[index_id]
    chart_data = _fetch_yahoo_chart(info["ticker"], period)

    return {
        "id": index_id,
        "name": info["name"],
        "country": info["country"],
        "currency": info["currency"],
        **chart_data,
    }


def get_all_indices_summary() -> list[dict]:
    """Get current prices for all tracked indices."""
    summaries = []
    for index_id, info in STOCK_INDICES.items():
        chart_data = _fetch_yahoo_chart(info["ticker"], "1w")
        current = chart_data.get("current_price")
        prev_close = chart_data.get("previous_close")
        change_pct = None
        if current and prev_close and prev_close != 0:
            change_pct = round(((current - prev_close) / prev_close) * 100, 2)

        summaries.append({
            "id": index_id,
            "name": info["name"],
            "country": info["country"],
            "currency": info["currency"],
            "current_price": current,
            "previous_close": prev_close,
            "change_pct": change_pct,
        })
    return summaries


# ── Forex ────────────────────────────────────────────────────────────

def get_forex_data(pair_id: str, period: str = "1m") -> dict:
    """Get historical data for a forex pair."""
    if pair_id not in FOREX_PAIRS:
        return {"error": f"Unknown forex pair: {pair_id}"}

    info = FOREX_PAIRS[pair_id]
    chart_data = _fetch_yahoo_chart(info["ticker"], period)

    return {
        "id": pair_id,
        "name": info["name"],
        "base": info["base"],
        "quote": info["quote"],
        **chart_data,
    }


def get_all_forex_summary() -> list[dict]:
    """Get current rates for all tracked forex pairs."""
    summaries = []
    for pair_id, info in FOREX_PAIRS.items():
        chart_data = _fetch_yahoo_chart(info["ticker"], "1w")
        current = chart_data.get("current_price")
        prev_close = chart_data.get("previous_close")
        change_pct = None
        if current and prev_close and prev_close != 0:
            change_pct = round(((current - prev_close) / prev_close) * 100, 2)

        summaries.append({
            "id": pair_id,
            "name": info["name"],
            "base": info["base"],
            "quote": info["quote"],
            "current_rate": current,
            "previous_close": prev_close,
            "change_pct": change_pct,
        })
    return summaries


# ── Crypto (CoinGecko) ──────────────────────────────────────────────

def _fetch_coingecko_chart(coin_id: str, period: str = "1m") -> dict:
    """Fetch price history from CoinGecko's free API."""
    params = CRYPTO_PERIOD_MAP.get(period, CRYPTO_PERIOD_MAP["1m"])
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"

    try:
        resp = requests.get(
            url,
            params={"vs_currency": "usd", "days": params["days"]},
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        price_points = data.get("prices", [])
        volume_points = data.get("total_volumes", [])

        timestamps = [int(p[0] / 1000) for p in price_points]
        prices = [p[1] for p in price_points]
        volumes = [v[1] for v in volume_points]

        current_price = prices[-1] if prices else None
        previous_close = prices[-2] if len(prices) >= 2 else None

        return {
            "timestamps": timestamps,
            "prices": prices,
            "volumes": volumes,
            "current_price": current_price,
            "previous_close": previous_close,
        }
    except Exception as e:
        logger.warning("CoinGecko fetch failed for %s, falling back to Yahoo: %s", coin_id, e)
        ticker = "BTC-USD" if coin_id == "bitcoin" else "ETH-USD"
        return _fetch_yahoo_chart(ticker, period)


def _fetch_coingecko_current(coin_id: str) -> dict:
    """Fetch current market data from CoinGecko."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    try:
        resp = requests.get(
            url,
            params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"},
            headers={"Accept": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        market = data.get("market_data", {})

        return {
            "current_price": market.get("current_price", {}).get("usd"),
            "market_cap": market.get("market_cap", {}).get("usd"),
            "total_volume_24h": market.get("total_volume", {}).get("usd"),
            "price_change_24h_pct": market.get("price_change_percentage_24h"),
            "price_change_7d_pct": market.get("price_change_percentage_7d"),
            "price_change_30d_pct": market.get("price_change_percentage_30d"),
            "ath": market.get("ath", {}).get("usd"),
            "ath_change_pct": market.get("ath_change_percentage", {}).get("usd"),
            "circulating_supply": market.get("circulating_supply"),
            "max_supply": market.get("max_supply"),
        }
    except Exception as e:
        logger.warning("CoinGecko current data failed for %s: %s", coin_id, e)
        return {}


def get_crypto_data(crypto_id: str, period: str = "1m") -> dict:
    """Get historical chart data for a crypto asset."""
    if crypto_id not in CRYPTO_ASSETS:
        return {"error": f"Unknown crypto asset: {crypto_id}"}

    info = CRYPTO_ASSETS[crypto_id]
    chart_data = _fetch_coingecko_chart(info["id"], period)
    current_data = _fetch_coingecko_current(info["id"])

    return {
        "id": crypto_id,
        "name": info["name"],
        "symbol": info["symbol"],
        "currency": "USD",
        **chart_data,
        "market_info": current_data,
    }


def get_all_crypto_summary() -> list[dict]:
    """Get current prices and stats for BTC and ETH."""
    summaries = []
    for crypto_id, info in CRYPTO_ASSETS.items():
        current_data = _fetch_coingecko_current(info["id"])
        summaries.append({
            "id": crypto_id,
            "name": info["name"],
            "symbol": info["symbol"],
            "current_price": current_data.get("current_price"),
            "change_24h_pct": current_data.get("price_change_24h_pct"),
            "change_7d_pct": current_data.get("price_change_7d_pct"),
            "change_30d_pct": current_data.get("price_change_30d_pct"),
            "market_cap": current_data.get("market_cap"),
            "volume_24h": current_data.get("total_volume_24h"),
            "ath": current_data.get("ath"),
        })
    return summaries


# ── Crypto Options (Deribit public API, no auth) ────────────────────

def _fetch_deribit_options(currency: str = "BTC") -> dict:
    """Fetch options market data from Deribit's public API."""
    base_url = "https://www.deribit.com/api/v2/public"

    result = {
        "currency": currency,
        "index_price": None,
        "implied_volatility": None,
        "put_call_ratio": None,
        "open_interest_total": 0,
        "volume_24h_total": 0,
        "calls_oi": 0,
        "puts_oi": 0,
        "key_expirations": [],
    }

    try:
        # Get index price
        resp = requests.get(
            f"{base_url}/get_index_price",
            params={"index_name": f"{currency.lower()}_usd"},
            timeout=10,
        )
        if resp.ok:
            idx_data = resp.json().get("result", {})
            result["index_price"] = idx_data.get("index_price")

        # Get book summary for all options
        resp = requests.get(
            f"{base_url}/get_book_summary_by_currency",
            params={"currency": currency, "kind": "option"},
            timeout=15,
        )
        if not resp.ok:
            return result

        book_summaries = resp.json().get("result", [])
        if not book_summaries:
            return result

        total_puts_oi = 0
        total_calls_oi = 0
        total_volume = 0
        iv_values = []
        expiration_data = {}

        for s in book_summaries:
            instrument = s.get("instrument_name", "")
            oi = s.get("open_interest", 0) or 0
            vol = s.get("volume", 0) or 0
            mark_iv = s.get("mark_iv")

            # Parse: BTC-28MAR25-90000-C
            parts = instrument.split("-")
            if len(parts) >= 4:
                expiry = parts[1]
                option_type = parts[-1]  # C or P

                if option_type == "C":
                    total_calls_oi += oi
                else:
                    total_puts_oi += oi

                total_volume += vol
                if mark_iv and mark_iv > 0:
                    iv_values.append(mark_iv)

                if expiry not in expiration_data:
                    expiration_data[expiry] = {
                        "call_oi": 0, "put_oi": 0,
                        "call_volume": 0, "put_volume": 0,
                        "iv_values": [],
                    }
                ed = expiration_data[expiry]
                if option_type == "C":
                    ed["call_oi"] += oi
                    ed["call_volume"] += vol
                else:
                    ed["put_oi"] += oi
                    ed["put_volume"] += vol
                if mark_iv and mark_iv > 0:
                    ed["iv_values"].append(mark_iv)

        # Aggregates
        result["open_interest_total"] = total_calls_oi + total_puts_oi
        result["volume_24h_total"] = round(total_volume, 2)
        result["put_call_ratio"] = round(total_puts_oi / total_calls_oi, 3) if total_calls_oi > 0 else None
        result["implied_volatility"] = round(sum(iv_values) / len(iv_values), 2) if iv_values else None
        result["calls_oi"] = total_calls_oi
        result["puts_oi"] = total_puts_oi

        # Top expirations by open interest
        expirations = []
        for exp, ed in sorted(expiration_data.items()):
            avg_iv = round(sum(ed["iv_values"]) / len(ed["iv_values"]), 2) if ed["iv_values"] else None
            total_oi = ed["call_oi"] + ed["put_oi"]
            expirations.append({
                "expiration": exp,
                "call_oi": ed["call_oi"],
                "put_oi": ed["put_oi"],
                "total_oi": total_oi,
                "call_volume": round(ed["call_volume"], 2),
                "put_volume": round(ed["put_volume"], 2),
                "pc_ratio": round(ed["put_oi"] / ed["call_oi"], 3) if ed["call_oi"] > 0 else None,
                "avg_iv": avg_iv,
            })
        expirations.sort(key=lambda x: x["total_oi"], reverse=True)
        result["key_expirations"] = expirations[:10]

    except Exception as e:
        logger.warning("Deribit options fetch failed for %s: %s", currency, e)

    return result


def get_crypto_options(crypto_id: str) -> dict:
    """Get options data for a crypto asset."""
    if crypto_id not in CRYPTO_ASSETS:
        return {"error": f"Unknown crypto asset: {crypto_id}"}

    info = CRYPTO_ASSETS[crypto_id]
    options_data = _fetch_deribit_options(info["symbol"])

    return {
        "id": crypto_id,
        "name": info["name"],
        "symbol": info["symbol"],
        **options_data,
    }
