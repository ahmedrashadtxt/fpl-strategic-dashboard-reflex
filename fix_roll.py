
import pandas as pd
import plotly.express as px
from rapidfuzz import process, fuzz
from backend.squad_logic import get_player_img_url, fmt_num

def run_rolling_analysis(conn, current_gw, manager_id, search_query, min_avg_mins, position_filter, sort_by, max_price, only_my_squad, lookback_window):
    from backend.rolling_logic import fetch_rolling_form_data
    from backend.data import get_manager_squad_ids, get_teams_fdr_map
    
    fdr_map = get_teams_fdr_map(conn, current_gw)
    df_raw = fetch_rolling_form_data(conn, current_gw, lookback_window, fdr_map)
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
            "Blended Form xP": ("Proj_Form_xP", False),
            "Expected Goal Involvement (xGI)": ("xGI", False),
            "Base FPL Form": ("Form", False),
            "Upcoming Fixture Difficulty (Lowest FDR)": ("Upcoming_FDR", True),
            "Recent Points (Total)": ("Total_Points", False),
        }
        sort_col, sort_asc = sort_map.get(sort_by, ("Proj_Form_xP", False))
        filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)
        
    if filtered_df.empty:
        return {"top_cards": [], "table": [], "fig": None}
        
    top_cards = []
    for _, row in filtered_df.head(4).iterrows():
        top_cards.append({
            "player": row["Player"],
            "team": row["Team"],
            "pos": row["Pos"],
            "price": float(row["Price"]),
            "avg_mins": int(row["Avg_Mins_GW"]),
            "form": float(row["Form"]),
            "fdr": float(row["Upcoming_FDR"]),
            "xgi": float(row.get("xGI", 0.0)),
            "form_xp": float(row["Proj_Form_xP"]),
            "img_url": get_player_img_url(row.get("photo"), row.get("code"))
        })
        
    table_data = []
    for _, row in filtered_df.head(35).iterrows():
        r_dict = row.fillna("").to_dict()
        r_dict["img_url"] = get_player_img_url(row.get("photo"), row.get("code"))
        r_dict["form_xp"] = float(row["Proj_Form_xP"])
        r_dict["Price"] = float(row["Price"])
        table_data.append(r_dict)
        
    x_mid = float(filtered_df["Upcoming_FDR"].median())
    y_mid = float(filtered_df["Proj_Form_xP"].median())
    
    fig = px.scatter(
        filtered_df,
        x="Upcoming_FDR",
        y="Proj_Form_xP",
        color="Pos",
        size="Price",
        hover_name="Player",
        hover_data={"Upcoming_FDR": True, "Proj_Form_xP": ":.2f", "Pos": False, "Price": False},
        title="Form vs. Fixture Difficulty Matrix",
        color_discrete_map={"GKP": "#f59e0b", "DEF": "#3b82f6", "MID": "#10b981", "FWD": "#ef4444"}
    )
    fig.add_vline(x=x_mid, line_dash="dash", line_color="gray", opacity=0.5)
    fig.add_hline(y=y_mid, line_dash="dash", line_color="gray", opacity=0.5)
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Avg Upcoming FDR (Lower = Easier)",
        yaxis_title="Blended Form xP",
        font_color="#cbd5e1"
    )
        
    return {"top_cards": top_cards, "table": table_data, "fig": fig}

with open("backend/rolling_logic.py", "a", encoding="utf-8") as f:
    import inspect
    f.write("\n\n")
    f.write(inspect.getsource(run_rolling_analysis))

