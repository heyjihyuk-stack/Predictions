"""Market data fetching for stock indices and forex pairs.

Uses free APIs (Yahoo Finance chart API, exchangerate.host) to get
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

# Period mapping for Yahoo Finance API
PERIOD_MAP = {
    "1w": {"range": "5d", "interval": "1h"},
    "1m": {"range": "1mo", "interval": "1d"},
    "3m": {"range": "3mo", "interval": "1d"},
    "1y": {"range": "1y", "interval": "1wk"},
    "5y": {"range": "5y", "interval": "1mo"},
}


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
