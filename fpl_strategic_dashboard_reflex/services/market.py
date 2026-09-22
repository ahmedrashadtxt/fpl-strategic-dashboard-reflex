"""Service functions for Transfer Market, Target Finder, and Price Change Tracking."""

import math
import os
import pandas as pd
from rapidfuzz import fuzz, process

from fpl_strategic_dashboard_reflex.services.cache import ttl_cache
from fpl_strategic_dashboard_reflex.services.betting import fetch_upcoming_betting_odds, get_fixture_market_xg_and_movement
from fpl_strategic_dashboard_reflex.services.squad import get_player_img_url, fmt_num, SILHOUETTE_BASE64
from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_manager_squad_ids,
    get_price_prediction_map,
)

pos_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}
pos_colors = {"GKP": "amber", "DEF": "blue", "MID": "green", "FWD": "purple"}


def apply_target_market_projection(
    conn,
    base_proj_pts: float,
    pos: str,
    fdr: int,
    is_home: bool,
    team_short: str,
    opp_short: str,
    market_weight: float,
    factor_movement: bool,
    market_cache: dict,
) -> float:
    h_team = team_short if is_home else opp_short
    a_team = opp_short if is_home else team_short
    fdr_h = fdr if is_home else 3
    fdr_a = 3 if is_home else fdr

    mkt_h_xg, mkt_a_xg, mkt_h_cs, mkt_a_cs, mv = get_fixture_market_xg_and_movement(
        conn, h_team, a_team, fdr_h, fdr_a, market_cache
    )

    mkt_team_xg = mkt_h_xg if is_home else mkt_a_xg
    mkt_cs_prob = mkt_h_cs if is_home else mkt_a_cs
    team_mv = mv["home"] if is_home else mv["away"]

    fdr_base = max(0.6, 2.55 - (fdr * 0.35))
    blended_xg = ((1.0 - market_weight) * fdr_base) + (market_weight * mkt_team_xg)

    if factor_movement:
        blended_xg = max(0.4, blended_xg + (0.40 * team_mv["delta_xg"]))

    if pos in ("MID", "FWD"):
        xg_scale = blended_xg / max(fdr_base, 0.4)
        xg_scale = max(0.4, min(2.2, xg_scale))
        return round(base_proj_pts * xg_scale, 2)
    elif pos in ("GKP", "DEF"):
        base_cs_prob = max(0.05, min(0.65, math.exp(-max(0.6, fdr * 0.4))))
        blended_cs_prob = ((1.0 - market_weight) * base_cs_prob) + (market_weight * mkt_cs_prob)
        if factor_movement:
            blended_cs_prob = max(0.02, min(0.85, blended_cs_prob + (0.25 * team_mv["delta_win"])))
        cs_diff = (blended_cs_prob - base_cs_prob) * 4.0
        return round(max(0.5, base_proj_pts + cs_diff), 2)
    return round(base_proj_pts, 2)


def get_price_trend_info(row: dict | pd.Series, price_map: dict) -> dict:
    p_id = row.get("id") or row.get("element_id")
    pred = price_map.get(p_id, {})
    status_raw = str(pred.get("price_status", "")).upper()
    prog = float(pred.get("target_progress_pct", 0.0))
    c_event = int(row.get("cost_change_event", 0))
    net_tx = int(row.get("net_transfers", 0))

    if c_event > 0:
        return {
            "trend_label": f"▲ Rose +£{c_event/10:.1f}m",
            "trend_color": "green",
            "trend_icon": "▲",
            "trend_type": "rising",
        }
    elif c_event < 0:
        return {
            "trend_label": f"▼ Fell -£{abs(c_event)/10:.1f}m",
            "trend_color": "red",
            "trend_icon": "▼",
            "trend_type": "falling",
        }
    elif "RISING_TONIGHT" in status_raw or prog >= 90.0:
        return {
            "trend_label": "▲ Rising (Tonight)",
            "trend_color": "green",
            "trend_icon": "▲",
            "trend_type": "rising",
        }
    elif "RISING_SOON" in status_raw or prog >= 70.0:
        return {
            "trend_label": "▲ Rising Soon",
            "trend_color": "green",
            "trend_icon": "▲",
            "trend_type": "rising",
        }
    elif "FALLING_TONIGHT" in status_raw or prog <= -90.0:
        return {
            "trend_label": "▼ Falling (Tonight)",
            "trend_color": "red",
            "trend_icon": "▼",
            "trend_type": "falling",
        }
    elif "FALLING_SOON" in status_raw or prog <= -70.0:
        return {
            "trend_label": "▼ Falling Soon",
            "trend_color": "red",
            "trend_icon": "▼",
            "trend_type": "falling",
        }
    elif net_tx > 20000:
        return {
            "trend_label": "▲ Rising",
            "trend_color": "green",
            "trend_icon": "▲",
            "trend_type": "rising",
        }
    elif net_tx < -20000:
        return {
            "trend_label": "▼ Falling",
            "trend_color": "red",
            "trend_icon": "▼",
            "trend_type": "falling",
        }
    else:
        return {
            "trend_label": "— Stable",
            "trend_color": "gray",
            "trend_icon": "",
            "trend_type": "stable",
        }


@ttl_cache(ttl_seconds=600)
def fetch_transfer_targets_base_data(_conn, current_gw: int, target_gw: int, enable_betting_target: bool, odds_api_key: str):
    """Caches base model evaluations and betting projections across all candidates."""
    query = """
    SELECT
        p.id,
        p.id AS element_id,
        p.code,
        p.photo,
        p.web_name AS Player,
        p.first_name || ' ' || p.second_name AS Full_Name,
        t.short_name AS Team,
        t.name AS Club_Name,
        p.team AS team_id,
        CASE p.element_type
            WHEN 1 THEN 'GKP'
            WHEN 2 THEN 'DEF'
            WHEN 3 THEN 'MID'
            WHEN 4 THEN 'FWD'
        END AS Pos,
        pos.singular_name AS Position,
        p.now_cost / 10.0 AS Cost,
        p.now_cost / 10.0 AS Price,
        p.cost_change_event,
        p.cost_change_start,
        p.transfers_in_event,
        p.transfers_out_event,
        (p.transfers_in_event - p.transfers_out_event) AS net_transfers,
        p.minutes AS minutes,
        p.minutes AS Minutes,
        p.total_points AS Total_Points,
        p.total_points AS Season_Points,
        p.form AS Form,
        p.points_per_game AS PPG,
        p.expected_goals,
        p.expected_assists,
        p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.selected_by_percent AS Own_Pct,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE (p.status = 'a' OR p.chance_of_playing_next_round >= 75)
    """
    candidates_df = pd.read_sql(query, _conn)
    if candidates_df.empty:
        return pd.DataFrame()

    fixtures_df = pd.read_sql(
        """
        SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
               th.short_name AS Home_Team, ta.short_name AS Away_Team,
               f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
        FROM fixtures f
        INNER JOIN teams th ON f.team_h = th.id
        INNER JOIN teams ta ON f.team_a = ta.id
        WHERE f.event >= ? AND f.event <= ?
        """,
        _conn,
        params=[current_gw, current_gw + 4],
    )
    hist_baselines_df = get_historical_player_baselines(_conn)
    market_cache = fetch_upcoming_betting_odds(odds_api_key) if enable_betting_target else {}

    results = []
    for _, p_row in candidates_df.iterrows():
        fix_data = get_fixture_for_team(fixtures_df, p_row["team_id"], target_gw)
        base_xp = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)
        final_xp = base_xp

        if enable_betting_target and fix_data.get("opponent"):
            opp_short = fix_data["opponent"].replace(" (H)", "").replace(" (A)", "")
            final_xp = apply_target_market_projection(
                _conn,
                base_xp,
                p_row["Pos"],
                fix_data["fdr"],
                fix_data["is_home"],
                p_row["Team"],
                opp_short,
                market_weight=0.35,
                factor_movement=True,
                market_cache=market_cache,
            )

        price = float(p_row["Cost"])
        xp_per_mil = round(final_xp / max(price, 4.0), 2)

        row_dict = dict(p_row)
        row_dict.update({
            "Fixture": fix_data.get("opponent", "TBD"),
            "FDR": fix_data.get("fdr", 3),
            "Proj_xP": round(final_xp, 2),
            "xP_per_Mil": xp_per_mil,
        })
        results.append(row_dict)

    target_df = pd.DataFrame(results)
    if not target_df.empty:
        for col in ["Proj_xP", "xP_per_Mil", "Cost", "Price", "Form", "Total_Points", "Season_Points", "FDR", "Own_Pct"]:
            if col in target_df.columns:
                target_df[col] = pd.to_numeric(target_df[col], errors="coerce").fillna(0)

        target_df["_search_target"] = (
            target_df["Player"].fillna("")
            + " "
            + target_df["Full_Name"].fillna("")
            + " "
            + target_df["Team"].fillna("")
            + " "
            + target_df["Club_Name"].fillna("")
        ).str.strip()

    return target_df


@ttl_cache(ttl_seconds=300)
def run_market_analysis(*args, **kwargs) -> dict:
    """Executes full transfer target scouting analysis, filtering, and metric card formatting."""
    conn = get_connection()
    try:
        if args and isinstance(args[0], int):
            current_gw = args[0]
            manager_id = args[1] if len(args) > 1 else ""
            search_query = args[2] if len(args) > 2 else ""
            position_filter = args[3] if len(args) > 3 else "All"
            sort_by = args[4] if len(args) > 4 else "Projected Points (xP)"
            max_price = args[5] if len(args) > 5 else 15.5
            exclude_my_squad = args[6] if len(args) > 6 else True
            enable_betting = args[7] if len(args) > 7 else True
            odds_api_key = args[8] if len(args) > 8 else os.getenv("ODDS_API_KEY", "")
        else:
            current_gw = kwargs.get("current_gw", args[0] if len(args) > 0 else 1)
            manager_id = kwargs.get("manager_id", args[1] if len(args) > 1 else "")
            search_query = kwargs.get("search_query", args[2] if len(args) > 2 else "")
            position_filter = kwargs.get("position_filter", kwargs.get("pos_filter", args[3] if len(args) > 3 else "All"))
            sort_by = kwargs.get("sort_by", args[4] if len(args) > 4 else "Projected Points (xP)")
            max_price = kwargs.get("max_price", args[5] if len(args) > 5 else 15.5)
            exclude_my_squad = kwargs.get("exclude_my_squad", args[6] if len(args) > 6 else True)
            enable_betting = kwargs.get("enable_betting", args[7] if len(args) > 7 else True)
            odds_api_key = kwargs.get("odds_api_key", args[8] if len(args) > 8 else os.getenv("ODDS_API_KEY", ""))

        try:
            max_price = float(max_price)
        except Exception:
            max_price = 15.5

        cgw_df = pd.read_sql("SELECT id FROM events WHERE is_current = 1 LIMIT 1", conn)
        actual_cgw = int(cgw_df.iloc[0]["id"]) if not cgw_df.empty else (current_gw if current_gw > 0 else 1)
        ngw_df = pd.read_sql("SELECT id FROM events WHERE is_next = 1 LIMIT 1", conn)
        target_gw = int(ngw_df.iloc[0]["id"]) if not ngw_df.empty else (actual_cgw + 1)

        raw_df = fetch_transfer_targets_base_data(conn, actual_cgw, target_gw, enable_betting, odds_api_key)
        if raw_df.empty:
            return {"top_cards": [], "cards": [], "table": []}

        df = raw_df.copy()

        # Position filter
        if position_filter and position_filter != "All":
            df = df[df["Pos"] == position_filter]

        # Price limit
        df = df[df["Price"] <= max_price]

        # Exclude user's squad
        if exclude_my_squad and manager_id and str(manager_id).strip():
            squad_ids = get_manager_squad_ids(str(manager_id).strip(), actual_cgw)
            if squad_ids and "element_id" in df.columns:
                df = df[~df["element_id"].isin(squad_ids)]

        # Search query fuzzy matching
        if search_query and search_query.strip() and not df.empty:
            q = search_query.strip().lower()
            choices = df["_search_target"].to_dict() if "_search_target" in df.columns else df["Player"].to_dict()
            matches = process.extract(q, choices, scorer=fuzz.WRatio, score_cutoff=60, limit=50)
            if matches:
                matched_indices = [m[2] for m in matches]
                df = df.loc[matched_indices]
            else:
                return {"top_cards": [], "cards": [], "table": []}

        # Sorting
        sort_map = {
            "Projected Points (xP)": ("Proj_xP", False),
            "Value Efficiency (xP / £M)": ("xP_per_Mil", False),
            "Current Form": ("Form", False),
            "Total Season Points": ("Total_Points", False),
            "Price (Low to High)": ("Price", True),
            "Ownership % (Low to High)": ("Own_Pct", True),
            "Easiest Fixture": ("FDR", True),
        }
        sort_col, sort_asc = sort_map.get(sort_by, ("Proj_xP", False))
        if sort_col in df.columns:
            df = df.sort_values(by=sort_col, ascending=sort_asc)

        price_map = get_price_prediction_map(conn)

        # Build Top 4 Cards
        top_cards = []
        for _, row in df.head(4).iterrows():
            pos = str(row.get("Pos", "MID"))
            p_img = get_player_img_url(row.get("photo"), row.get("code"))
            cost = float(row.get("Price", 0.0))
            proj_xp = float(row.get("Proj_xP", 0.0))
            xp_mil = float(row.get("xP_per_Mil", 0.0))
            fix = str(row.get("Fixture", ""))

            trend = get_price_trend_info(row, price_map)
            trend_tag = f" ({trend['trend_icon']} {trend['trend_type'].capitalize()})" if trend['trend_icon'] else ""

            top_cards.append({
                "player": str(row.get("Player", "")),
                "team": str(row.get("Team", "")),
                "team_display": f"({row.get('Team', '')})",
                "pos": pos,
                "pos_color": pos_colors.get(pos, "gray"),
                "badge_text": f"GW{target_gw} Target",
                "badge_color": "green",
                "subtext": f"Price £{cost:.1f}{trend_tag} · xP {proj_xp:.1f} · Val {xp_mil:.2f}xP/£M · Fix {fix}",
                "img_url": p_img,
            })

        # Build Table Records
        table_rows = []
        for _, row in df.head(50).iterrows():
            fdr_val = int(row.get("FDR", 3))
            fdr_color = "green" if fdr_val <= 2 else ("amber" if fdr_val == 3 else ("orange" if fdr_val == 4 else "red"))
            p_img = get_player_img_url(row.get("photo"), row.get("code"))
            trend_info = get_price_trend_info(row, price_map)
            pos = str(row.get("Pos", "MID"))

            table_rows.append({
                "img_url": p_img,
                "Player": str(row.get("Player", "")),
                "Team": str(row.get("Team", "")),
                "Pos": pos,
                "Pos_Color": pos_colors.get(pos, "gray"),
                "Price_Display": f"£{float(row.get('Price', 0.0)):.1f}",
                "Price_Trend_Label": trend_info["trend_label"],
                "Price_Trend_Color": trend_info["trend_color"],
                "Fixture": str(row.get("Fixture", "")),
                "FDR": f"FDR {fdr_val}",
                "FDR_Color": fdr_color,
                "Proj_xP": f"{float(row.get('Proj_xP', 0.0)):.1f}",
                "xP_per_Mil": f"{float(row.get('xP_per_Mil', 0.0)):.2f}",
                "Form": f"{float(row.get('Form', 0.0)):.1f}",
                "Own_Pct": f"{float(row.get('Own_Pct', 0.0)):.1f}%",
                "Season_Points": str(int(row.get("Total_Points", 0))),
            })

        return {"top_cards": top_cards, "cards": top_cards, "table": table_rows}
    finally:
        conn.close()
