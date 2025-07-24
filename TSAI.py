import requests
# ===================
# 🛰️ Direct REST API Historical Bars Fetch
# ===================
def fetch_bars_rest(symbol, limit=100, timeframe='1Day'):
    url = 'https://data.alpaca.markets/v2/stocks/bars'
    headers = {
        'APCA-API-KEY-ID': API_KEY,
        'APCA-API-SECRET-KEY': API_SECRET
    }
    # Accept a list or string for symbols
    if isinstance(symbol, list):
        symbol_str = ','.join(symbol)
    else:
        symbol_str = symbol
    params = {
        'symbols': symbol_str,
        'limit': limit,
        'timeframe': timeframe,
        'adjustment': 'raw',
        'feed': 'iex',  # Use IEX feed for free plans
        'sort': 'asc'
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        print(f"[REST DEBUG] Error fetching bars for {symbol}: {e}")
        return None
# ===================
# 📂 Print Open Trades
# ===================
def print_open_trades():
    try:
        positions = api.list_positions()
        if not positions:
            print(f"\n[{datetime.datetime.now()}] === No Open Trades ===")
            return
        print(f"\n[{datetime.datetime.now()}] === Open Trades ===")
        print(f"{'Symbol':<8} {'Qty':<8} {'Side':<6} {'Market Value':<15} {'Unrealized P/L':<15}")
        for pos in positions:
            print(f"{pos.symbol:<8} {pos.qty:<8} {pos.side:<6} {pos.market_value:<15} {pos.unrealized_pl:<15}")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Error fetching open trades: {e}")
import alpaca_trade_api as tradeapi
import pandas as pd
import time
import datetime
import os

# =========================
# 🔐 Alpaca API Credentials
# =========================
API_KEY = 'PK6NP9PMA73CZ4XD7LOE'
API_SECRET = 'buL8PWH2PbE1bjCQIhekJ4jPWF3Zn8hicJrIGYCR'
BASE_URL = 'https://paper-api.alpaca.markets'  # Paper trading URL

# ===================
# ⚙️ Configuration
# ===================
SYMBOLS = [
    'AAPL', 'MSFT', 'AMZN', 'GOOG', 'META', 'NVDA', 'TSLA', 'BRK.B', 'UNH', 'V',
    'JPM', 'XOM', 'MA', 'LLY', 'AVGO', 'HD', 'PG', 'CVX', 'COST', 'ABBV',
    'PEP', 'MRK', 'ADBE', 'KO', 'WMT', 'BAC', 'MCD', 'CSCO', 'ACN', 'ABT',
    'DHR', 'TMO', 'LIN', 'VZ', 'DIS', 'NKE', 'TXN', 'NEE', 'ORCL', 'PM',
    'AMGN', 'MDT', 'CRM', 'HON', 'UNP', 'QCOM', 'BMY', 'LOW', 'MS'
]  # Top 50 large-cap US stocks (IEX-compatible as possible)
MAX_INVEST_PER_STOCK = 1000  # Max $1,000 per stock
LOG_FILE = 'trade_log.csv'

# ===================
# 📡 Connect to Alpaca
# ===================
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version='v2')

# ===================
# 📊 Get Historical Data
# ===================
def fetch_data(symbol):
    # Try new API: pass a list of symbols
    try:
        from alpaca_trade_api.rest import TimeFrame
        bars = api.get_bars([symbol], TimeFrame.Day, limit=100)
        print(f"[DEBUG] Raw bars object for {symbol}: {bars}")
        if hasattr(bars, 'df'):
            df = bars.df
            if symbol in df['symbol'].unique():
                df = df[df['symbol'] == symbol]
            df.index = pd.to_datetime(df.index)
            print(f"[DEBUG] DataFrame shape for {symbol}: {df.shape}")
            return df
    except Exception as e:
        print(f"[DEBUG] get_bars (list) failed for {symbol}: {e}")

    # Try single symbol (old fallback)
    try:
        bars = api.get_bars(symbol, '1Day', limit=100).df
        bars.index = pd.to_datetime(bars.index)
        print(f"[DEBUG] Fallback DataFrame shape for {symbol}: {bars.shape}")
        return bars
    except Exception as e:
        print(f"[DEBUG] get_bars (single) failed for {symbol}: {e}")

    # Try get_barset (very old API)
    try:
        barset = api.get_barset(symbol, 'day', limit=100)
        bars = barset[symbol]
        data = {
            'time': [bar.t for bar in bars],
            'open': [bar.o for bar in bars],
            'high': [bar.h for bar in bars],
            'low': [bar.l for bar in bars],
            'close': [bar.c for bar in bars],
            'volume': [bar.v for bar in bars],
        }
        df = pd.DataFrame(data)
        df.index = pd.to_datetime(df['time'])
        print(f"[DEBUG] get_barset DataFrame shape for {symbol}: {df.shape}")
        return df
    except Exception as e:
        print(f"[DEBUG] get_barset failed for {symbol}: {e}")
    return pd.DataFrame()  # Return empty DataFrame if all fail


# ===================
# 🤖 Trading Strategy
# ===================
def run_strategy(df, open_positions=None, cash=None):
    # Use shorter SMAs for more frequent signals
    df['SMA5'] = df['close'].rolling(window=5).mean()
    df['SMA15'] = df['close'].rolling(window=15).mean()



    # 🛡️ Prevent index errors if not enough data
    if len(df) < 16 or df['SMA5'].isna().iloc[-2] or df['SMA15'].isna().iloc[-2]:
        print(f"[DEBUG] DataFrame length: {len(df)}")
        print(f"[DEBUG] Last 3 SMA5: {df['SMA5'].tail(3).values}")
        print(f"[DEBUG] Last 3 SMA15: {df['SMA15'].tail(3).values}")
        return 'hold'  # Not enough data to make decision

    # Example: Only buy if you have enough cash, only sell if you have a position
    # (You can expand this logic as needed)
    want_to_buy = df['SMA5'].iloc[-1] > df['SMA15'].iloc[-1]
    want_to_sell = df['SMA5'].iloc[-1] < df['SMA15'].iloc[-1]
    symbol = df.get('symbol', [None]*len(df))[-1] if 'symbol' in df.columns else None
    if open_positions is not None and cash is not None and symbol is not None:
        has_position = symbol in open_positions
        if want_to_buy and float(cash) > 0 and not has_position:
            return 'buy'
        elif want_to_sell and has_position:
            return 'sell'
        else:
            return 'hold'
    # Fallback: original logic
    if want_to_buy:
        return 'buy'
    elif want_to_sell:
        return 'sell'
    else:
        return 'hold'

# ===================
# 💰 Execute Trade
# ===================
def place_order(symbol, action, qty):
    try:
        position = api.get_position(symbol)
        has_position = True
    except:
        has_position = False

    if action == 'buy' and not has_position:
        api.submit_order(symbol=symbol, qty=qty, side='buy', type='market', time_in_force='gtc')
        log_trade(symbol, 'buy')
        print(f"[{datetime.datetime.now()}] {symbol:<5} : Buy executed ({qty} shares)")
    elif action == 'sell' and has_position:
        api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
        log_trade(symbol, 'sell')
        print(f"[{datetime.datetime.now()}] {symbol:<5} : Sell executed ({qty} shares)")
    # No print for hold

# ===================
# 🧾 Trade Logger
# ===================
def log_trade(symbol, action):
    now = datetime.datetime.now()
    log_entry = f"{now},{symbol},{action}\n"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)

# ===================
# 🧪 Main Bot Loop
# ===================
def main():
    import pytz
    eastern = pytz.timezone('US/Eastern')
    while True:
        now = datetime.datetime.now(eastern)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=30, second=0, microsecond=0)
        if not (market_open <= now <= market_close):
            print(f"[{now}] Market is closed. Waiting for open hours (9:30-16:30 ET)...")
            time.sleep(60)
            continue
        print("\n" + "="*80 + "\n")
        # Fetch account info and open positions
        try:
            account = api.get_account()
            cash = float(account.cash)
        except Exception as e:
            print(f"[{datetime.datetime.now()}] Error fetching account info: {e}")
            cash = 0
        try:
            positions = api.list_positions()
            open_positions = {p.symbol: float(p.qty) for p in positions}
        except Exception as e:
            print(f"[{datetime.datetime.now()}] Error fetching open positions: {e}")
            open_positions = {}

        # Print account summary
        print(f"\n[{datetime.datetime.now()}] === Account Summary ===")
        print(f"Cash: ${cash:,.2f}")
        print(f"Open Positions: {open_positions if open_positions else 'None'}")

        print_open_trades()
        all_data = {}
        decisions = []
        holds = []
        # Fetch all bars for all symbols at once using REST API (1Min, 1000 bars)
        bars_data = fetch_bars_rest(SYMBOLS, limit=1000, timeframe='1Min')
        bars_dict = bars_data.get('bars', {}) if bars_data else {}
        for symbol in SYMBOLS:
            try:
                bars = bars_dict.get(symbol, [])
                if not bars:
                    # Silently skip symbols with no data
                    continue
                # Convert to DataFrame
                df = pd.DataFrame(bars)
                # Rename columns to match expected names
                rename_map = {'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'}
                df.rename(columns=rename_map, inplace=True)
                # Convert 't' (timestamp) to datetime index if present
                if 't' in df.columns:
                    df['time'] = pd.to_datetime(df['t'], unit='ms') if df['t'].dtype != object else pd.to_datetime(df['t'])
                    df.set_index('time', inplace=True)
                all_data[symbol] = df.tail(1)
                # Calculate max shares to buy for $1,000 per stock
                latest_price = float(df['close'].iloc[-1]) if not df.empty else 0
                max_qty = int(MAX_INVEST_PER_STOCK // latest_price) if latest_price > 0 else 0
                # Pass open_positions and cash to strategy
                action = run_strategy(df, open_positions=open_positions, cash=cash)
                if action == 'buy' and max_qty > 0:
                    decisions.append(f"{symbol:<5} -> BUY {max_qty}")
                    place_order(symbol, 'buy', max_qty)
                elif action == 'sell':
                    # Sell all shares held for this symbol
                    qty_to_sell = int(open_positions.get(symbol, 0))
                    if qty_to_sell > 0:
                        decisions.append(f"{symbol:<5} -> SELL {qty_to_sell}")
                        place_order(symbol, 'sell', qty_to_sell)
                else:
                    holds.append(f"{symbol:<5}")
            except Exception as e:
                print(f"[{datetime.datetime.now()}] {symbol} Error: {e}")

        # Print all price data together
        print(f"\n[{datetime.datetime.now()}] === Latest Price Data for All Symbols ===")

        def letter_round(val):
            try:
                val = float(val)
            except:
                return str(val)
            if abs(val) >= 1_000_000_000:
                return f"{val/1_000_000_000:.2f}B"
            elif abs(val) >= 1_000_000:
                return f"{val/1_000_000:.2f}M"
            elif abs(val) >= 1_000:
                return f"{val/1_000:.2f}k"
            else:
                return f"{val:.2f}"

        # Standardize column widths
        col_widths = {col: max(10, len(col)) for col in next(iter(all_data.values())).columns}
        symbol_width = 8
        # Precompute max width for each column
        for data in all_data.values():
            for col in data.columns:
                for val in data[col]:
                    rounded = letter_round(val)
                    col_widths[col] = max(col_widths[col], len(rounded)+2)

        # Print header
        header = f"{'Symbol':<{symbol_width}} " + " ".join([f"{col:<{col_widths[col]}}" for col in data.columns])
        print(header)
        # Print rows
        for symbol, data in all_data.items():
            for idx, row in data.iterrows():
                row_str = f"{symbol:<{symbol_width}} " + " ".join([
                    f"{letter_round(row[col]):<{col_widths[col]}}" for col in data.columns
                ])
                print(row_str)

        # Print all decisions together
        print(f"\n[{datetime.datetime.now()}] === Decisions ===")
        for decision in decisions:
            print(decision)
        if holds:
            print(f"\nHOLD: {' '.join(holds)}")

        # Sleep for 30 seconds (for testing/demo purposes)
        time.sleep(120)

# ================
# 🚀 Start the bot
# ================
if __name__ == '__main__':
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("timestamp,symbol,action\n")
    main()
