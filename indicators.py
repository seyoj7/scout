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


def _true_ranges(candles: list[dict]) -> list[float]:
    ranges = []
    for index, candle in enumerate(candles):
        if index == 0:
            ranges.append(candle["high"] - candle["low"])
        else:
            previous_close = candles[index - 1]["close"]
            ranges.append(
                max(
                    candle["high"] - candle["low"],
                    abs(candle["high"] - previous_close),
                    abs(candle["low"] - previous_close),
                )
            )
    return ranges


def _wilder_atr(candles: list[dict], period: int) -> list[float | None]:
    """Calculate Pine-style ATR (Wilder RMA of true range)."""
    true_ranges = _true_ranges(candles)
    atr: list[float | None] = [None] * len(candles)
    if len(candles) < period:
        return atr

    current = sum(true_ranges[:period]) / period
    atr[period - 1] = current
    for index in range(period, len(candles)):
        current = (current * (period - 1) + true_ranges[index]) / period
        atr[index] = current
    return atr


def find_displacements(
    candles: list[dict],
    *,
    atr_length: int = 300,
    atr_multiplier: float = 1.5,
    min_body_pct: float = 60.0,
    require_fvg: bool = True,
    fvg_threshold: float = 0.3,
    swing_lookback: int = 15,
) -> list[dict | None]:
    """Return direction and structure-break status for displacement candles.

    With FVG enabled, the Pine indicator confirms the displacement one bar
    later, then paints the original candle using an offset of -1.
    """
    if atr_length < 1 or swing_lookback < 2:
        raise ValueError("ATR length must be positive and swing lookback at least 2")
    if not 0 <= min_body_pct <= 100 or atr_multiplier < 0 or fvg_threshold < 0:
        raise ValueError("Body percentage must be 0-100 and ATR thresholds nonnegative")

    count = len(candles)
    atr = _wilder_atr(candles, atr_length)
    ranges = [candle["high"] - candle["low"] for candle in candles]
    body_pct = [
        abs(candle["close"] - candle["open"]) / candle_range * 100
        if candle_range > 0
        else 0.0
        for candle, candle_range in zip(candles, ranges)
    ]
    big_range = []
    for index, candle_range in enumerate(ranges):
        current_atr = atr[index]
        big_range.append(
            current_atr is not None
            and current_atr > 0
            and candle_range >= current_atr * atr_multiplier
        )
    bullish = [
        body_pct[i] >= min_body_pct and candle["close"] > candle["open"]
        for i, candle in enumerate(candles)
    ]
    bearish = [
        body_pct[i] >= min_body_pct and candle["close"] < candle["open"]
        for i, candle in enumerate(candles)
    ]

    broke_up = [False] * count
    broke_down = [False] * count
    for index in range(swing_lookback, count):
        prior = candles[index - swing_lookback:index]
        broke_up[index] = candles[index]["high"] > max(c["high"] for c in prior)
        broke_down[index] = candles[index]["low"] < min(c["low"] for c in prior)

    result: list[dict | None] = [None] * count
    for index in range(count):
        if require_fvg:
            if index < 2:
                continue
            current_atr = atr[index]
            if current_atr is None:
                continue
            gap_up = (
                candles[index - 1]["high"] > candles[index - 2]["high"]
                and candles[index]["low"] > candles[index - 2]["high"]
                and candles[index]["low"] - candles[index - 2]["high"]
                > current_atr * fvg_threshold
            )
            gap_down = (
                candles[index - 1]["low"] < candles[index - 2]["low"]
                and candles[index]["high"] < candles[index - 2]["low"]
                and candles[index - 2]["low"] - candles[index]["high"]
                > current_atr * fvg_threshold
            )
            source = index - 1
            bull = big_range[source] and bullish[source] and gap_up
            bear = big_range[source] and bearish[source] and gap_down
        else:
            source = index
            bull = big_range[index] and bullish[index]
            bear = big_range[index] and bearish[index]

        if bull:
            result[source] = {"direction": "bullish", "break": broke_up[source]}
        elif bear:
            result[source] = {"direction": "bearish", "break": broke_down[source]}
    return result


__all__ = [
    "calculate_rsi",
    "find_displacements",
    "simple_moving_average",
]
