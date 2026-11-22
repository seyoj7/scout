"""Send a test alert to Telegram using the credentials in .env.

Run ``python test.py`` or choose a symbol and direction with, for example,
``python test.py --symbol ETHUSDT --direction bearish``.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from alert import CHART_CANDLES, INTERVAL, load_env, send_alert
from data_fetch import fetch_candles
from indicators import calculate_rsi, find_displacements
from mark_entries import find_entries


def main():
    parser = argparse.ArgumentParser(description="Send a test alert to Telegram")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol shown in the alert")
    parser.add_argument(
        "--direction", choices=("bullish", "bearish"), default="bullish"
    )
    parser.add_argument("--exchange", choices=("binance", "hype"), default="binance")
    args = parser.parse_args()

    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        parser.error("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")

    try:
        symbol = args.symbol.upper()
        fetched_candles = fetch_candles(args.exchange, symbol, INTERVAL, 500)
        now = int(datetime.now(timezone.utc).timestamp())
        candles = [
            c for c in fetched_candles if c["time"] + 4 * 60 * 60 <= now
        ]
        if not candles:
            raise RuntimeError("No closed candles available to build the test chart")

        signals = find_displacements(candles)
        rsi_marks = find_entries(calculate_rsi(fetched_candles), 70, 30)
        chart_start = max(0, len(fetched_candles) - CHART_CANDLES)
        chart_signals = signals + [None] * (len(fetched_candles) - len(signals))
        chart_marks = [
            (index - chart_start, label, value)
            for index, label, value in rsi_marks
            if index >= chart_start
        ]
        test_candle = candles[-1]
        test_signal = {
            "direction": args.direction,
            "break": signals[-1]["break"] if signals[-1] else False,
        }
        send_alert(
            token,
            chat_id,
            symbol,
            test_candle,
            test_signal,
            chart_candles=fetched_candles[chart_start:],
            chart_signals=chart_signals[chart_start:],
            chart_marks=chart_marks,
            exchange=args.exchange,
        )
    except Exception as exc:
        print(f"Could not send test alert: {exc}", file=sys.stderr)
        return 1

    print(
        f"Test chart alert sent to Telegram for {symbol} "
        f"({args.exchange}, {args.direction})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
