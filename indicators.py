from __future__ import annotations


def calculate_rsi(candles: list[dict], period: int = 14) -> list[float | None]:
    values: list[float | None] = [None] * len(candles)
    if len(candles) <= period:
        return values

    changes = [
        candles[i]["close"] - candles[i - 1]["close"] for i in range(1, len(candles))
    ]
    average_gain = sum(max(change, 0) for change in changes[:period]) / period
    average_loss = sum(max(-change, 0) for change in changes[:period]) / period

    def rsi(gain: float, loss: float) -> float:
        return 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)

    values[period] = rsi(average_gain, average_loss)
    for index in range(period + 1, len(candles)):
        change = changes[index - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
        values[index] = rsi(average_gain, average_loss)
    return values


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


__all__ = ["calculate_rsi", "simple_moving_average"]
