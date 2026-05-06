#!/usr/bin/env python3
import os
import json
import argparse
from datetime import datetime, timezone, timedelta
from collections import Counter

# --- CONFIGURATION ---
SHORT_TERM_MEMORY_FILE = "short_term_memory.json"
RISK_LOG_FILE = "risk_log.json"
SURPRISE_THRESHOLD = 3.0  
DECAY_RATE = 0.10         
PRUNE_THRESHOLD = 0.5     

def load_json(filepath, default_state):
    if not os.path.exists(filepath): return default_state
    try:
        with open(filepath, 'r') as f: return json.load(f)
    except: return default_state

def save_json(filepath, data):
    with open(filepath, 'w') as f: json.dump(data, f, indent=4)

def calculate_surprise(price, ma):
    if not ma or ma == 0: return 0.0
    return round((abs(price - ma) / ma) * 100, 4)

def decay_memory(memory_list):
    """MIRAS Retention Gate: Continuous weight decay for all associative pairs."""
    for item in memory_list:
        item['importance_score'] = round(item['importance_score'] * (1.0 - DECAY_RATE), 4)
    return [i for i in memory_list if i['importance_score'] >= PRUNE_THRESHOLD]

def get_miras_hierarchy_summary(args):
    """Produces the 3-Level MIRAS Scene Summary for the Agent."""
    memory = load_json(SHORT_TERM_MEMORY_FILE, [])
    risks = load_json(RISK_LOG_FILE, [])
    
    # --- LEVEL 1: MACRO REGIME ---
    macro_status = "UNKNOWN (Data Missing)"
    if args.spy_price and args.spy_ma:
        regime = "BULLISH" if args.spy_price > args.spy_ma else "BEARISH/VOLATILE"
        diff = ((args.spy_price - args.spy_ma) / args.spy_ma) * 100
        macro_status = f"{regime} (SPY is {diff:.2f}% relative to 200MA)"

    # --- LEVEL 2: EPISODIC TREND (Ticker Specific) ---
    ticker_mem = [m for m in memory if m.get('ticker') == args.ticker]
    # Filter for last 14 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    recent_mem = [m for m in ticker_mem if datetime.fromisoformat(m['timestamp']) > cutoff]
    
    if recent_mem:
        actions = [m.get('action', 'SKIP') for m in recent_mem]
        predominant_action = Counter(actions).most_common(1)[0][0]
        avg_surprise = sum(m['surprise_score'] for m in recent_mem) / len(recent_mem)
        episodic_report = f"Trend for {args.ticker}: Mostly '{predominant_action}'. Avg Surprise: {avg_surprise:.2f}%."
    else:
        episodic_report = f"No episodic data for {args.ticker} in the last 14 days."

    # --- LEVEL 3: GRANULAR SHOCKS (High Surprise Risks) ---
    # Sort risks by surprise score
    top_shocks = sorted(risks, key=lambda x: x['data']['surprise_score'], reverse=True)[:3]
    shock_list = []
    for s in top_shocks:
        r_ticker = s['data']['ticker']
        # Categorize: Systemic (Indices/Macro) vs Idiosyncratic (Specific Stock)
        cat = "SYSTEMIC" if r_ticker in ['SPY', 'QQQ', 'BTC'] else "IDIOSYNCRATIC"
        shock_list.append(f"- [{cat}] {r_ticker}: {s['data']['surprise_score']}% shock at {s['data']['timestamp'][:10]}")
    
    granular_report = "\n".join(shock_list) if shock_list else "No recent granular shocks recorded."

    # Final Structured Scene Summary
    summary = f"""
=== MIRAS HIERARCHY SCENE SUMMARY ===
LEVEL 1: MACRO REGIME
Status: {macro_status}

LEVEL 2: EPISODIC TREND
{episodic_report}

LEVEL 3: GRANULAR SHOCKS
{granular_report}
=====================================
    """
    return summary

def process_market_data(args):
    memory = load_json(SHORT_TERM_MEMORY_FILE, [])
    memory = decay_memory(memory)
    
    surprise_score = calculate_surprise(args.price, args.ma)
    event_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": args.ticker,
        "current_price": args.price,
        "moving_average": args.ma,
        "surprise_score": surprise_score,
        "importance_score": surprise_score * 2,
        "action": args.action,
        "reason": args.reason
    }

    if surprise_score >= SURPRISE_THRESHOLD:
        risk_log = load_json(RISK_LOG_FILE, [])
        risk_log.append({"alert": "MIRAS_SHOCK", "data": event_data})
        save_json(RISK_LOG_FILE, risk_log)

    memory.append(event_data)
    save_json(SHORT_TERM_MEMORY_FILE, memory)
    return {"status": "success", "surprise": surprise_score}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MIRAS Hierarchical Memory")
    parser.add_argument("--query", action="store_true")
    parser.add_argument("--ticker", type=str, required=True)
    parser.add_argument("--price", type=float)
    parser.add_argument("--ma", type=float)
    parser.add_argument("--spy_price", type=float)
    parser.add_argument("--spy_ma", type=float)
    parser.add_argument("--action", type=str, default="SKIP")
    parser.add_argument("--reason", type=str, default="No reason provided.")
    
    args = parser.parse_args()

    if args.query:
        print(get_miras_hierarchy_summary(args))
    else:
        if args.price is None or args.ma is None:
            print("Error: --price and --ma required for logging.")
        else:
            print(json.dumps(process_market_data(args), indent=2))