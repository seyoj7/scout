# Scout

Scout is a small Python command-line tool for viewing cryptocurrency candles and monitoring 50-period SMA intersections. It fetches market data from Binance or Hyperliquid, calculates the 50-period simple moving average (SMA), and can send 4-hour 50 SMA intersection alerts to Telegram with a chart image.

## Features

- Fetches OHLCV candle data from Binance or Hyperliquid.
- Plots candlesticks and a 50-period simple moving average (SMA).
- Runs a continuous 4-hour monitor and sends Telegram photo alerts when a closed candle intersects the 50 SMA.
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

Supported interval units are minutes (`m`), hours (`h`), days (`d`), and weeks (`w`), with a positive integer amount (for example, `15m`, `4h`, or `1d`). The chart command accepts any positive `--limit` (default 1000). Binance requests are paginated in batches of at most 1000 candles, allowing histories larger than 1000; the exchange may return fewer candles when the symbol has less available history. Hyperliquid's candle snapshot endpoint may cap the returned history independently of the requested limit.

### Chart contents

- Candles use teal for rising and red for falling periods.
- The blue line is the 50-candle SMA of closing prices.
- Price values appear on the right axis. Dates are displayed in India Standard Time (IST).

## Indicators and signal rules

### SMA

`simple_moving_average` computes a rolling average of candle closes. The chart displays the 50-period SMA. At the beginning of a dataset, it averages the closes available so far until 50 candles have accumulated.

The 4-hour Telegram monitor triggers an alert when a closed candle intersects the 50 SMA (`low <= sma <= high`).

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

The monitor fetches up to 500 four-hour candles, checks once per minute, and only calculates alert signals on fully closed candles. It sends a Telegram photo containing a recent chart and a caption with candle time in IST, OHLC values, and the 50 SMA value. It tracks progress in `alert_state.json`, keyed by exchange, symbol, and interval. On the first run for a key, it records the latest closed candle as its starting point; it does not send an alert for older signals. Progress is saved before a send attempt to avoid duplicate alerts after restarts or ambiguous network timeouts. If a send fails after progress is saved, that signal may not be retried automatically.

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
| `indicators.py` | 50-period SMA calculation. |
| `alert.py` | Continuous 4-hour monitor and Telegram message/photo delivery. |
| `requirements.txt` | Python package dependencies. |
| `alert_state.json` | Runtime alert progress, generated next to `alert.py`. |

## Troubleshooting

- **Missing Telegram credentials:** confirm `.env` is next to `alert.py` and contains both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
- **Invalid symbol or interval:** verify the symbol is supported by the selected exchange and use an interval such as `1h`, `4h`, or `1d`.
- **Network/API errors:** the chart command reports fetch errors; the alert loop prints a check failure and retries on its next poll.
