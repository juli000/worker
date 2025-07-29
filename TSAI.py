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
        # Sort positions by unrealized profit descending
        sorted_positions = sorted(positions, key=lambda p: float(getattr(p, 'unrealized_pl', 0)), reverse=True)
        for pos in sorted_positions:
            print(f"{pos.symbol:<8} {pos.qty:<8} {pos.side:<6} {pos.market_value:<15} {pos.unrealized_pl:<15}")
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Error fetching open trades: {e}")

from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
import pandas as pd
import time
import datetime
import os

load_dotenv()

# =========================
# 🔐 Alpaca API Credentials (from .env)
# =========================
API_KEY = os.getenv('API_KEY')
API_SECRET = os.getenv('API_SECRET')
BASE_URL = os.getenv('BASE_URL')

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
MAX_INVEST_PER_STOCK = 5000  # Max $5,000 per stock
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
def run_strategy(df, open_positions=None, cash=None, unrealized_pl=None):
    # Use shorter SMAs for more frequent signals
    df['SMA5'] = df['close'].rolling(window=5).mean()
    df['SMA15'] = df['close'].rolling(window=15).mean()

    # 🛡️ Prevent index errors if not enough data
    if len(df) < 16 or df['SMA5'].isna().iloc[-2] or df['SMA15'].isna().iloc[-2]:
        return 'hold'  # Not enough data to make decision

    want_to_buy = df['SMA5'].iloc[-1] > df['SMA15'].iloc[-1]
    want_to_sell = df['SMA5'].iloc[-1] < df['SMA15'].iloc[-1]
    symbol = df.get('symbol', [None]*len(df))[-1] if 'symbol' in df.columns else None
    has_position = symbol in open_positions if open_positions else False

    # Only sell if SMA condition AND unrealized P/L is positive
    if want_to_buy and float(cash) > 0 and not has_position:
        return 'buy'
    elif want_to_sell and has_position and unrealized_pl is not None and float(unrealized_pl) > 0:
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

        # ...existing code...
        # Print account summary at the very end, after all other output
        print(f"\n" + "="*40)
        print(f"[{datetime.datetime.now()}] ACCOUNT SUMMARY")
        invested_amount = 0.0
        num_positions = 0
        for p in positions:
            try:
                invested_amount += float(p.market_value)
                num_positions += 1
            except Exception:
                pass
        try:
            buying_power = float(getattr(account, 'buying_power', 0))
        except Exception:
            buying_power = 0.0
        try:
            portfolio_value = float(getattr(account, 'portfolio_value', 0))
        except Exception:
            portfolio_value = 0.0
        # Format and align all numbers
        label_width = 18
        value_width = 15
        print(f"{'Cash:':<{label_width}}{'$':>2}{cash:>{value_width-1},.2f}")
        print(f"{'Invested:':<{label_width}}{'$':>2}{invested_amount:>{value_width-1},.2f}")
        print(f"{'Positions:':<{label_width}}{num_positions:>{value_width}}")
        print(f"{'Buying Power:':<{label_width}}{'$':>2}{buying_power:>{value_width-1},.2f}")
        print(f"{'Portfolio Value:':<{label_width}}{'$':>2}{portfolio_value:>{value_width-1},.2f}")

        # Print total unrealized profit for all open positions
        total_unrealized_profit = 0.0
        try:
            for p in positions:
                try:
                    total_unrealized_profit += float(p.unrealized_pl)
                except Exception:
                    pass
            print(f"Total Unrealized Profit: ${total_unrealized_profit:,.2f}")
        except Exception:
            print("Could not calculate total unrealized profit.")
        print("-"*40)

        print_open_trades()
        all_data = {}
        decisions = []
        holds = []
        total_buy_cost = 0.0
        buy_details = []
        # Fetch all bars for all symbols at once using REST API (1Min, 1000 bars)
        bars_data = fetch_bars_rest(SYMBOLS, limit=1000, timeframe='1Min')
        bars_dict = bars_data.get('bars', {}) if bars_data else {}
        action_taken = set()
        for symbol in SYMBOLS:
            try:
                bars = bars_dict.get(symbol, [])
                if not bars:
                    continue
                df = pd.DataFrame(bars)
                rename_map = {'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'}
                df.rename(columns=rename_map, inplace=True)
                if 't' in df.columns:
                    df['time'] = pd.to_datetime(df['t'], unit='ms') if df['t'].dtype != object else pd.to_datetime(df['t'])
                    df.set_index('time', inplace=True)
                all_data[symbol] = df.tail(1)
                latest_price = float(df['close'].iloc[-1]) if not df.empty else 0
                max_qty = int(MAX_INVEST_PER_STOCK // latest_price) if latest_price > 0 else 0

                # Get unrealized P/L for this symbol if position exists
                unrealized_pl = None
                if symbol in open_positions:
                    try:
                        position = next((p for p in positions if p.symbol == symbol), None)
                        if position:
                            unrealized_pl = float(position.unrealized_pl)
                    except Exception:
                        unrealized_pl = None

                action = run_strategy(df, open_positions=open_positions, cash=cash, unrealized_pl=unrealized_pl)
                if action == 'buy' and max_qty > 0:
                    buy_cost = latest_price * max_qty
                    total_buy_cost += buy_cost
                    buy_details.append(f"{symbol}: {max_qty} @ ${latest_price:.2f} = ${buy_cost:.2f}")
                    decisions.append(f"{symbol:<5} -> BUY {max_qty}")
                    place_order(symbol, 'buy', max_qty)
                    action_taken.add(symbol)
                elif action == 'sell':
                    qty_available = int(open_positions.get(symbol, 0))
                    if qty_available > 0:
                        decisions.append(f"{symbol:<5} -> SELL {qty_available}")
                        place_order(symbol, 'sell', qty_available)
                        action_taken.add(symbol)
                else:
                    holds.append(f"{symbol:<5}")
            except Exception as e:
                print(f"[{datetime.datetime.now()}] {symbol} Error: {e}")

        # Ensure all open positions are shown as HOLD if no action was taken
        for symbol in open_positions:
            if symbol not in action_taken and f"{symbol:<5}" not in holds:
                holds.append(f"{symbol:<5}")

        # Do not print price data as requested

        # After all buys, print buy details and total buy cost
        if buy_details:
            print("\n" + "="*40)
            print("BUY SUMMARY")
            print("-"*40)
            print(f"{'Symbol':<8} {'Qty':<6} {'Price':<10} {'Total':<12}")
            for detail in buy_details:
                # detail format: "{symbol}: {max_qty} @ ${latest_price:.2f} = ${buy_cost:.2f}"
                parts = detail.split(':')
                symbol = parts[0]
                rest = parts[1].strip().split(' ')
                qty = rest[0]
                price = rest[2]
                total = rest[-1]
                print(f"{symbol:<8} {qty:<6} {price:<10} {total:<12}")
            print("-"*40)
            print(f"Total Buy Cost This Iteration: ${total_buy_cost:.2f}")
            print("="*40)

        # Print only actual actions taken (buy/sell) for this iteration
        print("\n" + "="*40)
        print(f"[{datetime.datetime.now()}] DECISIONS")
        print("-"*40)
        # Remove duplicates and only print actions that occurred
        printed = set()
        for decision in decisions:
            if decision not in printed:
                print(decision)
                printed.add(decision)
        print("="*40)

        print(f"[{datetime.datetime.now()}] Loop complete. Sleeping before next iteration...")
        # Sleep for 2 minutes (for testing/demo purposes)
        time.sleep(120)

# ================
# 🚀 Start the bot
# ================
if __name__ == '__main__':
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("timestamp,symbol,action\n")
    main()
