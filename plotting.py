from __future__ import annotations

import argparse
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from mark_entries import find_entries, mark_entries
from data_fetch import fetch_candles
from indicators import calculate_rsi, find_displacements, simple_moving_average

IST = ZoneInfo("Asia/Kolkata")


def plot_candles(
    candles: list[dict],
    marks: list[tuple[int, str, float]],
    symbol: str,
    exchange: str,
    interval: str,
    period: int,
    output: str | None,
    displacement_signals: list[dict | None] | None = None,
) -> None:
    times = [datetime.fromtimestamp(candle["time"], tz=IST) for candle in candles]
    x_values = mdates.date2num(times)
    spacing = (x_values[-1] - x_values[0]) / max(len(x_values) - 1, 1)
    candle_width = spacing * 0.7
    prices = [price for candle in candles for price in (candle["low"], candle["high"])]
    price_range = max(prices) - min(prices) or max(prices) * 0.01 or 1
    fig, ax = plt.subplots(figsize=(14, 7))
    for index, (x, candle) in enumerate(zip(x_values, candles)):
        rising = candle["close"] >= candle["open"]
        signal = displacement_signals[index] if displacement_signals else None
        if signal:
            color = "#60A5FA" if signal["direction"] == "bullish" else "#FFFF00"
            if signal["break"]:
                color = "#1E3195" if signal["direction"] == "bullish" else "#E6C800"
        else:
            color = "#26a69a" if rising else "#ef5350"
        ax.vlines(x, candle["low"], candle["high"], color=color, linewidth=1)
        body_bottom = min(candle["open"], candle["close"])
        body_height = abs(candle["close"] - candle["open"])
        if body_height == 0:
            ax.hlines(
                body_bottom,
                x - candle_width / 2,
                x + candle_width / 2,
                color=color,
                linewidth=1.5,
            )
        else:
            ax.add_patch(
                Rectangle(
                    (x - candle_width / 2, body_bottom),
                    candle_width,
                    body_height,
                    facecolor=color,
                    edgecolor=color,
                    linewidth=0.8,
                )
            )

    sma_50 = simple_moving_average(candles, 50)
    valid_values = [
        (x, value) for x, value in zip(x_values, sma_50) if value is not None
    ]
    if valid_values:
        ax.plot(
            [point[0] for point in valid_values],
            [point[1] for point in valid_values],
            color="#42a5f5",
            linewidth=1.4,
            label="SMA 50",
            zorder=3,
        )

    for index, label, value in marks:
        candle = candles[index]
        is_overbought = "\u2265" in label
        y = (
            candle["high"] + price_range * 0.025
            if is_overbought
            else candle["low"] - price_range * 0.025
        )
        color = "#ff9800" if is_overbought else "#42a5f5"
        ax.scatter(
            x_values[index],
            y,
            marker="v" if is_overbought else "^",
            s=90,
            color=color,
            edgecolors="white",
            linewidths=0.7,
            zorder=5,
            label=label,
        )
        ax.annotate(
            f"{value:.1f}",
            (x_values[index], y),
            xytext=(0, -14 if is_overbought else 10),
            textcoords="offset points",
            ha="center",
            va="top" if is_overbought else "bottom",
            color=color,
            fontsize=8,
        )

    # Keep a small border around the candles and RSI labels while using more
    # of the available chart area.
    ax.margins(x=0.01, y=0.10)
    left_limit, right_limit = ax.get_xlim()
    ax.set_xlim(left=left_limit, right=right_limit + spacing * 15)

    handles, labels = ax.get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    if unique:
        ax.legend(unique.values(), unique.keys(), loc="upper left")
    exchange_name = "Hyperliquid" if exchange == "hype" else "Binance"
    ax.set_title(
        f"{symbol} \u00b7 {interval} \u00b7 {len(candles)} candles", loc="left"
    )
    ax.set_title(f"Exchange: {exchange_name}", loc="right")
    ax.yaxis.tick_right()
    ax.format_xdata = lambda x: mdates.num2date(x, tz=IST).strftime("%d-%b-%y %I:%M %p")
    ax.format_ydata = lambda y: f"{y:,.2f}"
    ax.grid(True, alpha=0.2)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b-%y", tz=IST))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()
    if output:
        fig.savefig(output, dpi=160, bbox_inches="tight")
        print(f"Saved chart to {output}")
        plt.close(fig)
    else:
        plt.show()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch candles, report RSI entries, and plot them."
    )
    parser.add_argument("--exchange", choices=("binance", "hype"), default="binance")
    parser.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Market symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT",
    )
    parser.add_argument(
        "--interval", default="1d", help="Candle interval, e.g. 5m, 15m, 1h, 1d"
    )
    parser.add_argument(
        "--limit", type=int, default=1000, help="Number of candles to display (1-1000)"
    )
    parser.add_argument("--period", type=int, default=14, help="RSI period")
    parser.add_argument(
        "--output", help="Save image to a file instead of opening a window"
    )
    args = parser.parse_args()

    if not 1 <= args.limit <= 1000:
        parser.error("--limit must be between 1 and 1000")
    if args.period < 1:
        parser.error("--period must be at least 1")
    try:
        symbol = args.symbol.upper()
        fetch_limit = min(args.limit + 300, 1000)
        history = fetch_candles(args.exchange, symbol, args.interval, fetch_limit)
        rsi_values = calculate_rsi(history, args.period)
        history_marks = find_entries(rsi_values, 70, 30)
        history_signals = find_displacements(history)
        first_visible = max(0, len(history) - args.limit)
        candles = history[first_visible:]
        marks = [
            (index - first_visible, label, value)
            for index, label, value in history_marks
            if index >= first_visible
        ]
        displacement_signals = history_signals[first_visible:]
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Loaded {len(candles)} chart candles for {symbol} "
        f"({args.exchange}, {args.interval}) with ATR warm-up history."
    )
    mark_entries(candles, marks)
    bullish = sum(
        signal is not None and signal["direction"] == "bullish"
        for signal in displacement_signals
    )
    bearish = sum(
        signal is not None and signal["direction"] == "bearish"
        for signal in displacement_signals
    )
    breaks = sum(
        signal is not None and signal["break"] for signal in displacement_signals
    )
    print(
        f"Found {bullish} bullish and {bearish} bearish displacement candles "
        f"({breaks} structure breaks)."
    )
    plot_candles(
        candles,
        marks,
        symbol,
        args.exchange,
        args.interval,
        args.period,
        args.output,
        displacement_signals=displacement_signals,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
