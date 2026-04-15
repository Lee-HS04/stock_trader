import json
import argparse
import os

# The path where we store user limits (store in Docker volume)
CONFIG_PATH = "config.json"
account = "account.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        # Default limits if the user hasn't set any yet
        return {
            "initial_balance": 100000.00,
            "max_per_trade": 10000.00,
            "total_budget": 50000.00,
            "current_invested": 0.00,
            "blacklist": []
        }
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def check_trade(proposal_json):
    config = load_config()
    try:
        proposal = json.loads(proposal_json)
        firm = proposal['firm']
        trade_amount = proposal['amount']
        proposed_price = proposal['proposed_price']
        actual_price = proposal['actual_price']
        action = proposal['action']
    except KeyError as e:
        return {"status": "FAILURE", "reason": f"Invalid JSON, missing field:{str(e)}"}
    except json.JSONDecodeError as e:
        return {"status": "FAILURE", "reason":"Malformed JSON provided"}
    if os.path.exists(account):
        try:
            with open(account, "r") as file:
                account_data = json.load(file)
            config["current_invested"] = round(config["initial_balance"] - account_data.get("balance"),2)
        except Exception as e:
            return {"status": "REJECTED", "reason": f"System Busy: Could not verify account state ({str(e)})"}
    else:
        pass
    
    # Check Blacklist
    if firm in config['blacklist']:
        return {"status": "REJECTED", "reason": f"{firm} is on your blacklist."}

    if action == "sell":
        trade_amount *= -1
    elif action == "buy":
        # Check Single Transaction Limit
        if trade_amount > config['max_per_trade']:
            return {"status": "REJECTED", "reason": f"Trade amount ${trade_amount} exceeds your per-trade limit of ${config['max_per_trade']}."}
    else:
        return {"status": "REJECTED", "reason": "Action must be 'buy' or 'sell'"} 
    # Check Total Budget Limit
    if (config['current_invested'] + trade_amount) > config['total_budget']:
        return {"status": "REJECTED", "reason": f"Trade would exceed your total budget of ${config['total_budget']}."}

    # Check Price Hallucination (Safety gap of 5%)
    # This ensures the price suggested by the LLM at which to buy/sell matches the price given to it by trader.py and is not something it changed or hallucinated in order to pass our checks
    price_error = abs(proposed_price - actual_price)
    if price_error > (actual_price * 0.05):
        return {"status": "REJECTED", "reason": "Data integrity error: Price discrepancy too high."}

    return {"status": "APPROVED", "reason": "Trade is within safety parameters."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # The LLM passes its plan as a JSON string
    parser.add_argument("--proposal", required=True)
    args = parser.parse_args()
    
    result = check_trade(args.proposal)
    print(json.dumps(result))