
import pandas as pd
from rapidfuzz import process, fuzz
from backend.squad_logic import get_player_img_url, fmt_num

def run_expected_analysis(conn, current_gw, manager_id, search_query, min_avg_mins, position_filter, sort_by, max_price, only_my_squad, show_career_baseline):
    from backend.expected_logic import fetch_expected_stats_base_data
    from backend.data import get_manager_squad_ids
    
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
        }
        sort_col, sort_asc = sort_map.get(sort_by, ("Proj_GW_xP", False))
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

with open("backend/expected_logic.py", "a", encoding="utf-8") as f:
    import inspect
    f.write("\n\n")
    f.write(inspect.getsource(run_expected_analysis))

