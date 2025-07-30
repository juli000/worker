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
    # Stocks
    'AAPL', 'MSFT', 'AMZN', 'GOOG', 'META', 'NVDA', 'TSLA', 'BRK.B', 'UNH', 'V',
    'JPM', 'XOM', 'MA', 'LLY', 'AVGO', 'HD', 'PG', 'CVX', 'COST', 'ABBV',
    'PEP', 'MRK', 'ADBE', 'KO', 'WMT', 'BAC', 'MCD', 'CSCO', 'ACN', 'ABT',
    'DHR', 'TMO', 'LIN', 'VZ', 'DIS', 'NKE', 'TXN', 'NEE', 'ORCL', 'PM',
    'AMGN', 'MDT', 'CRM', 'HON', 'UNP', 'QCOM', 'BMY', 'LOW', 'MS',
    # ETFs (add more as needed)
    'SPY', 'QQQ', 'VTI', 'ARKK', 'DIA', 'IWM', 'XLK', 'XLF', 'XLE', 'XLV',
    # Crypto (Alpaca format)
    'BTCUSD', 'ETHUSD', 'SOLUSD', 'DOGEUSD', 'LTCUSD', 'ADAUSD', 'AVAXUSD', 'MATICUSD', 'BCHUSD', 'DOTUSD'
]  # Top stocks, ETFs, and crypto pairs
MAX_INVEST_PER_STOCK = 10000 #Max $5,000 per stock
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
    # Relative Volume & Price Action Breakout Strategy with bankroll/risk management
    if len(df) < 21:
        return 'hold', 0
    last_close = df['close'].iloc[-1]
    prev_high = df['high'].iloc[-21:-1].max()
    prev_low = df['low'].iloc[-21:-1].min()
    last_volume = df['volume'].iloc[-1]
    avg_volume = df['volume'].iloc[-21:-1].mean()
    rel_volume = last_volume / avg_volume if avg_volume > 0 else 1
    symbol = df.get('symbol', [None]*len(df))[-1] if 'symbol' in df.columns else None
    has_position = symbol in open_positions if open_positions else False

    # Dynamic max invest per stock: 20% of current cash
    max_invest_per_stock = float(cash) * 0.2 if cash else 0

    # Buy: price breakout above prev_high AND relative volume spike
    if last_close > prev_high and rel_volume > 1.5 and not has_position and float(cash) > 0:
        breakout_strength = (last_close - prev_high) / prev_high
        strength = breakout_strength * rel_volume
        # Only take trades with expected move >= 0.5%
        if strength >= 0.005:
            invest_amount = min(max_invest_per_stock, float(cash) * min(1, strength * 2))
            size = int(invest_amount // last_close)
            return 'buy', size
        else:
            return 'hold', 0
    # Sell: price breakdown below prev_low OR volume collapse
    elif (last_close < prev_low or rel_volume < 0.5) and has_position:
        position_size = int(open_positions.get(symbol, 0))
        if last_close < prev_low:
            size = position_size
        else:
            size = max(1, position_size // 2)
        return 'sell', size
    else:
        return 'hold', 0

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
        print(f"[{datetime.datetime.now().replace(microsecond=0)}] {symbol:<5} : Buy executed ({qty} shares)")
    elif action == 'sell' and has_position:
        api.submit_order(symbol=symbol, qty=qty, side='sell', type='market', time_in_force='gtc')
        log_trade(symbol, 'sell')
        print(f"[{datetime.datetime.now().replace(microsecond=0)}] {symbol:<5} : Sell executed ({qty} shares)")
    # No print for hold

# ===================
# 🧾 Trade Logger
# ===================
def log_trade(symbol, action):
    now = datetime.datetime.now().replace(microsecond=0)
    log_entry = f"{now},{symbol},{action}\n"

    with open(LOG_FILE, 'a') as f:
        f.write(log_entry)

# ===================
# 🧪 Main Bot Loop
# ===================
def main():
    import pytz
    eastern = pytz.timezone('US/Eastern')
    daily_start_value = None
    while True:
        now = datetime.datetime.now(eastern)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=30, second=0, microsecond=0)
        if not (market_open <= now <= market_close):
            print(f"[{now}] Market is closed. Waiting for open hours (9:30-16:30 ET)...")
            time.sleep(30)
            continue
        # Fetch account info and open positions
        account = None
        for attempt in range(4):
            try:
                account = api.get_account()
                cash = float(account.cash)
                equity = float(getattr(account, 'equity', cash))
                break
            except Exception as e:
                if attempt < 3:
                    print(f"Error fetching account info: {e}. Sleeping 3 seconds and retrying {3-attempt} more time(s)...")
                    time.sleep(3)
                else:
                    print(f"Failed to fetch account info after 4 attempts: {e}")
                    cash = 0
                    equity = 0
        if daily_start_value is None:
            daily_start_value = equity
        try:
            positions = api.list_positions()
            open_positions = {p.symbol: float(p.qty) for p in positions}
        except Exception:
            open_positions = {}

        bars_data = fetch_bars_rest(SYMBOLS, limit=1000, timeframe='1Min')
        bars_dict = bars_data.get('bars', {}) if bars_data else {}
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
                latest_price = float(df['close'].iloc[-1]) if not df.empty else 0

                # Get unrealized P/L for this symbol if position exists
                unrealized_pl = None
                if symbol in open_positions:
                    try:
                        position = next((p for p in positions if p.symbol == symbol), None)
                        if position:
                            unrealized_pl = float(position.unrealized_pl)
                    except Exception:
                        unrealized_pl = None

                action, size = run_strategy(df, open_positions=open_positions, cash=cash, unrealized_pl=unrealized_pl)
                if action == 'buy' and size > 0:
                    place_order(symbol, 'buy', size)
                elif action == 'sell' and size > 0:
                    place_order(symbol, 'sell', size)
            except Exception as e:
                print(f"[{datetime.datetime.now().replace(microsecond=0)}] {symbol} Error: {e}")

        # Print total unrealized P&L and check daily profit
        total_unrealized_pl = 0.0
        try:
            positions = api.list_positions()
            for p in positions:
                try:
                    total_unrealized_pl += float(p.unrealized_pl)
                except Exception:
                    pass
        except Exception:
            pass
        daily_profit = equity - daily_start_value
        print(f"[{datetime.datetime.now().replace(microsecond=0)}] Total Unrealized P&L: ${total_unrealized_pl:.2f} | Daily Profit: ${daily_profit:.2f} ({(daily_profit/daily_start_value*100 if daily_start_value else 0):.2f}%)")
        # Stop trading for the day if 1% profit reached
        if daily_start_value and daily_profit/daily_start_value >= 0.01:
            print(f"[{datetime.datetime.now().replace(microsecond=0)}] Target reached (1% daily gain). Pausing trading until tomorrow.")
            while True:
                time.sleep(60)

        # Check for user input to sell all positions
        import sys
        user_input = None
        try:
            import msvcrt
            start = time.time()
            while time.time() - start < 15:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch.lower() == 's':
                        user_input = 's'
                        break
                time.sleep(0.1)
        except ImportError:
            # Non-Windows fallback
            import select
            i, o, e = select.select([sys.stdin], [], [], 15)
            if i:
                user_input = sys.stdin.readline().strip().lower()

        if user_input == 's':
            try:
                positions = api.list_positions()
                for p in positions:
                    qty = int(float(p.qty))
                    if qty > 0:
                        place_order(p.symbol, 'sell', qty)
                print(f"[{datetime.datetime.now().replace(microsecond=0)}] All positions sold.")
            except Exception as e:
                print(f"[{datetime.datetime.now().replace(microsecond=0)}] Error selling all: {e}")

# ================
# 🚀 Start the bot
# ================
if __name__ == '__main__':
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("timestamp,symbol,action\n")
    main()
