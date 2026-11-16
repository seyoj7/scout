from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _load_json(request: Request, exchange: str) -> list[Any]:
    try:
        with urlopen(request, timeout=15) as response:
            raw = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not fetch candles from {exchange}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{exchange.capitalize()} returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(raw, list):
        raise RuntimeError(f"{exchange} returned an unexpected candle response.")
    return raw


def interval_seconds(interval: str) -> int:
    if len(interval) < 2 or not interval[:-1].isdigit():
        raise ValueError(f"Unsupported candle interval: {interval}")
    amount = int(interval[:-1])
    unit = interval[-1]
    units = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
    if amount < 1 or unit not in units:
        raise ValueError(f"Unsupported candle interval: {interval}")
    return amount * units[unit]


def fetch_candles(exchange: str, symbol: str, interval: str, limit: int) -> list[dict]:
    if exchange == "binance":
        query = urlencode({"symbol": symbol, "interval": interval, "limit": limit})
        request = Request(f"https://api.binance.com/api/v3/klines?{query}")
        raw = _load_json(request, "Binance")

        candles = [
            {
                "time": int(row[0]) // 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in raw
        ]
    else:
        end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ms = end_ms - interval_seconds(interval) * limit * 1000
        coin = symbol.removesuffix("USDT")
        payload = json.dumps(
            {
                "type": "candleSnapshot",
                "req": {
                    "coin": coin,
                    "interval": interval,
                    "startTime": start_ms,
                    "endTime": end_ms,
                },
            }
        ).encode("utf-8")
        request = Request(
            "https://api.hyperliquid.xyz/info",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        raw = _load_json(request, "Hyperliquid")

        candles = [
            {
                "time": int(row["t"]) // 1000,
                "open": float(row["o"]),
                "high": float(row["h"]),
                "low": float(row["l"]),
                "close": float(row["c"]),
                "volume": float(row["v"]),
            }
            for row in raw
        ]

    if not candles:
        raise RuntimeError(f"{exchange.capitalize()} returned no candles for {symbol}.")
    return sorted(candles, key=lambda candle: candle["time"])
