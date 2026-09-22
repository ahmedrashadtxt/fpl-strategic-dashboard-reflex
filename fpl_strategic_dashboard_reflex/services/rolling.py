"""Service functions for Rolling Form analysis."""

from fpl_strategic_dashboard_reflex.services.squad import get_player_img_url, fmt_num, SILHOUETTE_BASE64
from fpl_strategic_dashboard_reflex.services.db import get_connection, get_manager_squad_ids, get_teams_fdr_map
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from rapidfuzz import fuzz, process
from fpl_strategic_dashboard_reflex.services.cache import ttl_cache

pos_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
pos_colors = {"GKP": "amber", "DEF": "blue", "MID": "green", "FWD": "purple"}


@ttl_cache(ttl_seconds=300)
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


def calc_rolling_proj_xp(row):
    etype = int(row.get("element_type", 3))
    xgi90 = float(row.get("Rolling_xGI_per_90", 0))
    avg_mins = float(row.get("Rolling_Avg_Mins", 60))
    avg_pts = float(row.get("Rolling_Avg_Pts", 3.0))
    fdr = int(row.get("Upcoming_FDR", 15))

    app_pts = 2.0 * min(1.0, max(0.2, avg_mins / 75.0))
    att_weight = 4.2 if etype == 4 else (4.6 if etype == 3 else 3.5)
    underlying_xp = (xgi90 * att_weight) * (avg_mins / 90.0)
    schedule_mult = max(0.75, min(1.25, 1.0 + ((15 - fdr) / 30.0)))
    blended_raw = (0.55 * (app_pts + underlying_xp)) + (0.45 * avg_pts)
    return round(blended_raw * schedule_mult, 2)


@ttl_cache(ttl_seconds=300)
def run_rolling_analysis(*args, **kwargs):
    if args and isinstance(args[0], int):
        conn = get_connection()
        current_gw = args[0]
        manager_id = args[1] if len(args) > 1 else ""
        window_size = args[2] if len(args) > 2 else 5
        search_query = args[3] if len(args) > 3 else ""
        min_avg_mins = args[4] if len(args) > 4 else 45
        position_filter = args[5] if len(args) > 5 else "All"
        sort_by = args[6] if len(args) > 6 else "Projected Form xP / Match"
        only_my_squad = args[7] if len(args) > 7 else False
        max_price = args[8] if len(args) > 8 else 15.5
        min_matches = args[9] if len(args) > 9 else 1
    else:
        conn = args[0] if len(args) > 0 else kwargs.get("conn", get_connection())
        current_gw = args[1] if len(args) > 1 else kwargs.get("current_gw", 1)
        manager_id = args[2] if len(args) > 2 else kwargs.get("manager_id", "")
        window_size = kwargs.get("window_size", args[3] if len(args) > 3 else 5)
        search_query = kwargs.get("search_query", args[4] if len(args) > 4 else "")
        min_avg_mins = kwargs.get("min_avg_mins", args[5] if len(args) > 5 else 45)
        position_filter = kwargs.get("position_filter", args[6] if len(args) > 6 else "All")
        sort_by = kwargs.get("sort_by", args[7] if len(args) > 7 else "Projected Form xP / Match")
        only_my_squad = kwargs.get("only_my_squad", args[8] if len(args) > 8 else False)
        max_price = kwargs.get("max_price", args[9] if len(args) > 9 else 15.5)
        min_matches = kwargs.get("min_matches", args[10] if len(args) > 10 else 1)

    if conn is None:
        conn = get_connection()

    if isinstance(window_size, str):
        w_str = window_size.replace("L", "").strip()
        lookback_window = int(w_str) if w_str.isdigit() else 5
    elif isinstance(window_size, (int, float)):
        lookback_window = int(window_size)
    else:
        lookback_window = 5

    try:
        max_price = float(max_price)
    except Exception:
        max_price = 15.5

    try:
        min_matches = int(min_matches)
    except Exception:
        min_matches = 1

    try:
        min_avg_mins = int(min_avg_mins)
    except Exception:
        min_avg_mins = 45

    fdr_map = get_teams_fdr_map(conn, current_gw)
    df_raw = fetch_rolling_base_data(conn, lookback_window)
    if df_raw.empty:
        return {"top_cards": [], "cards": [], "table": [], "fig": go.Figure()}

    df_raw["Upcoming_FDR"] = df_raw["Team_ID"].map(fdr_map).fillna(15).astype(int)
    df_raw["Proj_Form_xP"] = df_raw.apply(calc_rolling_proj_xp, axis=1)

    filtered_df = df_raw.copy()

    if position_filter != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == position_filter]

    filtered_df = filtered_df[
        (filtered_df["Price"] <= max_price)
        & (filtered_df["Rolling_Avg_Mins"] >= min_avg_mins)
        & (filtered_df["Rolling_Matches_Played"] >= min_matches)
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
        matches = process.extract(
            query=q,
            choices=search_targets,
            scorer=fuzz.WRatio,
            score_cutoff=60,
            limit=40,
        )
        if matches:
            matched_indices = [m[2] for m in matches]
            filtered_df = filtered_df.loc[matched_indices]
        else:
            filtered_df = filtered_df.iloc[0:0]
    elif not filtered_df.empty:
        sort_rolling_map = {
            "Projected Form xP / Match": ("Proj_Form_xP", False),
            "Rolling Avg Points": ("Rolling_Avg_Pts", False),
            "Rolling Sum xGI": ("Rolling_Sum_xGI", False),
            "Rolling xGI / 90": ("Rolling_xGI_per_90", False),
            "Upcoming Fixture Ease": ("Upcoming_FDR", True),
            "Rolling Avg Minutes": ("Rolling_Avg_Mins", False),
            "Price": ("Price", False),
            # Legacy fallbacks
            "Form vs Price Ratio": ("Rolling_Avg_Pts", False),
            "Points / GW": ("Rolling_Avg_Pts", False),
            "Minutes / GW": ("Rolling_Avg_Mins", False),
            "Rolling xGI": ("Rolling_Sum_xGI", False),
            "Total Points": ("Rolling_Avg_Pts", False),
            "Upcoming Schedule (Easiest FDR)": ("Upcoming_FDR", True),
            "Blended Form xP": ("Proj_Form_xP", False),
            "Expected Goal Involvement (xGI)": ("Rolling_Sum_xGI", False),
            "Roll_Points_GW": ("Rolling_Avg_Pts", False),
            "Roll_xGI_90": ("Rolling_xGI_per_90", False),
            "Roll_Mins_GW": ("Rolling_Avg_Mins", False),
            "FDR_Next_5": ("Upcoming_FDR", True),
            "Proj_Form_xP": ("Proj_Form_xP", False),
        }
        r_col, r_asc = sort_rolling_map.get(sort_by, ("Proj_Form_xP", False))
        if r_col in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=r_col, ascending=r_asc)

    if filtered_df.empty:
        return {"top_cards": [], "cards": [], "table": [], "fig": go.Figure()}

    # Plotly Scatter Matrix
    if len(filtered_df) >= 2:
        x_mid = float(filtered_df["Upcoming_FDR"].median())
        y_mid = float(filtered_df["Proj_Form_xP"].median())

        fig = px.scatter(
            filtered_df,
            x="Upcoming_FDR",
            y="Proj_Form_xP",
            color="Pos",
            size="Price",
            size_max=16,
            hover_name="Player",
            hover_data={
                "Team": True,
                "Price": ":.1f",
                "Proj_Form_xP": ":.2f",
                "Rolling_Avg_Pts": ":.2f",
                "Rolling_Sum_xGI": ":.2f",
                "Upcoming_FDR": True,
                "Rolling_Avg_Mins": ":.0f",
                "Rolling_Matches_Played": True,
                "Pos": False,
            },
            labels={
                "Upcoming_FDR": "Upcoming 5-GW Fixture Difficulty Rating (Lower = Easier)",
                "Proj_Form_xP": "Projected Form xP / Match",
                "Pos": "Position",
            },
            title="Projected Form vs Fixture Run (Proj Form xP vs Next 5 FDR)",
            color_discrete_map={
                "GKP": "#f59e0b",
                "DEF": "#3b82f6",
                "MID": "#10b981",
                "FWD": "#ef4444",
            },
        )

        fig.update_traces(
            marker=dict(
                opacity=0.88,
                line=dict(width=1, color="rgba(255, 255, 255, 0.45)"),
            )
        )

        fig.add_vline(x=x_mid, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)")
        fig.add_hline(y=y_mid, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)")

        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            paper_bgcolor="rgba(15, 23, 42, 0.0)",
            margin=dict(l=20, r=20, t=50, b=20),
            height=450,
            xaxis=dict(gridcolor="rgba(255, 255, 255, 0.08)", zeroline=False),
            yaxis=dict(gridcolor="rgba(255, 255, 255, 0.08)", zeroline=False),
        )
    else:
        fig = go.Figure()

    # Top Cards
    top_cards = []
    for _, row in filtered_df.head(4).iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        proj_xp = float(row["Proj_Form_xP"])
        pos_str = str(row["Pos"])
        top_cards.append({
            "player": str(row["Player"]),
            "team": str(row["Team"]),
            "team_display": f"({row['Team']})",
            "pos": pos_str,
            "pos_color": pos_colors.get(pos_str, "gray"),
            "badge_text": f"Proj {proj_xp:.1f} xP",
            "badge_color": "green",
            "subtext": (
                f"Price £{float(row['Price']):.1f} · Form xP {proj_xp:.2f} · "
                f"Avg Pts {float(row['Rolling_Avg_Pts']):.1f} · Next 5 FDR {int(row['Upcoming_FDR'])}"
            ),
            "img_url": p_img,
        })

    # Table Data
    table_data = []
    for _, row in filtered_df.head(35).iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        fdr_val = int(row["Upcoming_FDR"])
        fdr_color = "green" if fdr_val <= 11 else ("amber" if fdr_val <= 14 else "red")
        proj_xp = float(row["Proj_Form_xP"])
        pos_str = str(row["Pos"])
        table_data.append({
            "img_url": p_img,
            "Player": str(row["Player"]),
            "Team": str(row["Team"]),
            "Pos": pos_str,
            "Pos_Color": pos_colors.get(pos_str, "gray"),
            "Price_Display": f"{float(row['Price']):.1f}",
            "Latest_GW": str(int(row["Latest_GW"])),
            "Proj_Form_XP_Display": f"{proj_xp:.2f}",
            "Rolling_Avg_Pts_Display": f"{float(row['Rolling_Avg_Pts']):.2f}",
            "Rolling_Sum_xGI_Display": f"{float(row['Rolling_Sum_xGI']):.2f}",
            "Rolling_xGI_90_Display": f"{float(row['Rolling_xGI_per_90']):.2f}",
            "FDR_Display": str(fdr_val),
            "FDR_Color": fdr_color,
            "Rolling_Avg_Mins_Display": f"{float(row['Rolling_Avg_Mins']):.1f}",
            "Rolling_Matches_Played": str(int(row["Rolling_Matches_Played"])),
        })

    return {"top_cards": top_cards, "cards": top_cards, "table": table_data, "fig": fig}
