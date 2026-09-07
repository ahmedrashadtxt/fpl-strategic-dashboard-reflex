
import re

with open("tabs/transfer_market.py", "r", encoding="utf-8") as f:
    text = f.read()

# Extract the two functions up to @st.fragment
match = re.search(r"(def apply_target_market_projection.*?)(?=@st\.fragment)", text, re.DOTALL)
if match:
    func_text = match.group(1)
    
    # Strip out @st.cache_data
    func_text = re.sub(r"@st\.cache_data.*?\n", "", func_text)
    
    with open("backend/market_logic.py", "w", encoding="utf-8") as out:
        out.write("""import math
import pandas as pd
from rapidfuzz import fuzz, process

from backend.betting_engine import fetch_upcoming_betting_odds, get_fixture_market_xg_and_movement
from backend.data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_manager_squad_ids,
)

""")
        out.write(func_text)
    print("Market logic written.")
else:
    print("Match not found.")

