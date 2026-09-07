from backend.squad_logic import get_player_img_url, fmt_num, SILHOUETTE_BASE64
from backend.data import get_manager_squad_ids, get_teams_fdr_map
import numpy as np
import pandas as pd
import plotly.express as px
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


def fetch_rolling_base_data(_conn, window_size: int):
    """Caches rolling window computations per window size."""
    table_check = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_match_history'",
        _conn,
    )
    if table_check.empty:
        return pd.DataFrame()

    rolling_query = f"""
    WITH ranked_matches AS (
        SELECT
            h.element_id,
            p.code,
            p.photo,
            p.web_name AS Player,
            p.first_name || ' ' || p.second_name AS Full_Name,
            t.short_name AS Team,
            t.name AS Club_Name,
            p.team AS Team_ID,
            CASE p.element_type
                WHEN 1 THEN 'GKP'
                WHEN 2 THEN 'DEF'
                WHEN 3 THEN 'MID'
                WHEN 4 THEN 'FWD'
            END AS Pos,
            p.element_type AS element_type,
            p.now_cost / 10.0 AS Price,
            h.round AS GW,
            h.total_points,
            h.minutes,
            CAST(h.expected_goal_involvements AS FLOAT) AS xgi,
            AVG(h.total_points) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Avg_Pts,
            SUM(CAST(h.expected_goal_involvements AS FLOAT)) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Sum_xGI,
            AVG(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Avg_Mins,
            SUM(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Total_Mins,
            SUM(CASE WHEN h.minutes > 0 THEN 1 ELSE 0 END) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Matches_Played,
            ROW_NUMBER() OVER (
                PARTITION BY h.element_id
                ORDER BY h.round DESC
            ) AS rn
        FROM player_match_history h
        INNER JOIN players p ON h.element_id = p.id
        INNER JOIN teams t ON p.team = t.id
    )
    SELECT
        element_id,
        code,
        photo,
        Player,
        Full_Name,
        Team,
        Club_Name,
        Team_ID,
        Pos,
        element_type,
        Price,
        GW AS Latest_GW,
        ROUND(Rolling_Avg_Pts, 2) AS Rolling_Avg_Pts,
        ROUND(Rolling_Sum_xGI, 2) AS Rolling_Sum_xGI,
        ROUND(Rolling_Avg_Mins, 1) AS Rolling_Avg_Mins,
        Rolling_Matches_Played,
        ROUND(
            CASE 
                WHEN Rolling_Total_Mins > 0 
                THEN (Rolling_Sum_xGI / Rolling_Total_Mins) * 90.0 
                ELSE 0.0 
            END, 2
        ) AS Rolling_xGI_per_90
    FROM ranked_matches
    WHERE rn = 1
    """
    df = pd.read_sql(rolling_query, _conn)
    if not df.empty:
        for col in [
            "Price", "Rolling_Avg_Pts", "Rolling_Sum_xGI", "Rolling_Avg_Mins",
            "Rolling_xGI_per_90", "Rolling_Matches_Played", "element_type"
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df = df.dropna(subset=["Player"])
        df = df[df["Player"].astype(str).str.strip() != ""]
        df["_search_target"] = (
            df["Player"].fillna("")
            + " "
            + df["Full_Name"].fillna("")
            + " "
            + df["Team"].fillna("")
            + " "
            + df["Club_Name"].fillna("")
        ).str.strip()
    return df




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
