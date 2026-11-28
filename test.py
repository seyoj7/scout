"""Send a test alert to Telegram using the credentials in .env.

Run ``python test.py`` or choose a symbol and exchange with, for example,
``python test.py --symbol ETHUSDT --exchange hype``.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from alert import CHART_CANDLES, INTERVAL, load_env, send_alert
from data_fetch import fetch_candles
from indicators import simple_moving_average


def main():
    parser = argparse.ArgumentParser(description="Send a test alert to Telegram")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol shown in the alert")
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

        sma_values = simple_moving_average(candles, 50)
        chart_start = max(0, len(fetched_candles) - CHART_CANDLES)
        test_candle = candles[-1]
        test_sma = sma_values[-1]
        send_alert(
            token,
            chat_id,
            symbol,
            test_candle,
            test_sma,
            chart_candles=fetched_candles[chart_start:],
            exchange=args.exchange,
        )
    except Exception as exc:
        print(f"Could not send test alert: {exc}", file=sys.stderr)
        return 1

    print(
        f"Test chart alert sent to Telegram for {symbol} ({args.exchange})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
