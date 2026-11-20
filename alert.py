import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from data_fetch import fetch_candles
from indicators import find_displacements

INTERVAL = "4h"
POLL_SECONDS = 60
STATE_FILE = Path(__file__).with_name("alert_state.json")


def load_env():
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def send_alert(token, chat_id, symbol, candle, signal):
    direction = signal["direction"].capitalize()
    candle_time = datetime.fromtimestamp(candle["time"], timezone.utc)
    message = (
        f"{direction} 4H displacement: {symbol}\n"
        f"Candle: {candle_time:%Y-%m-%d %H:%M} UTC\n"
        f"Open: {candle['open']:g}  High: {candle['high']:g}\n"
        f"Low: {candle['low']:g}  Close: {candle['close']:g}\n"
        f"Structure break: {'Yes' if signal['break'] else 'No'}"
    )
    request = Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": message}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram send failed"))


def load_state():
    if not STATE_FILE.exists():
        return {}
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("alert_state.json must contain a JSON object")
    return state


def save_state(state):
    temporary_file = STATE_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary_file.replace(STATE_FILE)


def main():
    parser = argparse.ArgumentParser(description="Telegram alerts for 4H displacement candles")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--exchange", choices=("binance", "hype"), default="binance")
    args = parser.parse_args()

    load_env()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise SystemExit("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to .env")

    symbol = args.symbol.upper()
    state = load_state()
    state_key = f"{args.exchange}:{symbol}:{INTERVAL}"
    saved_progress = state.get(state_key, {})
    if isinstance(saved_progress, dict):
        last_closed_time = saved_progress.get("last_checked_confirmation")
    else:
        last_closed_time = saved_progress
    print(f"Watching {symbol} ({args.exchange}, {INTERVAL})")

    while True:
        try:
            candles = fetch_candles(args.exchange, symbol, INTERVAL, 500)
            now = int(datetime.now(timezone.utc).timestamp())
            candles = [c for c in candles if c["time"] + 4 * 60 * 60 <= now]
            signals = find_displacements(candles)

            if candles:
                if last_closed_time is None:
                    last_closed_time = candles[-1]["time"]
                    state[state_key] = {
                        "last_checked_confirmation": last_closed_time
                    }
                    save_state(state)
                else:
                    for index, candle in enumerate(candles):
                        if candle["time"] <= last_closed_time:
                            continue

                        # Persist before sending to prevent duplicates after a
                        # restart or an ambiguous Telegram timeout.
                        last_closed_time = candle["time"]
                        state[state_key] = {
                            "last_checked_confirmation": last_closed_time
                        }
                        save_state(state)

                        source = index - 1  # FVG confirms and colors the prior candle.
                        signal = signals[source] if source >= 0 else None
                        if signal is not None:
                            send_alert(token, chat_id, symbol, candles[source], signal)
                            print(f"Sent {signal['direction']} alert for {symbol}")
        except Exception as exc:
            print(f"Alert check failed: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
