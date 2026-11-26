# Scout

Scout is a small Python command-line tool for viewing cryptocurrency candles and monitoring displacement candles. It fetches market data from Binance or Hyperliquid, calculates RSI and moving averages, marks RSI threshold entries on charts, and can send 4-hour displacement alerts to Telegram with a chart image.

## Features

- Fetches OHLCV candle data from Binance or Hyperliquid.
- Plots candlesticks, a 50-period simple moving average (SMA), RSI threshold markers, and displacement signals.
- Prints RSI threshold entries and counts displacement signals in the requested chart history.
- Runs a continuous 4-hour displacement monitor and sends Telegram photo alerts.
- Saves alert progress locally so the same confirmed candle is not sent again after a restart.

## Requirements

- Python 3.10 or newer (the code uses modern type annotations and `str.removesuffix`).
- Dependencies listed in `requirements.txt` (currently Matplotlib).
- Internet access to query the exchange API and, for alerts, the Telegram Bot API.

Install the dependency:

```bash
python -m pip install -r requirements.txt
```

## View a chart

Run the chart tool with its defaults (BTCUSDT, Binance, daily candles):

```bash
python plotting.py
```

Choose the exchange, market, candle interval, and visible candle count:

```bash
python plotting.py --exchange binance --symbol ETHUSDT --interval 4h --limit 300
python plotting.py --exchange hype --symbol BTCUSDT --interval 1h --limit 200
```

Save the chart to an image instead of opening a window:

```bash
python plotting.py --symbol BTCUSDT --interval 4h --limit 300 --output chart.png
```

Supported interval units are minutes (`m`), hours (`h`), days (`d`), and weeks (`w`), with a positive integer amount (for example, `15m`, `4h`, or `1d`). The chart command accepts any positive `--limit` (default 1000) and an RSI period of at least 1. It fetches up to 300 extra candles for indicator warm-up. Binance requests are paginated in batches of at most 1000 candles, allowing histories larger than 1000; the exchange may return fewer candles when the symbol has less available history. Hyperliquid's candle snapshot endpoint may cap the returned history independently of the requested limit.

### Chart contents

- Candles use teal for rising and red for falling periods. Displacement candles have separate blue/yellow coloring, with darker colors when a structure break is detected.
- The blue line is the 50-candle SMA of closing prices.
- Price values appear on the right axis. Dates are displayed in India Standard Time (IST).
- RSI entry markers show when RSI crosses into or out of the configured threshold regions; the command currently uses 70 and 30. Entries are also printed in the terminal.

## Indicators and signal rules

### RSI

`calculate_rsi` in `indicators.py` calculates a Wilder-style RSI. It seeds average gains and losses from the first `period` close-to-close changes, then updates each average using Wilder's smoothing formula. Values before the seed is available are `None`. If average loss is zero, RSI is set to 100.

`find_entries` in `mark_entries.py` reports threshold transitions, not every candle that remains beyond a threshold:

- An overbought entry is recorded when RSI reaches or crosses above 70.
- An oversold entry is recorded when RSI reaches or crosses below 30.

The chart command uses a default RSI period of 14; override it with `--period`. RSI is used for chart/terminal markers only. The Telegram alert loop does not send RSI alerts.

### SMA

`simple_moving_average` computes a rolling average of candle closes. The chart displays the 50-period SMA. At the beginning of a dataset, it averages the closes available so far until 50 candles have accumulated.

### Displacement candles

`find_displacements` uses these defaults:

| Setting | Default | Meaning |
| --- | ---: | --- |
| ATR length | 300 candles | Period for the Wilder-smoothed Average True Range. |
| ATR multiplier | 1.5 | Candle high-low range must be at least 1.5 times ATR. |
| Minimum body | 60% | Candle body must occupy at least this percentage of its high-low range. |
| Require fair value gap (FVG) | Yes | Requires a directional three-candle gap to confirm displacement. |
| FVG threshold | 0.3 ATR | The gap must be larger than 0.3 times ATR. |
| Swing lookback | 15 candles | Checks whether the candle breaks the prior 15-candle high or low. |

A bullish displacement candle must have a sufficiently large range and body, close above its open, and (by default) be followed by the FVG pattern checked by the next candle. A bearish candle uses the inverse conditions. The FVG confirmation is calculated one candle later, but the signal is assigned to the original displacement candle. The structure-break flag is true when that signal candle's high exceeds the previous lookback highs (bullish) or its low falls below the previous lookback lows (bearish).

With FVG required, the signal is unavailable until the confirming candle exists. The monitor only analyzes closed candles and associates a newly confirmed signal with the preceding candle.

## Telegram alerts

The alert monitor watches one symbol and exchange at a time, using the fixed `4h` interval. Create a Telegram bot and obtain its bot token and destination chat ID, then create a `.env` file in the project directory:

```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Keep `.env` private; it is ignored by Git. Start monitoring with:

```bash
python alert.py
python alert.py --symbol ETHUSDT --exchange binance
python alert.py --symbol BTCUSDT --exchange hype
```

The monitor fetches up to 500 four-hour candles, checks once per minute, and only calculates alert signals on fully closed candles. It sends a Telegram photo containing a recent chart and a caption with direction, candle time in IST, OHLC values, and whether a structure break occurred. It tracks progress in `alert_state.json`, keyed by exchange, symbol, and interval. On the first run for a key, it records the latest closed candle as its starting point; it does not send an alert for older signals. Progress is saved before a send attempt to avoid duplicate alerts after restarts or ambiguous network timeouts. If a send fails after progress is saved, that signal may not be retried automatically.

The loop logs errors and continues polling. Stop it with Ctrl+C. Run separate processes if you want to monitor multiple symbols.

## Data sources

- Binance candles come from the public Spot API (`api.binance.com`). Use Binance symbols such as `BTCUSDT`.
- Hyperliquid candles come from its public info endpoint (`api.hyperliquid.xyz`). The program removes a trailing `USDT` from the provided symbol before requesting the coin, so examples include `BTCUSDT` and `ETHUSDT`.

The program does not place orders or manage positions. Exchange/API availability, supported symbols, and returned candle history depend on the data providers.

## Project files

| File | Purpose |
| --- | --- |
| `plotting.py` | Chart command-line interface and Matplotlib chart rendering. |
| `data_fetch.py` | Binance and Hyperliquid candle fetching and interval conversion. |
| `indicators.py` | RSI, SMA, ATR, and displacement/FVG calculations. |
| `mark_entries.py` | RSI threshold-crossing detection and terminal output. |
| `alert.py` | Continuous 4-hour monitor and Telegram message/photo delivery. |
| `requirements.txt` | Python package dependencies. |
| `alert_state.json` | Runtime alert progress, generated next to `alert.py`. |

## Troubleshooting

- **Missing Telegram credentials:** confirm `.env` is next to `alert.py` and contains both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **No displacement signals:** the default 300-candle ATR warm-up plus FVG and body/range filters can make qualifying signals uncommon. The chart history may not contain enough candles for ATR to initialize.
- **Invalid symbol or interval:** verify the symbol is supported by the selected exchange and use an interval such as `1h`, `4h`, or `1d`.
- **Network/API errors:** the chart command reports fetch errors; the alert loop prints a check failure and retries on its next poll.
