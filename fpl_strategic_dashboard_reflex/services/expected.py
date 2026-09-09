from fpl_strategic_dashboard_reflex.services.squad import get_player_img_url, fmt_num, SILHOUETTE_BASE64
from fpl_strategic_dashboard_reflex.services.db import get_manager_squad_ids
from fpl_strategic_dashboard_reflex.services.db import get_manager_squad_ids
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

pos_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def get_player_img_url_old(photo, code=None):
    photo_str = str(photo) if pd.notna(photo) else ""
    if not photo_str or "Photo-Missing" in photo_str or photo_str == "None":
        if pd.notna(code) and str(code).strip():
            return f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{int(code)}.png"
        return SILHOUETTE_BASE64

    base_name = photo_str.replace(".jpg", "").replace(".png", "")
    if not base_name.startswith("p"):
        base_name = f"p{base_name}"
    return f"https://resources.premierleague.com/premierleague/photos/players/110x140/{base_name}.png"


def fetch_expected_stats_base_data(_conn, current_gw: int = 1):
    """Fetches player attacking metrics and calculates expected gameweek points (Proj xP)."""
    table_check = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_past_seasons'",
        _conn,
    )
    has_history = not table_check.empty

    hist_join = """
        LEFT JOIN (
            SELECT 
                element_id,
                ROUND((SUM(goals_scored + assists) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_GI_90,
                ROUND((SUM(total_points) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_Pts_90,
                SUM(minutes) AS Career_Mins
            FROM player_past_seasons
            GROUP BY element_id
        ) hist ON p.id = hist.element_id
    """ if has_history else ""

    hist_select = """
        hist.Career_GI_90,
        hist.Career_Pts_90,
        hist.Career_Mins,
    """ if has_history else """
        NULL AS Career_GI_90,
        NULL AS Career_Pts_90,
        NULL AS Career_Mins,
    """

    query = f"""
    SELECT
        p.id AS element_id,
        p.code,
        p.photo,
        p.web_name AS Player,
        p.first_name || ' ' || p.second_name AS Full_Name,
        t.short_name AS Team,
        t.name AS Club_Name,
        CASE p.element_type
            WHEN 1 THEN 'GKP'
            WHEN 2 THEN 'DEF'
            WHEN 3 THEN 'MID'
            WHEN 4 THEN 'FWD'
        END AS Pos,
        p.element_type AS element_type,
        p.now_cost / 10.0 AS Price,
        p.minutes AS Minutes,
        p.total_points AS Total_Points,
        p.goals_scored AS Goals,
        p.assists AS Assists,
        p.clean_sheets AS Clean_Sheets,
        p.saves AS Saves,
        p.expected_goals AS xG,
        p.expected_assists AS xA,
        p.expected_goal_involvements AS xGI,
        p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance,
        {hist_select}
        p.now_cost / 10.0 AS price_val
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    {hist_join}
    """
    df_xgi = pd.read_sql(query, _conn)

    current_season_numeric = [
        "Price", "Minutes", "Total_Points", "Goals", "Assists", "Clean_Sheets",
        "Saves", "xG", "xA", "xGI", "xGI_per_90", "element_type"
    ]
    for col_name in current_season_numeric:
        if col_name in df_xgi.columns:
            df_xgi[col_name] = pd.to_numeric(df_xgi[col_name], errors="coerce").fillna(0)

    career_numeric = ["Career_GI_90", "Career_Pts_90", "Career_Mins"]
    for col_name in career_numeric:
        if col_name in df_xgi.columns:
            df_xgi[col_name] = pd.to_numeric(df_xgi[col_name], errors="coerce")

    completed_gws = max(1, current_gw - 1)
    df_xgi["Avg_Mins_GW"] = (df_xgi["Minutes"] / completed_gws).round(1)

    pos_default_xgi90 = {1: 0.01, 2: 0.08, 3: 0.25, 4: 0.38}

    def calc_proj_xp(row):
        etype = int(row.get("element_type", 3))
        mins = float(row.get("Minutes", 0))
        price = float(row.get("Price", 5.0))
        avg_mins = float(row.get("Avg_Mins_GW", 0))

        # ── 1. Expected Match Minutes Ratio ──
        if current_gw > 1:
            if avg_mins >= 65:
                mins_factor = min(1.0, avg_mins / 90.0)
            elif avg_mins >= 30:
                mins_factor = (avg_mins / 90.0) * 0.85
            elif mins > 0:
                mins_factor = max(0.05, mins / (completed_gws * 90.0))
            else:
                mins_factor = 0.80 if price >= 8.5 else (0.50 if price >= 6.5 else 0.15)
        else:
            mins_factor = 0.90 if price >= 8.0 else (0.75 if price >= 6.0 else 0.50)

        # ── 2. Bayesian Shrinkage on Per-90 Attack Rates ──
        sw = min(1.0, mins / 360.0) if current_gw > 1 else 0.0
        pos_base_xgi = pos_default_xgi90.get(etype, 0.25)

        if mins > 0:
            raw_xg90 = (float(row.get("xG", 0)) / mins) * 90.0
            raw_xa90 = (float(row.get("xA", 0)) / mins) * 90.0
        else:
            raw_xg90 = pos_base_xgi * 0.55
            raw_xa90 = pos_base_xgi * 0.45

        xg90 = (sw * raw_xg90) + ((1.0 - sw) * (pos_base_xgi * 0.55))
        xa90 = (sw * raw_xa90) + ((1.0 - sw) * (pos_base_xgi * 0.45))

        if etype == 4:
            base_xp90 = (xg90 * 4.0) + (xa90 * 3.0) + 2.0
        elif etype == 3:
            base_xp90 = (xg90 * 5.0) + (xa90 * 3.0) + 2.3
        else:
            base_xp90 = (xg90 * 6.0) + (xa90 * 3.0) + 2.0

        status = str(row.get("Status", "a"))
        chance = row.get("Chance")
        if status in ("i", "u", "s"):
            avail = 0.0
        elif pd.notna(chance) and str(chance).strip() not in ("", "None"):
            avail = float(chance) / 100.0
        else:
            avail = 1.0

        return round(max(0.0, base_xp90 * mins_factor * avail), 2)

    def calc_proj_xp_90(row):
        etype = int(row.get("element_type", 3))
        mins = float(row.get("Minutes", 0))
        pos_base_xgi = pos_default_xgi90.get(etype, 0.25)

        sw = min(1.0, mins / 360.0) if current_gw > 1 else 0.0
        if mins > 0:
            raw_xg90 = (float(row.get("xG", 0)) / mins) * 90.0
            raw_xa90 = (float(row.get("xA", 0)) / mins) * 90.0
        else:
            raw_xg90 = pos_base_xgi * 0.55
            raw_xa90 = pos_base_xgi * 0.45

        xg90 = (sw * raw_xg90) + ((1.0 - sw) * (pos_base_xgi * 0.55))
        xa90 = (sw * raw_xa90) + ((1.0 - sw) * (pos_base_xgi * 0.45))

        multiplier = 4.0 if etype == 4 else (5.0 if etype == 3 else 6.0)
        return round((xg90 * multiplier) + (xa90 * 3.0) + 2.0, 2)

    if not df_xgi.empty:
        df_xgi["Proj_Attacking_xP"] = df_xgi.apply(calc_proj_xp, axis=1)
        df_xgi["Proj_Attacking_xP_90"] = df_xgi.apply(calc_proj_xp_90, axis=1)
        df_xgi["Proj_GW_xP"] = df_xgi["Proj_Attacking_xP"]
        df_xgi["Proj_GW_xP_90"] = df_xgi["Proj_Attacking_xP_90"]
        df_xgi = df_xgi.dropna(subset=["Player"])
        df_xgi = df_xgi[df_xgi["Player"].astype(str).str.strip() != ""]

        df_xgi["_search_target"] = (
            df_xgi["Player"].fillna("")
            + " "
            + df_xgi["Full_Name"].fillna("")
            + " "
            + df_xgi["Team"].fillna("")
            + " "
            + df_xgi["Club_Name"].fillna("")
        ).str.strip()

    return df_xgi




def run_expected_analysis(conn, current_gw, manager_id, search_query, min_avg_mins, position_filter, sort_by, max_price, only_my_squad, show_career_baseline):
def run_expected_analysis(
    conn=None,
    current_gw=1,
    manager_id="",
    search_query="",
    min_avg_mins=0,
    position_filter="All",
    sort_by="xGI",
    max_price=15.0,
    only_my_squad=False,
    show_career_baseline=False,
):
    from fpl_strategic_dashboard_reflex.services.expected import fetch_expected_stats_base_data
    from fpl_strategic_dashboard_reflex.services.db import get_manager_squad_ids
    from fpl_strategic_dashboard_reflex.services.db import get_connection, get_manager_squad_ids

    if isinstance(conn, int):
        show_career_baseline = only_my_squad
        only_my_squad = max_price
        max_price = sort_by
        sort_by = position_filter
        position_filter = min_avg_mins
        min_avg_mins = search_query
        search_query = manager_id
        manager_id = current_gw
        current_gw = conn
        conn = get_connection()
    elif conn is None:
        conn = get_connection()
    
    df_raw = fetch_expected_stats_base_data(conn, current_gw)
    if df_raw.empty:
        return None
        
    filtered_df = df_raw.copy()
    
    if position_filter != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == position_filter]
        
    filtered_df = filtered_df[
        (filtered_df["Avg_Mins_GW"] >= min_avg_mins)
        & (filtered_df["Price"] <= max_price)
    ]
    
    if only_my_squad and not filtered_df.empty:
        if not manager_id:
            filtered_df = filtered_df.iloc[0:0]
        else:
            squad_ids = get_manager_squad_ids(manager_id, current_gw)
            filtered_df = filtered_df[filtered_df["element_id"].isin(squad_ids)]
            
    has_search = bool(search_query and search_query.strip())
    
    if has_search and not filtered_df.empty:
        q = search_query.strip()
        search_targets = filtered_df["_search_target"].to_dict()
        results = process.extract(
            q,
            search_targets,
            scorer=fuzz.partial_ratio,
            limit=None,
            score_cutoff=65,
        )
        if results:
            matched_indices = [idx for (_, score, idx) in results]
            filtered_df = filtered_df.loc[matched_indices]
        else:
            filtered_df = filtered_df.iloc[0:0]
            
    if not filtered_df.empty:
        sort_map = {
            "Projected Gameweek xP (Total)": ("Proj_GW_xP", False),
            "Expected Goal Involvement (xGI)": ("xGI", False),
            "Expected Goals (xG)": ("xG", False),
            "Expected Assists (xA)": ("xA", False),
            "Form": ("Form", False),
            "Total Points": ("Total_Points", False),
            "Attacking Return Probability (1+ G/A)": ("Att_Ret_Prob", False),
            "Bonus Points System (BPS)": ("BPS", False),
            "Projected Points / 90": ("Proj_GW_xP_90", False),
            "xGI": ("xGI", False),
            "xG": ("xG", False),
            "xA": ("xA", False),
            "Att_Ret_Prob": ("Att_Ret_Prob", False),
            "BPS": ("BPS", False),
            "Proj_GW_xP": ("Proj_GW_xP", False),
        }
        sort_col, sort_asc = sort_map.get(sort_by, ("Proj_GW_xP", False))
        sort_col, sort_asc = sort_map.get(sort_by, ("xGI", False))
        if sort_col not in filtered_df.columns:
            sort_col = "xGI" if "xGI" in filtered_df.columns else "Total_Points"
        filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)
        
    if filtered_df.empty:
        return {"top_cards": [], "table": []}
        
    top_cards = []
    for _, row in filtered_df.head(4).iterrows():
        top_cards.append({
            "player": row["Player"],
            "team": row["Team"],
            "pos": row["Pos"],
            "price": float(row["Price"]),
            "avg_mins": int(row["Avg_Mins_GW"]),
            "xg": float(row.get("xG", 0.0)),
            "xa": float(row.get("xA", 0.0)),
            "xgi": float(row.get("xGI", 0.0)),
            "pts": int(float(row["Total_Points"])),
            "gw_xp": float(row["Proj_GW_xP"]),
            "img_url": get_player_img_url(row.get("photo"), row.get("code"))
        })
        
    table_data = []
    for _, row in filtered_df.head(35).iterrows():
        r_dict = row.fillna("").to_dict()
        r_dict["img_url"] = get_player_img_url(row.get("photo"), row.get("code"))
        r_dict["gw_xp"] = float(row["Proj_GW_xP"])
        r_dict["Price"] = float(row["Price"])
        table_data.append(r_dict)
        
    return {"top_cards": top_cards, "table": table_data}
    return {"top_cards": top_cards, "cards": top_cards, "table": table_data}
