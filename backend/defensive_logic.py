from backend.squad_logic import get_player_img_url, fmt_num, SILHOUETTE_BASE64
from backend.data import get_manager_squad_ids
from backend.data import get_manager_squad_ids
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


def fetch_defensive_base_data(_conn, current_gw: int = 1):
    """Fetches player defensive records and precomputes absolute gameweek projected defensive xP."""
    player_cols = [
        c.lower()
        for c in pd.read_sql("PRAGMA table_info(players)", _conn)["name"].tolist()
    ]

    t_expr = (
        "p.tackles AS T"
        if "tackles" in player_cols
        else ("p.t AS T" if "t" in player_cols else "0 AS T")
    )

    if "clearances_blocks_interceptions" in player_cols:
        cbi_expr = "p.clearances_blocks_interceptions AS CBI"
    elif "cbi" in player_cols:
        cbi_expr = "p.cbi AS CBI"
    elif all(c in player_cols for c in ["clearances", "blocks", "interceptions"]):
        cbi_expr = "(p.clearances + p.blocks + p.interceptions) AS CBI"
    else:
        cbi_expr = "0 AS CBI"

    r_expr = (
        "p.recoveries AS R"
        if "recoveries" in player_cols
        else ("p.r AS R" if "r" in player_cols else "0 AS R")
    )

    if "defensive_contribution" in player_cols:
        dc_expr = "p.defensive_contribution AS DC"
    elif "defensive_contributions" in player_cols:
        dc_expr = "p.defensive_contributions AS DC"
    elif "dc" in player_cols:
        dc_expr = "p.dc AS DC"
    else:
        cbi_col = (
            "p.clearances_blocks_interceptions"
            if "clearances_blocks_interceptions" in player_cols
            else ("p.cbi" if "cbi" in player_cols else "0")
        )
        t_col = "p.tackles" if "tackles" in player_cols else "0"
        r_col = "p.recoveries" if "recoveries" in player_cols else "0"
        dc_expr = f"""
            CASE 
                WHEN p.element_type = 2 THEN (COALESCE({cbi_col}, 0) + COALESCE({t_col}, 0))
                ELSE (COALESCE({cbi_col}, 0) + COALESCE({t_col}, 0) + COALESCE({r_col}, 0))
            END AS DC
        """

    xgc_expr = (
        "p.expected_goals_conceded AS xGC"
        if "expected_goals_conceded" in player_cols
        else "0.0 AS xGC"
    )
    xgc_90_expr = (
        "p.expected_goals_conceded_per_90 AS xGC_per_90"
        if "expected_goals_conceded_per_90" in player_cols
        else "0.0 AS xGC_per_90"
    )

    table_check = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_past_seasons'",
        _conn,
    )
    has_history = not table_check.empty

    past_cols = (
        [
            c.lower()
            for c in pd.read_sql(
                "PRAGMA table_info(player_past_seasons)", _conn
            )["name"].tolist()
        ]
        if has_history
        else []
    )

    gc_hist_col = "SUM(goals_conceded)" if "goals_conceded" in past_cols else "0"
    cs_hist_col = "SUM(clean_sheets)" if "clean_sheets" in past_cols else "0"

    hist_join = (
        f"""
        LEFT JOIN (
            SELECT 
                element_id,
                ROUND(({gc_hist_col} * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_GC_90,
                ROUND(({cs_hist_col} * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_CS_90,
                ROUND((SUM(total_points) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_Pts_90,
                SUM(minutes) AS Career_Mins
            FROM player_past_seasons
            GROUP BY element_id
        ) hist ON p.id = hist.element_id
    """
        if has_history
        else ""
    )

    hist_select = (
        """
        hist.Career_GC_90,
        hist.Career_CS_90,
        hist.Career_Pts_90,
        hist.Career_Mins,
    """
        if has_history
        else """
        NULL AS Career_GC_90,
        NULL AS Career_CS_90,
        NULL AS Career_Pts_90,
        NULL AS Career_Mins,
    """
    )

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
        p.clean_sheets AS Clean_Sheets,
        p.goals_conceded AS Goals_Conceded,
        p.saves AS Saves,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance,
        {xgc_expr},
        {xgc_90_expr},
        {t_expr},
        {cbi_expr},
        {r_expr},
        {dc_expr},
        {hist_select}
        p.now_cost / 10.0 AS price_val
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    {hist_join}
    """
    df_def = pd.read_sql(query, _conn)

    current_season_numeric = [
        "Price", "Minutes", "Total_Points", "Clean_Sheets", "Goals_Conceded",
        "Saves", "xGC", "xGC_per_90", "T", "CBI", "R", "DC", "element_type"
    ]
    for col_name in current_season_numeric:
        if col_name in df_def.columns:
            df_def[col_name] = pd.to_numeric(df_def[col_name], errors="coerce").fillna(0)

    career_numeric = ["Career_GC_90", "Career_CS_90", "Career_Pts_90", "Career_Mins"]
    for col_name in career_numeric:
        if col_name in df_def.columns:
            df_def[col_name] = pd.to_numeric(df_def[col_name], errors="coerce")

    df_def["DC_per_90"] = (
        (df_def["DC"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
    ).fillna(0.0).round(2)
    df_def["Saves_per_90"] = (
        (df_def["Saves"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
    ).fillna(0.0).round(2)

    if (df_def["xGC_per_90"] == 0).all():
        df_def["xGC_per_90"] = (
            (df_def["xGC"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
        ).fillna(0.0).round(2)

    completed_gws = max(1, current_gw - 1)
    df_def["Avg_Mins_GW"] = (df_def["Minutes"] / completed_gws).round(1)

    def calc_def_xp(row):
        etype = int(row.get("element_type", 2))
        mins = float(row.get("Minutes", 0))
        career_gc = row.get("Career_GC_90")
        avg_mins = float(row.get("Avg_Mins_GW", 0))

        raw_xgc90 = float(row.get("xGC_per_90", 0))
        if raw_xgc90 <= 0:
            raw_xgc90 = 1.35

        if mins < 90:
            baseline_gc = (
                float(career_gc)
                if pd.notna(career_gc) and float(career_gc) > 0
                else 1.35
            )
            weight = mins / 90.0
            xgc90 = (raw_xgc90 * weight) + (baseline_gc * (1.0 - weight))
        else:
            xgc90 = raw_xgc90

        cs_prob = np.exp(-xgc90)
        saves90 = float(row.get("Saves_per_90", 0))

        # Expected match playing time and clean sheet 60-minute eligibility
        if current_gw > 1:
            if avg_mins >= 60:
                mins_factor = min(1.0, avg_mins / 90.0)
                cs_eligible = 1.0
            elif avg_mins >= 30:
                mins_factor = (avg_mins / 90.0) * 0.85
                cs_eligible = 0.40
            elif mins > 0:
                mins_factor = max(0.05, mins / (completed_gws * 90.0))
                cs_eligible = 0.05
            else:
                mins_factor = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.35
                cs_eligible = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.35
        else:
            mins_factor = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.60
            cs_eligible = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.60

        status = str(row.get("Status", "a"))
        chance = row.get("Chance")
        if status in ("i", "u", "s"):
            avail = 0.0
        elif pd.notna(chance) and str(chance).strip() not in ("", "None"):
            avail = float(chance) / 100.0
        else:
            avail = 1.0

        if etype == 1:
            cs_pts = cs_prob * 4.0 * cs_eligible
            gc_deduction = (xgc90 * mins_factor) * 0.50
            save_pts = (saves90 * mins_factor) / 3.0
            net_def_xp = cs_pts - gc_deduction + save_pts
        elif etype == 2:
            cs_pts = cs_prob * 4.0 * cs_eligible
            gc_deduction = (xgc90 * mins_factor) * 0.50
            net_def_xp = cs_pts - gc_deduction
        elif etype == 3:
            net_def_xp = cs_prob * 1.0 * cs_eligible
        else:
            net_def_xp = 0.0

        dc90 = float(row.get("DC_per_90", 0))
        dc_boost = (0.40 if dc90 >= 10.0 else (0.20 if dc90 >= 7.0 else 0.0)) * mins_factor
        return round(max(0.0, (net_def_xp + dc_boost) * avail), 2)

    def calc_def_xp_90(row):
        etype = int(row.get("element_type", 2))
        mins = float(row.get("Minutes", 0))
        career_gc = row.get("Career_GC_90")

        raw_xgc90 = float(row.get("xGC_per_90", 0))
        if raw_xgc90 <= 0:
            raw_xgc90 = 1.35

        if mins < 90:
            baseline_gc = (
                float(career_gc)
                if pd.notna(career_gc) and float(career_gc) > 0
                else 1.35
            )
            weight = mins / 90.0
            xgc90 = (raw_xgc90 * weight) + (baseline_gc * (1.0 - weight))
        else:
            xgc90 = raw_xgc90

        cs_prob = np.exp(-xgc90)
        saves90 = float(row.get("Saves_per_90", 0))

        if etype == 1:
            cs_pts = cs_prob * 4.0
            gc_deduction = xgc90 * 0.50
            save_pts = saves90 / 3.0
            net_def_xp = cs_pts - gc_deduction + save_pts
        elif etype == 2:
            cs_pts = cs_prob * 4.0
            gc_deduction = xgc90 * 0.50
            net_def_xp = cs_pts - gc_deduction
        elif etype == 3:
            net_def_xp = cs_prob * 1.0
        else:
            net_def_xp = 0.0

        dc90 = float(row.get("DC_per_90", 0))
        dc_boost = 0.40 if dc90 >= 10.0 else (0.20 if dc90 >= 7.0 else 0.0)
        return round(max(0.1, net_def_xp + dc_boost), 2)

    if not df_def.empty:
        df_def["Proj_Defensive_xP"] = df_def.apply(calc_def_xp, axis=1)
        df_def["Proj_Defensive_xP_90"] = df_def.apply(calc_def_xp_90, axis=1)
        df_def = df_def.dropna(subset=["Player"])
        df_def = df_def[df_def["Player"].astype(str).str.strip() != ""]

        df_def["_search_target"] = (
            df_def["Player"].fillna("")
            + " "
            + df_def["Full_Name"].fillna("")
            + " "
            + df_def["Team"].fillna("")
            + " "
            + df_def["Club_Name"].fillna("")
        ).str.strip()

    return df_def




def run_defensive_analysis(conn, current_gw, manager_id, search_query, min_avg_mins, position_filter, sort_by, max_price, only_my_squad, show_career_baseline):
    from backend.defensive_logic import fetch_defensive_base_data
    from backend.data import get_manager_squad_ids
    
    df_raw = fetch_defensive_base_data(conn, current_gw)
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
            "Projected Defensive xP": ("Proj_Defensive_xP", False),
            "DC per 90": ("DC_per_90", False),
            "Total DC": ("DC", False),
            "Projected Defensive xP / 90": ("Proj_Def_xP_90", False),
            "CBI (Clearances, Blocks, Int)": ("CBI", False),
            "Tackles (T)": ("T", False),
            "Recoveries (R)": ("R", False),
            "Expected Goals Conceded (Lowest xGC)": ("xGC", True),
            "Clean Sheets": ("Clean_Sheets", False),
            "Total Points": ("Total_Points", False),
            "Goalkeeper Saves": ("Saves", False),
        }
        sort_col, sort_asc = sort_map.get(sort_by, ("Proj_Defensive_xP", False))
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
            "xgc": float(row["xGC"]),
            "dc_90": float(row["DC_per_90"]),
            "pts": int(float(row["Total_Points"])),
            "def_xp": float(row["Proj_Defensive_xP"]),
            "career_cs": float(row.get("Career_CS_90", 0.0)) if pd.notna(row.get("Career_CS_90")) else 0.0,
            "img_url": get_player_img_url(row.get("photo"), row.get("code"))
        })
        
    table_data = []
    for _, row in filtered_df.head(35).iterrows():
        r_dict = row.fillna("").to_dict()
        r_dict["img_url"] = get_player_img_url(row.get("photo"), row.get("code"))
        r_dict["def_xp"] = float(row["Proj_Defensive_xP"])
        r_dict["Price"] = float(row["Price"])
        table_data.append(r_dict)
        
    return {"top_cards": top_cards, "table": table_data}
