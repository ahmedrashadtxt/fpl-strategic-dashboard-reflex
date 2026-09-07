
import re

with open("fpl_strategic_dashboard_reflex/state.py", "r", encoding="utf-8") as f:
    text = f.read()

# Remove import
text = text.replace("    get_summary_stats,\n", "")

# Remove variables in AppState
vars_block = """    # ── Summary Stats ──────────────────────────────────────────────────
    total_players: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    heating_transfers: int = 0
    cooling_transfers: int = 0
"""
text = text.replace(vars_block, "")

# Remove execution
exec_block = """            summary_df = get_summary_stats(conn)
            if not summary_df.empty:
                row = summary_df.iloc[0]
                self.total_players = int(row.get("total", 0) or 0)
                self.buy_signals = int(row.get("buys", 0) or 0)
                self.sell_signals = int(row.get("sells", 0) or 0)
                self.heating_transfers = int(row.get("heating", 0) or 0)
                self.cooling_transfers = int(row.get("cooling", 0) or 0)"""
text = text.replace(exec_block, "")

with open("fpl_strategic_dashboard_reflex/state.py", "w", encoding="utf-8") as f:
    f.write(text)

