import json
import argparse
import os

# The path where we store user limits (should be in your Docker volume)
CONFIG_PATH = "config.json"

def load_config():
    """Loads user-defined safety limits."""
    if not os.path.exists(CONFIG_PATH):
        # Default limits if the user hasn't set any yet
        return {
            "max_per_trade": 1000.0,
            "total_budget": 5000.0,
            "current_invested": 0.0,
            "blacklist": []
        }
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def check_trade(proposal_json):
    config = load_config()
    proposal = json.loads(proposal_json)
    
    firm = proposal['firm']
    trade_amount = proposal['amount']
    
    # Check Blacklist
    if firm in config['blacklist']:
        return {"status": "REJECTED", "reason": f"{firm} is on your blacklist."}

    # Check Single Transaction Limit
    if trade_amount > config['max_per_trade']:
        return {"status": "REJECTED", "reason": f"Trade amount ${trade_amount} exceeds your per-trade limit of ${config['max_per_trade']}."}

    # Check Total Budget Limit
    if (config['current_invested'] + trade_amount) > config['total_budget']:
        return {"status": "REJECTED", "reason": f"Trade would exceed your total budget of ${config['total_budget']}."}

    # Check Price Hallucination (Safety gap of 5%)
    # This ensures the price suggested by the LLM at which to buy/sell matches the price given to it by trader.py and is not something it changed or made up to pass our checks
    price_error = abs(proposal['proposed_price'] - proposal['actual_price'])
    if price_error > (proposal['actual_price'] * 0.05):
        return {"status": "REJECTED", "reason": "Data integrity error: Price discrepancy too high."}

    return {"status": "APPROVED", "reason": "Trade is within safety parameters."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # The LLM passes its plan as a JSON string
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args()
    
    result = check_trade(args.proposal)
    print(json.dumps(result))