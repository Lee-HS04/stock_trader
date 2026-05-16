from massive import RESTClient
import pandas as pd
import pandas_ta as ta
import argparse
import json
import os
import glob
from datetime import datetime
from dateutil.relativedelta import relativedelta

API_KEY = os.getenv("MASSIVE_API_KEY") 
client = RESTClient(API_KEY)

def get_historical_data(firm, benchmark="SPY", unit="years", value="1", backtest=False, target_date=None):
    val = int(value) if value else 1
    unit = unit if unit else "years"
    prd = {unit: val}
    
    # Set the 'current' date context
    if backtest and target_date:
        to_date = pd.to_datetime(target_date)
    else:
        to_date = datetime.now()
    from_date = to_date - relativedelta(**prd)

    if backtest:
        # --- BACKTEST MODE: LOAD FROM STOCKBENCH FILES ---
        def load_parquet_data(ticker):
            path = f"parquet/{ticker}/day/"
            if not os.path.exists(path):
                raise FileNotFoundError(f"Parquet data missing for {ticker} at {path}")
            
            df = pd.read_parquet(path)
            # Standardize index to datetime
            if 'Date' in df.columns:
                df.set_index(pd.to_datetime(df['Date']), inplace=True)
            else:
                df.index = pd.to_datetime(df.index)
            
            df.sort_index(inplace=True)
            df.columns = [c.lower() for c in df.columns] # Ensure 'close' is lowercase
            return df.loc[df.index <= to_date].copy()

        info = load_parquet_data(firm)
        bench_info = load_parquet_data(benchmark)

        # Load Fundamentals from cache
        date_str = to_date.strftime("%Y-%m-%d")
        # Pattern search for JSON: stock_indicators often named like {TICKER}_{DATE}.json
        json_pattern = f"stock_indicators/*{firm}*{date_str}*.json"
        found_files = glob.glob(json_pattern)
        
        fundamentals = {}
        if found_files:
            with open(found_files[0], 'r') as f:
                fundamentals = json.load(f)
        
        return info, bench_info, fundamentals

    else:
        # --- LIVE MODE: LOAD FROM MASSIVE API ---
        aggs = client.get_aggs(firm, 1, "day", from_date, to_date)
        info = pd.DataFrame([vars(x) for x in aggs])
        info['timestamp'] = pd.to_datetime(info['timestamp'], unit='ms')
        info.set_index('timestamp', inplace=True)
        # Ensure columns are lowercase
        info.columns = [c.lower() for c in info.columns]
        
        bench_aggs = client.get_aggs(benchmark, 1, "day", from_date, to_date)
        bench_info = pd.DataFrame([vars(x) for x in bench_aggs])
        bench_info['timestamp'] = pd.to_datetime(bench_info['timestamp'], unit='ms')
        bench_info.set_index('timestamp', inplace=True)
        bench_info.columns = [c.lower() for c in bench_info.columns]
        
        return info, bench_info, {} # No fundamental JSON in live mode

def calculate_indicators(firm, info, bench_info, fundamentals, rsi_p=14, ema_p=20, sma_p=100): 
    """
    This function is now data-source agnostic. 
    It works as long as 'info' and 'bench_info' have a 'close' column.
    """
    if len(info) < 2:
        return json.dumps({"error": f"Insufficient historical data for {firm}."})

    # 1. Technical Analysis (Always uses the 'close' column)
    # pandas_ta automatically looks for 'close' in lowercase
    info['RSI'] = ta.rsi(info['close'], length=rsi_p or 14)
    info['EMA'] = ta.ema(info['close'], length=ema_p or 20)
    info['SMA'] = ta.sma(info['close'], length=sma_p or 100)
    
    # 2. Alpha Calculation
    symbol_return = (info['close'].iloc[-1] / info['close'].iloc[-2]) - 1
    bench_return = (bench_info['close'].iloc[-1] / bench_info['close'].iloc[-2]) - 1
    alpha = symbol_return - bench_return
    
    # 3. Formulate Output
    # If fundamentals is empty (Live mode), it just returns an empty dict for that key
    result = {
        "ticker": firm,
        "date": info.index[-1].strftime("%Y-%m-%d"),
        "technical_analysis": {
            "latest_closing_price": float(info['close'].iloc[-1]),
            "rsi": float(info['RSI'].iloc[-1]) if not pd.isna(info['RSI'].iloc[-1]) else None,
            "ema": float(info['EMA'].iloc[-1]) if not pd.isna(info['EMA'].iloc[-1]) else None,
            "sma": float(info['SMA'].iloc[-1]) if not pd.isna(info['SMA'].iloc[-1]) else None,
            "alpha": float(alpha)
        },
        "fundamental_data": fundamentals 
    }
    
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--firm", type=str, required=True)
    parser.add_argument("--unit", type=str, default="years")
    parser.add_argument("--period", type=str, default="1")
    parser.add_argument("--benchmark", type=str, default="SPY")
    parser.add_argument("--rsi", type=int)
    parser.add_argument("--ema", type=int)
    parser.add_argument("--sma", type=int)
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--date", type=str, help="YYYY-MM-DD (Required for backtest)")
    
    args = parser.parse_args()
    
    try:
        # Retrieve the data
        info, bench_info, fundamentals = get_historical_data(
            args.firm, args.benchmark, args.unit, args.period, args.backtest, args.date
        )
        
        # Calculate and print JSON for LLM
        print(calculate_indicators(
            args.firm, info, bench_info, fundamentals, 
            args.rsi, args.ema, args.sma
        ))
        
    except Exception as e:
        # Ensure errors are returned as JSON so the agent can understand them
        print(json.dumps({"error": str(e)}))