
import re

with open("backend/audit_logic.py", "r", encoding="utf-8") as f:
    text = f.read()

text = "from backend.squad_logic import get_player_img_url, fmt_num, SILHOUETTE_BASE64, fetch_manager_entry, fetch_manager_picks, get_rolling_player_metrics\nfrom backend.data import get_manager_squad_ids, calculate_projected_points, get_fixture_for_team, get_historical_player_baselines, get_teams_fdr_map, solve_optimal_xi\n" + text

with open("backend/audit_logic.py", "w", encoding="utf-8") as f:
    f.write(text)

