import sqlite3
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

class IntegratedQuantitativeAuditor:
    def __init__(self, db_path="trade_history.db", account_path="account.json", peers_path="competitors.json"):
        self.db_path = db_path
        self.account_path = account_path
        self.peers_path = peers_path
        self.initial_capital = 100000.0

    def _get_internal_performance(self):
        """Pulls the ground truth from your local database and account files."""
        try:
            # 1. Get current balance from account.json
            with open(self.account_path, 'r') as f:
                account = json.load(f)
            current_balance = account.get("current_balance", self.initial_capital)
            total_return = (current_balance - self.initial_capital) / self.initial_capital

            # 2. Get trade history from SQLite
            conn = sqlite3.connect(self.db_path)
            # Assuming table 'trades' with columns: timestamp, pnl, symbol
            df = pd.read_sql_query("SELECT * FROM trades", conn)
            conn.close()

            hit_rate = (df['pnl'] > 0).mean() if not df.empty else 0
            trade_count = len(df)

            return {
                "return": total_return,
                "hit_rate": hit_rate,
                "count": trade_count,
                "raw_df": df
            }
        except Exception as e:
            print(f"Internal Data Error: {e}")
            return {"return": 0.0, "hit_rate": 0, "count": 0}

    def _get_external_peers(self):
        """Loads the live rankings updated by the Massive API script."""
        try:
            with open(self.peers_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def generate_audit_report(self):
        # 1. Fetch data from the DB and Peers
        agent = self._get_internal_performance()
        peers = self._get_external_peers()

        if not peers:
            return "Audit Error: competitors.json not found. Run update_peers.py first."

        # 2. Extract specific mirrors
        master = peers.get("Strategic_Master", {"return": 0.06})
        sprinter = peers.get("Tactical_AI_Sprinter", {"return": 0.12})
        market = peers.get("Market_Baseline", {"return": 0.04})

        # 3. Differential Critique Logic (The "Self-Judging" Brain)
        critique_points = []
        
        # Scenario: Underperforming the Masters (Robustness check)
        if agent['return'] < master['return']:
            critique_points.append(
                f"You are failing the 'Robustness' test. Legendary traders ({master['name']}) are outperforming you by "
                f"{(master['return'] - agent['return']):.2%}. Your strategy is likely too erratic."
            )
        
        # Scenario: Underperforming the Sprinters (Speed check)
        if agent['return'] < sprinter['return']:
            critique_points.append(
                f"You are failing the 'Speed' test. Current market leaders ({sprinter['name']}) are capturing "
                f"{(sprinter['return'] - agent['return']):.2%} more Alpha. Your entries are likely too lagging."
            )

        # Scenario: High Hit Rate but Low Profit (Risk management check)
        if agent['hit_rate'] > 0.65 and agent['return'] < market['return']:
            critique_points.append(
                "Warning: You have a high Hit Rate but low Market Alpha. You are 'picking up pennies.' "
                "Your winners are too small, or your losers are too large."
            )

        # 4. Final Rankings for the Leaderboard
        leaderboard = [
            {"name": sprinter['name'], "return": f"{sprinter['return']:.2%}", "rank": 1},
            {"name": master['name'], "return": f"{master['return']:.2%}", "rank": 2},
            {"name": "YOU (Agent)", "return": f"{agent['return']:.2%}", "rank": 3 if agent['return'] < master['return'] else 1}
        ]

        # 5. Output for the LLM Evolution Loop
        report = {
            "timestamp": datetime.now().isoformat(),
            "internal_metrics": {
                "total_return": f"{agent['return']:.2%}",
                "hit_rate": f"{agent['hit_rate']:.2%}",
                "trades_closed": agent['count']
            },
            "external_comparison": {
                "market_alpha": f"{(agent['return'] - market['return']):.2%}",
                "gap_to_masters": f"{(agent['return'] - master['return']):.2%}",
                "gap_to_sprinters": f"{(agent['return'] - sprinter['return']):.2%}"
            },
            "leaderboard": sorted(leaderboard, key=lambda x: x['return'], reverse=True),
            "expert_critique": " ".join(critique_points) if critique_points else "You are currently dominating both speed and robustness benchmarks.",
            "evolution_prompt": "Based on the critique, which Pillar 3 tool weights will you adjust to climb the leaderboard?"
        }

        return json.dumps(report, indent=4)

if __name__ == "__main__":
    auditor = IntegratedQuantitativeAuditor()
    print(auditor.generate_audit_report())