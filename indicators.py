from __future__ import annotations


def simple_moving_average(candles: list[dict], period: int) -> list[float | None]:
    closes = [candle["close"] for candle in candles]
    average: list[float | None] = [None] * len(closes)
    running_sum = 0.0
    for index, close in enumerate(closes):
        running_sum += close
        if index >= period:
            running_sum -= closes[index - period]
        average[index] = running_sum / min(index + 1, period)
    return average


__all__ = [
    "simple_moving_average",
]
