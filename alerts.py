from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def mark_entries(
    rsi_values: list[float | None], upper: float, lower: float
) -> list[tuple[int, str, float]]:
    marks = []
    previous = None
    for index, value in enumerate(rsi_values):
        if value is None:
            continue
        if value >= upper and (previous is None or previous < upper):
            marks.append((index, f"RSI \u2265 {upper:g}", value))
        elif value <= lower and (previous is None or previous > lower):
            marks.append((index, f"RSI \u2264 {lower:g}", value))
        previous = value
    return marks


def print_alerts(candles: list[dict], marks: list[tuple[int, str, float]]) -> None:
    if marks:
        for index, label, value in marks:
            date = datetime.fromtimestamp(
                candles[index]["time"], tz=IST
            ).strftime("%Y-%m-%d %I:%M %p IST")
            print(f"{date}: {label} (RSI {value:.2f})")
    else:
        print("No RSI entries at 70 or 30 in the requested candles.")
