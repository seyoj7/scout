import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

from data_fetch import fetch_candles
from indicators import simple_moving_average

INTERVAL = "4h"
POLL_SECONDS = 60
CHART_CANDLES = 200
STATE_FILE = Path(__file__).with_name("alert_state.json")
IST = ZoneInfo("Asia/Kolkata")


def load_env():
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _alert_message(symbol, candle, sma_value):
    candle_time = datetime.fromtimestamp(candle["time"], IST)
    return (
        f"4H 50 SMA intersection: {symbol}\n"
        f"Time: {candle_time:%Y-%m-%d %I:%M %p} IST\n"
        f"Open: {candle['open']:g}  High: {candle['high']:g}\n"
        f"Low: {candle['low']:g}  Close: {candle['close']:g}\n"
        f"SMA 50: {sma_value:g}"
    )


def _send_telegram_photo(token, chat_id, caption, image_path):
    boundary = "----ScoutAlertBoundary7MA4YWxkTrZu0gW"
    image = Path(image_path).read_bytes()
    body = b"".join(
        (
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
                f"{chat_id}\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="caption"\r\n\r\n'
                f"{caption}\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="photo"; filename="alert.png"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode("utf-8"),
            image,
            f"\r\n--{boundary}--\r\n".encode("ascii"),
        )
    )
    request = Request(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urlopen(request, timeout=15) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram send failed"))


def send_alert(
    token,
    chat_id,
    symbol,
    candle,
    sma_value,
    *,
    chart_candles=None,
    exchange="binance",
):
    message = _alert_message(symbol, candle, sma_value)
    if chart_candles is None:
        request = Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat_id, "text": message}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram send failed"))
        return

    # Build a 200-candle chart and send it as the alert photo with the text caption.
    from plotting import plot_candles

    with tempfile.TemporaryDirectory() as directory:
        image_path = Path(directory) / "alert.png"
        plot_candles(
            chart_candles,
            symbol,
            exchange,
            INTERVAL,
            str(image_path),
        )
        _send_telegram_photo(token, chat_id, message, image_path)


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
    parser = argparse.ArgumentParser(description="Telegram alerts for 4H 50 SMA intersections")
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
            fetched_candles = fetch_candles(args.exchange, symbol, INTERVAL, 500)
            now = int(datetime.now(timezone.utc).timestamp())
            candles = [
                c for c in fetched_candles if c["time"] + 4 * 60 * 60 <= now
            ]
            sma_values = simple_moving_average(candles, 50)

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

                        sma_value = sma_values[index]
                        if sma_value is not None and candle["low"] <= sma_value <= candle["high"]:
                            # Add the latest in-progress candle to the image,
                            # while keeping signal calculations on closed bars.
                            chart_end = len(fetched_candles)
                            chart_start = max(0, chart_end - CHART_CANDLES)
                            send_alert(
                                token,
                                chat_id,
                                symbol,
                                candle,
                                sma_value,
                                chart_candles=fetched_candles[chart_start:chart_end],
                                exchange=args.exchange,
                            )
                            print(f"Sent 50 SMA intersection chart alert for {symbol}")
        except Exception as exc:
            print(f"Alert check failed: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
