import html
import math
import os
import textwrap
import pandas as pd
import requests
import streamlit as st

from betting_engine import (
    fetch_upcoming_betting_odds,
    get_fixture_market_xg_and_movement,
    sync_fixture_odds_snapshots,
)
from data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)
try:
    from audit_db import save_pre_gw_snapshot, get_snapshot, is_owner_manager
except (ImportError, Exception):
    import sys
    if "audit_db" in sys.modules:
        try:
            import importlib
            import audit_db
            importlib.reload(audit_db)
            from audit_db import save_pre_gw_snapshot, get_snapshot, is_owner_manager
        except Exception:
            def save_pre_gw_snapshot(*args, **kwargs): return 1
            def get_snapshot(*args, **kwargs): return None
            def is_owner_manager(manager_id=None): return False
    else:
        def save_pre_gw_snapshot(*args, **kwargs): return 1
        def get_snapshot(*args, **kwargs): return None
        def is_owner_manager(manager_id=None): return False


from theme import (
    fmt_num,
    render_guide_popover,
    render_list_card,
    render_optimizer_status,
    render_skeleton_cards,
    section_header,
)

SILHOUETTE_BASE64 = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmci"
    "IHZpZXdCb3g9IjAgMCA0NCA0NCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ0IiBoZWlnaHQ9"
    "IjQ0IiByeD0iMjIiIGZpbGw9IiMxZTI5M2IiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjE2IiByPSI3"
    "LjUiIGZpbGw9IiM2NDc0OGIiLz48cGF0aCBkPSJNOSAzOWMwLTcuMTggNS44Mi0xMyAxMy0xM3Mx"
    "MyA1LjgyIDEzIDEzIiBmaWxsPSIjNjQ3NDhiIi8+PC9zdmc+"
)

def get_player_img_url(photo, code=None):
    photo_str = str(photo) if pd.notna(photo) else ""
    if not photo_str or "Photo-Missing" in photo_str or photo_str == "None":
        if pd.notna(code) and str(code).strip():
            return f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{int(code)}.png"
        return SILHOUETTE_BASE64

    base_name = photo_str.replace(".jpg", "").replace(".png", "")
    if not base_name.startswith("p"):
        base_name = f"p{base_name}"
    return f"https://resources.premierleague.com/premierleague/photos/players/110x140/{base_name}.png"

@st.cache_data(ttl=600, show_spinner=False)
def get_rolling_player_metrics(_conn, window_size: int = 5):
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
            AVG(h.total_points) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS roll_pts,
            SUM(CAST(h.expected_goal_involvements AS FLOAT)) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS roll_xgi,
            AVG(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS roll_mins,
            SUM(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS roll_tot_mins,
            ROW_NUMBER() OVER (
                PARTITION BY h.element_id
                ORDER BY h.round DESC
            ) AS rn
        FROM player_match_history h
    )
    SELECT
        element_id,
        ROUND(roll_pts, 1) AS roll_pts,
        ROUND(roll_mins, 0) AS roll_mins,
        ROUND(
            CASE 
                WHEN roll_tot_mins > 0 
                THEN (roll_xgi / roll_tot_mins) * 90.0 
                ELSE 0.0 
            END, 2
        ) AS roll_xgi90
    FROM ranked_matches
    WHERE rn = 1
    """
    df = pd.read_sql(rolling_query, _conn)
    if not df.empty and "element_id" in df.columns:
        return df.set_index("element_id")
    return pd.DataFrame()

def enrich_squad_df(df: pd.DataFrame, rolling_df: pd.DataFrame, fdr_map: dict) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    res = df.copy()

    id_col = "id" if "id" in res.columns else ("element_id" if "element_id" in res.columns else None)
    team_id_col = "team_id" if "team_id" in res.columns else ("team" if "team" in res.columns else None)

    if id_col and rolling_df is not None and not rolling_df.empty:
        res["roll_pts"] = res[id_col].map(rolling_df["roll_pts"]).fillna(0.0)
        res["roll_xgi90"] = res[id_col].map(rolling_df["roll_xgi90"]).fillna(0.0)
        res["roll_mins"] = res[id_col].map(rolling_df["roll_mins"]).fillna(0).astype(int)
    else:
        res["roll_pts"] = 0.0
        res["roll_xgi90"] = 0.0
        res["roll_mins"] = 0

    if team_id_col and fdr_map:
        res["fdr5"] = res[team_id_col].map(fdr_map).fillna(15).astype(int)
    else:
        res["fdr5"] = 15

    return res

def build_player_tooltip(p: pd.Series, is_live: bool = False) -> str:
    import html
    player_name = html.escape(str(p.get("Player", "")))
    pos = html.escape(str(p.get("Pos", "")))
    team = html.escape(str(p.get("Team", "")))
    cost = p.get("Cost", 0.0)
    cost_str = f"£{fmt_num(cost, '.1f')}m" if cost else "£"

    roll_pts = fmt_num(p.get("roll_pts", 0.0), ".1f")
    roll_xgi90 = fmt_num(p.get("roll_xgi90", 0.0), ".2f")
    roll_mins = int(p.get("roll_mins", 0))
    fdr5 = int(p.get("fdr5", 15))
    fdr5_cls = "tt-fdr-easy" if fdr5 <= 11 else ("tt-fdr-med" if fdr5 <= 14 else "tt-fdr-hard")

    form = fmt_num(p.get("Form", 0.0), ".1f")
    ppg = fmt_num(p.get("PPG", 0.0), ".1f")
    opp = html.escape(str(p.get("Opponent", "-")))

    status = str(p.get("Status", "a"))
    news = str(p.get("News", ""))
    news_row = ""
    if status != "a" and news and news != "None":
        clean_news = html.escape(news[:40] + ("..." if len(news) > 40 else ""))
        news_row = f'<div class="tt-row tt-news"><span>[!] {clean_news}</span></div>'

    explain_list = p.get("Live_Explain")
    if not isinstance(explain_list, list):
        explain_list = []
    
    match_started = is_live and len(explain_list) > 0

    if match_started:
        pts = int(p.get("Raw_GW_Pts", 0))
        body_content = (
            f'<div class="tt-row"><span class="tt-label">GW Points:</span>'
            f'<span class="tt-val" style="color:#4ade80; font-weight:700;">{pts} pts</span></div>'
        )
        
        stat_map = {
            "minutes": "Minutes",
            "goals_scored": "Goals",
            "assists": "Assists",
            "clean_sheets": "Clean Sheet",
            "goals_conceded": "Goals Conceded",
            "own_goals": "Own Goals",
            "penalties_saved": "Penalties Saved",
            "penalties_missed": "Penalties Missed",
            "yellow_cards": "Yellow Card",
            "red_cards": "Red Card",
            "saves": "Saves",
            "bonus": "Bonus"
        }
        
        agg_stats = {}
        for fixture in explain_list:
            for stat in fixture.get("stats", []):
                ident = stat["identifier"]
                if stat["points"] != 0 or ident == "minutes":
                    if ident not in agg_stats:
                        agg_stats[ident] = {"points": 0, "value": 0}
                    agg_stats[ident]["points"] += stat["points"]
                    agg_stats[ident]["value"] += stat["value"]
                    
        if agg_stats:
            body_content += f'<hr style="border: 0; border-top: 1px solid rgba(255,255,255,0.08); margin: 6px 0;">'
            for ident, data in agg_stats.items():
                label = stat_map.get(ident, ident.replace("_", " ").title())
                val_str = str(data["value"])
                if ident == "minutes":
                    val_str += "\'"
                    
                pt_val = data["points"]
                if pt_val > 0:
                    pt_color = "#4ade80"
                    pt_str = f"+{pt_val}"
                elif pt_val < 0:
                    pt_color = "#ef4444"
                    pt_str = f"{pt_val}"
                else:
                    pt_color = "#94a3b8"
                    pt_str = f"{pt_val}"
                    
                body_content += (
                    f'<div class="tt-row"><span class="tt-label" style="font-size: 0.70rem; color: #94a3b8; padding-left: 5px;">&bull; {label} ({val_str})</span>'
                    f'<span class="tt-val" style="color:{pt_color}; font-size: 0.75rem;">{pt_str}</span></div>'
                )
    else:
        proj = fmt_num(p.get("Proj_Pts", 0.0), ".1f")
        body_content = (
            f'<div class="tt-row"><span class="tt-label">Fixture:</span>'
            f'<span class="tt-val">{opp}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Projected xP:</span>'
            f'<span class="tt-val" style="color:#60a5fa;">{proj} xP</span></div>'
            f'<div class="tt-row"><span class="tt-label">Avg Pts (L5):</span><span class="tt-val">{roll_pts}</span></div>'
            f'<div class="tt-row"><span class="tt-label">xGI / 90 (L5):</span><span class="tt-val">{roll_xgi90}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Avg Mins (L5):</span><span class="tt-val">{roll_mins}m</span></div>'
            f'<div class="tt-row"><span class="tt-label">Next 5 FDR:</span><span class="tt-val {fdr5_cls}">{fdr5}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Form / PPG:</span><span class="tt-val">{form} / {ppg}</span></div>'
        )

    return (
        f'<div class="player-tooltip-card">'
        f'<div class="tt-header">'
        f'<span class="tt-name">{player_name}</span>'
        f'<span class="tt-badge">{team} &middot; {pos} &middot; {cost_str}</span>'
        f'</div>'
        f'<div class="tt-body">'
        f'{body_content}'
        f'{news_row}'
        f'</div></div>'
    )

@st.cache_data(ttl=60, show_spinner=False)
def fetch_manager_transfers(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/transfers/"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_manager_entry(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_manager_history(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_manager_picks(manager_id: str, eval_gw: int, current_gw: int):
    try:
        picks_url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{eval_gw}/picks/"
        picks_res = requests.get(picks_url, timeout=10)
        if picks_res.status_code == 200:
            return picks_res.json()
        for g in range(current_gw, 0, -1):
            url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{g}/picks/"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                return res.json()
        return {}
    except Exception:
        return {}

@st.cache_data(ttl=120, show_spinner=False)
def fetch_live_gameweek_points(eval_gw: int):
    try:
        live_url = f"https://fantasy.premierleague.com/api/event/{eval_gw}/live/"
        res = requests.get(live_url, timeout=10)
        if res.status_code == 200:
            return {
                item["id"]: {
                    "total_points": item["stats"]["total_points"],
                    "minutes": item["stats"]["minutes"],
                    "bonus": item["stats"]["bonus"],
                    "bps": item["stats"]["bps"],
                    "explain": item.get("explain", [])
                }
                for item in res.json().get("elements", [])
            }
        return {}
    except Exception:
        return {}

@st.cache_data(ttl=300, show_spinner=False)
def fetch_dream_team_data(target_gw: int):
    try:
        dt_res = requests.get(
            f"https://fantasy.premierleague.com/api/dream-team/{target_gw}/",
            timeout=10,
        ).json()
        dt_elements = dt_res.get("team", [])
        picks_list = [
            {
                "element": el["element"],
                "position": i + 1,
                "multiplier": 2 if i == 0 else 1,
                "is_captain": i == 0,
                "is_vice_captain": i == 1,
            }
            for i, el in enumerate(dt_elements)
        ]
        top_pts = sum(el.get("points", 0) for el in dt_elements)
        return {
            "type": "dream_team",
            "manager_name": "Team of the Week",
            "player_name": "Official Dream Team",
            "total_score": top_pts,
            "picks": picks_list,
        }
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_motw_manager_data(target_gw: int):
    motw_id = None
    motw_score = None
    fallback_used = False
    try:
        bs_res = requests.get(
            "https://fantasy.premierleague.com/api/bootstrap-static/", timeout=10
        )
        if bs_res.status_code == 200:
            bs_events = bs_res.json().get("events", [])
            for ev in bs_events:
                if ev.get("id") == target_gw:
                    motw_id = ev.get("highest_scoring_entry")
                    motw_score = ev.get("highest_score")
                    break
    except Exception:
        pass

    if not motw_id:
        try:
            league_res = requests.get("https://fantasy.premierleague.com/api/leagues-classic/314/standings/", timeout=10)
            if league_res.status_code == 200:
                results = league_res.json().get("standings", {}).get("results", [])
                if results:
                    motw_id = results[0].get("entry")
                    motw_score = results[0].get("event_total")
                    fallback_used = True
        except Exception:
            pass

    if motw_id:
        try:
            mgr_info = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{motw_id}/", timeout=10
            ).json()
            mgr_name = mgr_info.get("name", "World #1 Manager" if fallback_used else "Top Manager")
            player_name = (
                f"{mgr_info.get('player_first_name', '')}"
                f" {mgr_info.get('player_last_name', '')}".strip()
            )
            picks_res = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{motw_id}/event/{target_gw}/picks/",
                timeout=10,
            ).json()
            picks_list = picks_res.get("picks", [])
            
            final_score = motw_score or picks_res.get("entry_history", {}).get("points", 0)
            
            return {
                "type": "motw",
                "manager_name": mgr_name,
                "player_name": player_name,
                "total_score": final_score,
                "picks": picks_list,
            }
        except Exception:
            pass
    return None

def quick_sync_live_prices(conn):
    try:
        res = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", timeout=10)
        if res.status_code == 200:
            elements = res.json().get("elements", [])
            cursor = conn.cursor()
            cursor.executemany(
                """
                UPDATE players 
                SET now_cost = ?, status = ?, news = ?, chance_of_playing_next_round = ?,
                    total_points = ?, form = ?, points_per_game = ?
                WHERE id = ?
                """,
                [
                    (
                        el["now_cost"],
                        el.get("status"),
                        el.get("news"),
                        el.get("chance_of_playing_next_round"),
                        el.get("total_points"),
                        el.get("form"),
                        el.get("points_per_game"),
                        el["id"],
                    )
                    for el in elements
                ],
            )
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Failed to refresh player prices: {e}")
    return False

def solve_budget_dream_15(league_eval_df: pd.DataFrame, max_budget: float = 100.0) -> pd.DataFrame:
    df = league_eval_df.sort_values(by="Proj_Pts", ascending=False).copy()
    pos_targets = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    selected_ids = []
    team_counts = {}

    for pos, count in pos_targets.items():
        cheapest_pos = df[df["Pos"] == pos].sort_values(by=["Cost", "Proj_Pts"], ascending=[True, False])
        for _, row in cheapest_pos.iterrows():
            t_id = row["team_id"]
            if len([p for p in selected_ids if df.loc[df["id"] == p, "Pos"].values[0] == pos]) < count:
                if team_counts.get(t_id, 0) < 3:
                    selected_ids.append(row["id"])
                    team_counts[t_id] = team_counts.get(t_id, 0) + 1

    current_squad = df[df["id"].isin(selected_ids)].copy()
    improved = True
    while improved:
        improved = False
        best_gain = 0
        best_swap = None
        current_cost = current_squad["Cost"].sum()
        remaining_bank = max_budget - current_cost

        for _, cur_p in current_squad.iterrows():
            pos = cur_p["Pos"]
            cur_team = cur_p["team_id"]
            candidates = df[
                (df["Pos"] == pos) &
                (~df["id"].isin(current_squad["id"])) &
                (df["Proj_Pts"] > cur_p["Proj_Pts"])
            ]

            for _, cand_p in candidates.iterrows():
                cost_diff = cand_p["Cost"] - cur_p["Cost"]
                cand_team = cand_p["team_id"]
                if cost_diff > remaining_bank:
                    continue
                team_count = len(current_squad[current_squad["team_id"] == cand_team])
                if cand_team != cur_team and team_count >= 3:
                    continue
                pts_gain = cand_p["Proj_Pts"] - cur_p["Proj_Pts"]
                if pts_gain > best_gain:
                    best_gain = pts_gain
                    best_swap = (cur_p["id"], cand_p["id"])

        if best_swap:
            drop_id, add_id = best_swap
            current_squad = current_squad[current_squad["id"] != drop_id]
            current_squad = pd.concat([current_squad, df[df["id"] == add_id]])
            improved = True

    return current_squad

def solve_unconstrained_super_15(league_eval_df: pd.DataFrame) -> pd.DataFrame:
    df = league_eval_df.sort_values(by="Proj_Pts", ascending=False).copy()
    pos_targets = {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}
    selected_ids = []
    team_counts = {}

    for pos, target_count in pos_targets.items():
        pos_df = df[df["Pos"] == pos]
        for _, row in pos_df.iterrows():
            t_id = row["team_id"]
            if len([p for p in selected_ids if df.loc[df["id"] == p, "Pos"].values[0] == pos]) < target_count:
                if team_counts.get(t_id, 0) < 3:
                    selected_ids.append(row["id"])
                    team_counts[t_id] = team_counts.get(t_id, 0) + 1

    return df[df["id"].isin(selected_ids)].copy()

from typing import Optional, Tuple

def apply_market_projection_with_movement(
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
) -> Tuple[float, Optional[dict], Optional[dict]]:
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
        final_proj = base_proj_pts * xg_scale
    elif pos in ("GKP", "DEF"):
        base_cs_prob = max(0.05, min(0.65, math.exp(-max(0.6, fdr * 0.4))))
        blended_cs_prob = ((1.0 - market_weight) * base_cs_prob) + (market_weight * mkt_cs_prob)
        if factor_movement:
            blended_cs_prob = max(0.02, min(0.85, blended_cs_prob + (0.25 * team_mv["delta_win"])))
        cs_diff = (blended_cs_prob - base_cs_prob) * 4.0
        final_proj = max(0.5, base_proj_pts + cs_diff)
    else:
        final_proj = base_proj_pts

    diff = mkt_team_xg - fdr_base
    dis_item = None
    if abs(diff) >= 0.30:
        dis_item = {
            "Club": team_short,
            "Fixture": f"{team_short} vs {opp_short}" if is_home else f"{opp_short} vs {team_short}",
            "Model xG": round(fdr_base, 2),
            "Market xG": round(mkt_team_xg, 2),
            "Diff": f"{diff:+.2f}",
            "CS Prob": f"{int(mkt_cs_prob * 100)}%",
            "Verdict": "Market Bullish ↑" if diff > 0 else "Market Bearish ↓",
        }

    move_item = {
        "Club": team_short,
        "Fixture": f"{team_short} vs {opp_short}" if is_home else f"{opp_short} vs {team_short}",
        "Open xG": round(team_mv["open_xg"], 2),
        "Current xG": round(team_mv["curr_xg"], 2),
        "Δ xG": f"{team_mv['delta_xg']:+.2f}",
        "Trend": team_mv["trend"],
        "Signal": team_mv["note"],
    }

    return round(final_proj, 2), dis_item, move_item

def find_best_chip_gw(chip_type: str, squad_df: pd.DataFrame, conn, next_gw_id: int) -> int:
    if chip_type in ("None", "") or next_gw_id >= 19:
        return next_gw_id

    fix_df = pd.read_sql(
        """
        SELECT event, team_h, team_a, team_h_difficulty, team_a_difficulty
        FROM fixtures
        WHERE event >= ? AND event <= 19
        """,
        conn,
        params=[next_gw_id],
    )
    if fix_df.empty:
        return next_gw_id

    best_gw = next_gw_id
    best_score = -999.0

    top_league_attackers = pd.DataFrame()
    if chip_type in ("Wildcard 1", "Free Hit"):
        top_league_attackers = pd.read_sql(
            """
            SELECT team, element_type, form, now_cost 
            FROM players 
            WHERE status = 'a' AND element_type IN (2, 3, 4)
            ORDER BY CAST(form AS FLOAT) DESC 
            LIMIT 30
            """,
            conn,
        )

    for gw in range(next_gw_id, 20):
        gw_fix = fix_df[fix_df["event"] == gw]
        if gw_fix.empty:
            continue

        if chip_type == "Triple Captain":
            gw_score = 0.0
            top_attackers = (
                squad_df[squad_df["Pos"].isin(["MID", "FWD"])]
                .sort_values("Season_Points", ascending=False)
                .head(4)
            )
            for _, p in top_attackers.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team_id"]) | (gw_fix["team_a"] == p["team_id"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team_id"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    form_val = float(p.get("Form", 4.0) or 4.0)
                    h_bonus = 1.15 if is_h else 1.0
                    score = form_val * (6 - fdr) * h_bonus
                    if score > gw_score:
                        gw_score = score
            if gw_score > best_score:
                best_score = gw_score
                best_gw = gw

        elif chip_type == "Bench Boost":
            gw_score = 0.0
            bench = squad_df[squad_df["order"] > 11] if "order" in squad_df.columns else squad_df.tail(4)
            for _, p in bench.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team_id"]) | (gw_fix["team_a"] == p["team_id"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team_id"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    gw_score += (5 - fdr) + (0.5 if is_h else 0)
            if gw_score > best_score:
                best_score = gw_score
                best_gw = gw

        elif chip_type == "Free Hit":
            squad_fixture_pts = 0.0
            for _, p in squad_df.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team_id"]) | (gw_fix["team_a"] == p["team_id"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team_id"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    form_val = float(p.get("Form", 3.5) or 3.5)
                    squad_fixture_pts += form_val * (6.0 - fdr) * (1.1 if is_h else 0.95)

            league_ceiling_pts = 0.0
            for _, p in top_league_attackers.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    form_val = float(p["form"] or 4.0)
                    league_ceiling_pts += form_val * (6.0 - fdr) * (1.15 if is_h else 0.95)

            benchmarked_ceiling = (league_ceiling_pts / max(1, len(top_league_attackers))) * 11.0
            benchmarked_squad = (squad_fixture_pts / max(1, len(squad_df))) * 11.0
            score = benchmarked_ceiling - benchmarked_squad

            if score > best_score:
                best_score = score
                best_gw = gw

        elif chip_type == "Wildcard 1":
            squad_fixture_pts = 0.0
            for _, p in squad_df.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team_id"]) | (gw_fix["team_a"] == p["team_id"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team_id"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    form_val = float(p.get("Form", 3.5) or 3.5)
                    squad_fixture_pts += form_val * (6.0 - fdr) * (1.1 if is_h else 0.95)

            league_ceiling_pts = 0.0
            for _, p in top_league_attackers.iterrows():
                p_fix = gw_fix[(gw_fix["team_h"] == p["team"])]
                if not p_fix.empty:
                    is_h = p_fix["team_h"].values[0] == p["team"]
                    fdr = p_fix["team_h_difficulty"].values[0] if is_h else p_fix["team_a_difficulty"].values[0]
                    form_val = float(p["form"] or 4.0)
                    league_ceiling_pts += form_val * (6.0 - fdr) * (1.15 if is_h else 0.95)

            benchmarked_ceiling = (league_ceiling_pts / max(1, len(top_league_attackers))) * 11.0
            benchmarked_squad = (squad_fixture_pts / max(1, len(squad_df))) * 11.0
            delta = benchmarked_ceiling - benchmarked_squad
            horizon_weight = 1.0 + ((20 - gw) * 0.04)
            score = delta * horizon_weight

            if score > best_score:
                best_score = score
                best_gw = gw

    return best_gw

@st.cache_data(ttl=600, show_spinner=False)
def get_cached_league_eval_df(
    _conn,
    current_gw: int,
    selected_eval_gw: int,
    enable_betting: bool = False,
    market_weight: float = 0.35,
    factor_movement: bool = True,
) -> pd.DataFrame:
    adv_fix_df = pd.read_sql(
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
        params=[current_gw, max(19, selected_eval_gw)],
    )
    all_players_query = """
    SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
           t.short_name AS Team,
           CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
           pos.singular_name AS Position, p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
           p.total_points AS Season_Points, p.expected_goals, p.expected_assists,
           p.form AS Form, p.points_per_game AS PPG, p.expected_goal_involvements_per_90 AS xGI_per_90,
           p.status AS Status, p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE (p.status = 'a' OR p.chance_of_playing_next_round >= 75)
    """
    all_pl_df = pd.read_sql(all_players_query, _conn)
    hist_baselines_df = get_historical_player_baselines(_conn)
    odds_api_key = st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", ""))
    market_cache = fetch_upcoming_betting_odds(odds_api_key) if enable_betting else {}

    league_eval_list = []
    for _, p_row in all_pl_df.iterrows():
        fix_data = get_fixture_for_team(adv_fix_df, p_row["team_id"], selected_eval_gw)
        proj_pts = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)

        if enable_betting and fix_data.get("opponent"):
            opp_short = fix_data["opponent"].replace(" (H)", "").replace(" (A)", "")
            proj_pts, _, _ = apply_market_projection_with_movement(
                _conn,
                proj_pts,
                p_row["Pos"],
                fix_data["fdr"],
                fix_data["is_home"],
                p_row["Team"],
                opp_short,
                market_weight,
                factor_movement,
                market_cache,
            )

        p_eval = dict(p_row)
        p_eval.update({
            "Opponent": fix_data["opponent"],
            "FDR": fix_data["fdr"],
            "Proj_Pts": proj_pts,
        })
        league_eval_list.append(p_eval)

    return pd.DataFrame(league_eval_list)

@st.cache_data(ttl=600, show_spinner=False)
def get_cached_league_dream_15(
    _conn,
    current_gw: int,
    selected_eval_gw: int,
    total_budget: float,
    enable_betting: bool = False,
    market_weight: float = 0.35,
    factor_movement: bool = True,
):
    league_eval_df = get_cached_league_eval_df(
        _conn, current_gw, selected_eval_gw, enable_betting, market_weight, factor_movement
    )
    league_dream_15 = solve_budget_dream_15(league_eval_df, max_budget=total_budget)
    return solve_optimal_xi(league_dream_15)

@st.cache_data(ttl=600, show_spinner=False)
def get_cached_league_super_15(
    _conn,
    current_gw: int,
    selected_eval_gw: int,
    enable_betting: bool = False,
    market_weight: float = 0.35,
    factor_movement: bool = True,
):
    league_eval_df = get_cached_league_eval_df(
        _conn, current_gw, selected_eval_gw, enable_betting, market_weight, factor_movement
    )
    super_15 = solve_unconstrained_super_15(league_eval_df)
    return solve_optimal_xi(super_15)

def render_pitch_component(
    starters_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    is_live: bool = False,
    rolling_df: pd.DataFrame = None,
    fdr_map: dict = None,
):
    if rolling_df is not None or fdr_map is not None:
        starters_df = enrich_squad_df(starters_df, rolling_df, fdr_map)
        if bench_df is not None and not bench_df.empty:
            bench_df = enrich_squad_df(bench_df, rolling_df, fdr_map)

    pos_rows = ["GKP", "DEF", "MID", "FWD"]
    pitch_rows_html = ""

    for pos in pos_rows:
        row_players = starters_df[starters_df["Pos"] == pos]
        players_html = ""
        for _, p in row_players.iterrows():
            mult = int(round(float(p.get("Multiplier", 1)))) if pd.notna(p.get("Multiplier")) else 1
            is_c = (p.get("is_cap") is True or p.get("is_cap") == 1) or mult >= 2
            is_v = (p.get("is_vc") is True or p.get("is_vc") == 1) and not is_c

            cap_badge = ""
            if mult == 3:
                cap_badge = '<div class="pitch-cap-badge tc">3x</div>'
            elif is_c:
                cap_badge = '<div class="pitch-cap-badge c">C</div>'
            elif is_v:
                cap_badge = '<div class="pitch-cap-badge vc">V</div>'

            img_url = get_player_img_url(p.get("photo"), p.get("code"))
            player_name = p.get("Player", "")

            if is_live:
                pts = int(p.get("GW_Points", 0))
                mult_txt = f" ({mult}x)" if mult > 1 else ""
                pts_sub = f"{pts} pts{mult_txt}"
                
                live_mins = p.get("Live_Mins") or 0
                live_bonus = p.get("Live_Bonus") or 0
                live_bps = p.get("Live_BPS") or 0
                
                mins_str = f"{int(live_mins)}'" if live_mins > 0 else "0'"
                bonus_str = f" (+{int(live_bonus)}B)" if live_bonus > 0 else (f" ({int(live_bps)} bps)" if live_bps > 0 else "")
                
                sub_color = "#4ade80" if pts >= 6 else "#f8fafc"
                stat_pill_content = (
                    f'<span style="color: {sub_color}; font-weight: 700; display: block;">{pts_sub}</span>'
                    f'<span style="color: #94a3b8; font-size: 0.62rem; display: block;">{mins_str}{bonus_str}</span>'
                )
            else:
                proj = p.get("Proj_Pts", 0.0)
                cost = p.get("Cost", 0.0)
                cost_str = f"£{fmt_num(cost, '.1f')}m" if cost else ""
                mult_txt = f" ({mult}x)" if mult > 1 else ""
                stat_pill_content = (
                    f'<span style="color: #60a5fa; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;">{fmt_num(proj, ".1f")} xP{mult_txt}</span>'
                    f'<span style="color: #94a3b8; font-size: 0.62rem; display: block; line-height: 1.1; margin-top: 1px;">{cost_str}</span>'
                )

            clean_url = html.escape(str(img_url))
            avatar_style = f"background-image: url('{clean_url}'), url('{SILHOUETTE_BASE64}');"
            tooltip_html = build_player_tooltip(p, is_live=is_live)

            players_html += (
                f'<div class="pitch-player-node">'
                f'{tooltip_html}'
                f'<div class="pitch-avatar-wrap">'
                f'<div class="pitch-player-avatar" style="{avatar_style}"></div>'
                f'{cap_badge}'
                f'</div>'
                f'<div class="pitch-name-pill">{html.escape(player_name)}</div>'
                f'<div class="pitch-stat-pill">{stat_pill_content}</div>'
                f'</div>'
            )
        pitch_rows_html += f'<div class="pitch-formation-row">{players_html}</div>'

    dugout_html = ""
    if bench_df is not None and not bench_df.empty:
        bench_html = ""
        for idx, (_, b) in enumerate(bench_df.iterrows()):
            img_url = get_player_img_url(b.get("photo"), b.get("code"))
            player_name = b.get("Player", "")
            pos = b.get("Pos", "")
            mult = int(round(float(b.get("Multiplier", 1)))) if pd.notna(b.get("Multiplier")) else 1

            if is_live:
                pts = int(b.get("Raw_GW_Pts", 0))
                b_stat_content = f"<span>{pts} pts</span>"
            else:
                proj = b.get("Proj_Pts", 0.0)
                b_cost = b.get("Cost", 0.0)
                b_cost_str = f"£{fmt_num(b_cost, '.1f')}m" if b_cost else ""
                active_bb_badge = " (1x)" if mult == 1 and not is_live else ""
                b_stat_content = (
                    f'<span style="color: #60a5fa; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;">{fmt_num(proj, ".1f")} xP{active_bb_badge}</span>'
                    f'<span style="color: #94a3b8; font-size: 0.62rem; display: block; line-height: 1.1; margin-top: 1px;">{b_cost_str}</span>'
                )

            sub_label = "Sub GKP" if pos == "GKP" else f"Sub {idx}"
            clean_url = html.escape(str(img_url))
            bench_avatar_style = f"background-image: url('{clean_url}'), url('{SILHOUETTE_BASE64}');"
            bench_tooltip_html = build_player_tooltip(b, is_live=is_live)

            bench_html += (
                f'<div class="pitch-player-node bench-node">'
                f'{bench_tooltip_html}'
                f'<div class="bench-order-tag">{sub_label}</div>'
                f'<div class="pitch-avatar-wrap">'
                f'<div class="pitch-player-avatar bench-avatar" style="{bench_avatar_style}"></div>'
                f'</div>'
                f'<div class="pitch-name-pill">{html.escape(player_name)}</div>'
                f'<div class="pitch-stat-pill">{b_stat_content}</div>'
                f'</div>'
            )
        dugout_html = (
            f'<div class="pitch-dugout">'
            f'<div class="dugout-title">BENCH DUGOUT</div>'
            f'<div class="dugout-row">{bench_html}</div>'
            f'</div>'
        )

    full_pitch_html = (
        f'<style>'
        f'.pitch-board-wrap {{ width: 100%; max-width: 100%; margin: 0 auto 1rem auto; position: relative; overflow: visible; }}'
        f'.tactical-pitch {{'
        f'  background: radial-gradient(circle at 50% 50%, #154323 0%, #0c2714 100%);'
        f'  border: 2px solid rgba(255, 255, 255, 0.2);'
        f'  border-radius: 12px;'
        f'  position: relative;'
        f'  overflow: visible;'
        f'  padding: 14px 4px 10px 4px;'
        f'  display: flex;'
        f'  flex-direction: column;'
        f'  justify-content: space-around;'
        f'  height: 520px !important;'
        f'  min-height: 520px !important;'
        f'  max-height: 520px !important;'
        f'  box-sizing: border-box !important;'
        f'  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);'
        f'}}'
        f'.pitch-line {{ position: absolute; pointer-events: none; }}'
        f'.center-line {{ top: 50%; left: 0; right: 0; height: 1.5px; background: rgba(255, 255, 255, 0.12); }}'
        f'.center-circle {{ top: 50%; left: 50%; transform: translate(-50%, -50%); width: 90px; height: 90px; border-radius: 50%; border: 1.5px solid rgba(255, 255, 255, 0.12); }}'
        f'.penalty-box-top {{ top: 0; left: 50%; transform: translateX(-50%); width: 170px; height: 55px; border: 1.5px solid rgba(255, 255, 255, 0.12); border-top: none; }}'
        f'.penalty-arc-top {{ top: 55px; left: 50%; transform: translateX(-50%); width: 60px; height: 25px; border-bottom-left-radius: 30px; border-bottom-right-radius: 30px; border: 1.5px solid rgba(255, 255, 255, 0.12); border-top: none; }}'
        f'.penalty-box-bottom {{ bottom: 0; left: 50%; transform: translateX(-50%); width: 170px; height: 55px; border: 1.5px solid rgba(255, 255, 255, 0.12); border-bottom: none; }}'
        f'.penalty-arc-bottom {{ bottom: 55px; left: 50%; transform: translateX(-50%); width: 60px; height: 25px; border-top-left-radius: 30px; border-top-right-radius: 30px; border: 1.5px solid rgba(255, 255, 255, 0.12); border-bottom: none; }}'
        f'.pitch-formation-row {{ display: flex; justify-content: space-around; align-items: center; z-index: 2; width: 100%; margin: 2px 0; position: relative; }}'
        f'.pitch-player-node {{ display: flex; flex-direction: column; align-items: center; flex: 1; max-width: 68px; min-width: 0; text-align: center; position: relative; cursor: pointer; }}'
        f'.pitch-player-node:hover {{ z-index: 120 !important; }}'
        f'.pitch-avatar-wrap {{ position: relative; width: 44px; height: 44px; margin-bottom: 3px; }}'
        f'.pitch-player-avatar {{'
        f'  width: 44px !important;'
        f'  height: 44px !important;'
        f'  min-width: 44px !important;'
        f'  min-height: 44px !important;'
        f'  border-radius: 50% !important;'
        f'  background-size: cover, cover !important;'
        f'  background-position: top center, center !important;'
        f'  background-repeat: no-repeat, no-repeat !important;'
        f'  border: 2px solid #ffffff !important;'
        f'  background-color: #1e293b !important;'
        f'  box-shadow: 0 2px 6px rgba(0,0,0,0.35) !important;'
        f'}}'
        f'.bench-avatar {{ border-color: #94a3b8 !important; opacity: 0.9; }}'
        f'.pitch-cap-badge {{ position: absolute; top: -4px; right: -4px; width: 18px; height: 18px; border-radius: 50%; font-size: 0.65rem; font-weight: 800; display: flex; align-items: center; justify-content: center; border: 1.5px solid #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.4); }}'
        f'.pitch-cap-badge.c {{ background: #22c55e; color: #ffffff; }}'
        f'.pitch-cap-badge.tc {{ background: #eab308; color: #000000; }}'
        f'.pitch-cap-badge.vc {{ background: #3b82f6; color: #ffffff; }}'
        f'.pitch-name-pill {{ background: #0f172a; color: #f8fafc; font-size: 0.70rem; font-weight: 700; padding: 2px 4px; border-radius: 4px; width: 94%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 1px 3px rgba(0,0,0,0.25); }}'
        f'.pitch-stat-pill {{ background: rgba(15, 23, 42, 0.85); font-size: 0.66rem; font-weight: 700; padding: 1px 4px; border-radius: 3px; margin-top: 2px; border: 1px solid rgba(255, 255, 255, 0.08); width: 94%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box; }}'
        f'.pitch-dugout {{ background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-top: 8px; padding: 8px 6px 14px 6px; position: relative; overflow: visible; min-height: 128px !important; height: auto !important; box-sizing: border-box !important; }}'
        f'.dugout-title {{ font-size: 0.7rem; font-weight: 800; color: #94a3b8; letter-spacing: 0.05em; text-align: center; margin-bottom: 6px; }}'
        f'.dugout-row {{ display: flex; justify-content: space-around; align-items: center; }}'
        f'.bench-node {{ flex: 1; max-width: 64px; }}'
        f'.bench-order-tag {{ font-size: 0.65rem; color: #94a3b8; font-weight: 600; margin-bottom: 2px; }}'
        f'.player-tooltip-card {{'
        f'  visibility: hidden;'
        f'  opacity: 0;'
        f'  position: absolute;'
        f'  bottom: 110%;'
        f'  left: 50%;'
        f'  transform: translateX(-50%) translateY(4px);'
        f'  width: 175px;'
        f'  background: rgba(15, 23, 42, 0.96);'
        f'  backdrop-filter: blur(10px);'
        f'  -webkit-backdrop-filter: blur(10px);'
        f'  border: 1px solid rgba(255, 255, 255, 0.16);'
        f'  border-radius: 8px;'
        f'  padding: 8px 10px;'
        f'  box-shadow: 0 12px 28px rgba(0,0,0,0.65), 0 2px 8px rgba(0,0,0,0.4);'
        f'  z-index: 1000;'
        f'  transition: opacity 0.16s ease, transform 0.16s ease, visibility 0.16s;'
        f'  pointer-events: none;'
        f'  text-align: left;'
        f'}}'
        f'.player-tooltip-card::after {{'
        f'  content: "";'
        f'  position: absolute;'
        f'  top: 100%;'
        f'  left: 50%;'
        f'  margin-left: -5px;'
        f'  border-width: 5px;'
        f'  border-style: solid;'
        f'  border-color: rgba(15, 23, 42, 0.96) transparent transparent transparent;'
        f'}}'
        f'.pitch-player-node:hover .player-tooltip-card {{'
        f'  visibility: visible;'
        f'  opacity: 1;'
        f'  transform: translateX(-50%) translateY(0);'
        f'}}'
        f'.pitch-player-node:first-child .player-tooltip-card {{ left: 0; transform: translateX(0) translateY(4px); }}'
        f'.pitch-player-node:first-child:hover .player-tooltip-card {{ transform: translateX(0) translateY(0); }}'
        f'.pitch-player-node:first-child .player-tooltip-card::after {{ left: 20px; }}'
        f'.pitch-player-node:last-child .player-tooltip-card {{ left: auto; right: 0; transform: translateX(0) translateY(4px); }}'
        f'.pitch-player-node:last-child:hover .player-tooltip-card {{ transform: translateX(0) translateY(0); }}'
        f'.pitch-player-node:last-child .player-tooltip-card::after {{ left: auto; right: 20px; }}'
        f'.pitch-formation-row:first-child .player-tooltip-card {{ bottom: auto; top: 108%; transform: translateX(-50%) translateY(-4px); }}'
        f'.pitch-formation-row:first-child:hover .player-tooltip-card {{ transform: translateX(-50%) translateY(0); }}'
        f'.pitch-formation-row:first-child .player-tooltip-card::after {{ top: auto; bottom: 100%; border-color: transparent transparent rgba(15, 23, 42, 0.96) transparent; }}'
        f'.tt-header {{ display: flex; flex-direction: column; gap: 1px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 5px; margin-bottom: 5px; }}'
        f'.tt-name {{ font-family: "Outfit", sans-serif; font-size: 0.82rem; font-weight: 700; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}'
        f'.tt-badge {{ font-size: 0.68rem; color: #94a3b8; font-weight: 600; }}'
        f'.tt-body {{ display: flex; flex-direction: column; gap: 2.5px; }}'
        f'.tt-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.69rem; color: #94a3b8; }}'
        f'.tt-val {{ font-weight: 700; color: #f1f5f9; }}'
        f'.tt-fdr-easy {{ color: #4ade80 !important; }}'
        f'.tt-fdr-med {{ color: #facc15 !important; }}'
        f'.tt-fdr-hard {{ color: #f87171 !important; }}'
        f'.tt-news {{ font-size: 0.64rem; color: #fb923c; margin-top: 2px; padding-top: 3px; border-top: 1px dashed rgba(255, 255, 255, 0.1); }}'
        f'</style>'
        f'<div class="pitch-board-wrap">'
        f'<div class="tactical-pitch">'
        f'<div class="pitch-line penalty-box-top"></div>'
        f'<div class="pitch-line penalty-arc-top"></div>'
        f'<div class="pitch-line center-circle"></div>'
        f'<div class="pitch-line center-line"></div>'
        f'<div class="pitch-line penalty-box-bottom"></div>'
        f'<div class="pitch-line penalty-arc-bottom"></div>'
        f'{pitch_rows_html}'
        f'</div>'
        f'{dugout_html}'
        f'</div>'
    )
    st.markdown(full_pitch_html, unsafe_allow_html=True)

@st.cache_data(ttl=60, show_spinner=False)
def fetch_live_fixtures(gw: int):
    try:
        url = f"https://fantasy.premierleague.com/api/fixtures/?event={gw}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return {f["id"]: f for f in res.json()}
    except Exception:
        pass
    return {}

def enrich_live_squad_with_fixtures_and_xp(squad_df, conn, selected_gw, current_gw):
    try:
        gw_fixtures_df = pd.read_sql(
            """
            SELECT f.id, f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                   th.short_name AS Home_Team, ta.short_name AS Away_Team,
                   f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff,
                   f.started, f.finished, f.finished_provisional, f.minutes,
                   f.team_h_score, f.team_a_score
            FROM fixtures f
            INNER JOIN teams th ON f.team_h = th.id
            INNER JOIN teams ta ON f.team_a = ta.id
            WHERE f.event = ?
            """,
            conn,
            params=[selected_gw],
        )
    except Exception:
        gw_fixtures_df = pd.DataFrame()

    api_fixes = fetch_live_fixtures(selected_gw)
    try:
        hist_baselines_df = get_historical_player_baselines(conn)
    except Exception:
        hist_baselines_df = pd.DataFrame()

    opponents = []
    fdrs = []
    is_homes = []
    status_list = []
    match_status_desc = []
    xp_list = []

    for _, row in squad_df.iterrows():
        tid = row.get("team_id") or row.get("team")
        match = gw_fixtures_df[(gw_fixtures_df["team_h_id"] == tid) | (gw_fixtures_df["team_a_id"] == tid)] if not gw_fixtures_df.empty else pd.DataFrame()
        if match.empty:
            opponents.append("Blank")
            fdrs.append(5)
            is_homes.append(False)
            status_list.append("finished")
            match_status_desc.append("Blank")
            xp_list.append(0.0)
            continue

        opp_parts = []
        fdrs_part = []
        started_any = False
        finished_all = True
        match_mins_max = 0

        for _, f_row in match.iterrows():
            fid = f_row["id"]
            live_f = api_fixes.get(fid, {})
            is_home = (f_row["team_h_id"] == tid)
            opp_team = f_row["Away_Team"] if is_home else f_row["Home_Team"]
            fdr_val = int(f_row["Home_Diff"] if is_home else f_row["Away_Diff"])
            opp_parts.append(f"{opp_team} (H)" if is_home else f"{opp_team} (A)")
            fdrs_part.append(fdr_val)

            f_started = bool(live_f.get("started", f_row["started"]))
            f_finished = bool(live_f.get("finished", f_row["finished"]) or live_f.get("finished_provisional", f_row["finished_provisional"]))
            f_mins = int(live_f.get("minutes", f_row["minutes"]) or 0)
            if f_mins > match_mins_max:
                match_mins_max = f_mins

            if f_started:
                started_any = True
            if not f_finished:
                finished_all = False

        opp_str = " & ".join(opp_parts)
        fdr = int(round(sum(fdrs_part) / len(fdrs_part))) if fdrs_part else 3
        is_home_primary = (match.iloc[0]["team_h_id"] == tid)

        p_mins = int(row.get("Live_Mins") or 0)
        fix_info = {"opponent": opp_str, "fdr": fdr, "is_home": is_home_primary}
        base_xp = calculate_projected_points(row.to_dict(), fix_info, current_gw, hist_baselines_df)
        mult = int(round(float(row.get("Multiplier", 1)))) if pd.notna(row.get("Multiplier")) else 1
        final_xp = round(base_xp * mult, 1)

        if finished_all or p_mins >= 90:
            status_kind = "finished"
            status_desc = f"FT · {p_mins}'" if p_mins > 0 else "FT · Unused"
        elif started_any or p_mins > 0:
            status_kind = "live"
            display_mins = p_mins if p_mins > 0 else match_mins_max
            status_desc = f"LIVE {display_mins}'"
        else:
            status_kind = "upcoming"
            status_desc = "Yet to Play"

        opponents.append(opp_str)
        fdrs.append(fdr)
        is_homes.append(is_home_primary)
        status_list.append(status_kind)
        match_status_desc.append(status_desc)
        xp_list.append(final_xp)

    squad_df["Opponent"] = opponents
    squad_df["FDR"] = fdrs
    squad_df["Is_Home"] = is_homes
    squad_df["Match_Status"] = status_list
    squad_df["Match_Status_Desc"] = match_status_desc
    squad_df["Proj_Pts"] = xp_list

    return squad_df

def render_match_tracker_sidebar(starters_df, bench_df, user_eval_pts=0, is_dark=True):
    bg_panel = "#141414" if is_dark else "#ffffff"
    border_panel = "#27272a" if is_dark else "#e2e8f0"
    text_main = "#f8fafc" if is_dark else "#0f172a"
    text_sub = "#94a3b8" if is_dark else "#64748b"
    row_border = "rgba(255, 255, 255, 0.05)" if is_dark else "#f1f5f9"
    stat_box_bg = "rgba(255, 255, 255, 0.03)" if is_dark else "#f8fafc"
    stat_box_border = "rgba(255, 255, 255, 0.07)" if is_dark else "#e2e8f0"

    played_starters = starters_df[starters_df["Match_Status"].isin(["finished", "live"])] if "Match_Status" in starters_df.columns else pd.DataFrame()
    upcoming_starters = starters_df[starters_df["Match_Status"] == "upcoming"] if "Match_Status" in starters_df.columns else starters_df

    played_count = len(played_starters)
    total_starters = len(starters_df)
    played_label = f"{played_count}/{total_starters} Played" if total_starters > 0 else f"{played_count} Played"
    remaining_xp = float(upcoming_starters["Proj_Pts"].sum()) if not upcoming_starters.empty and "Proj_Pts" in upcoming_starters.columns else 0.0
    projected_final = user_eval_pts + remaining_xp
    has_remaining_xp = round(remaining_xp, 1) > 0.0
    score_label = "Score + xP" if has_remaining_xp else "Score"
    xp_addon = f' <span style="font-size: 0.72rem; font-weight: 600; color: #60a5fa;">(+{remaining_xp:.1f} xP)</span>' if has_remaining_xp else ""
    projected_html = (
        f"""<div style="text-align: right;">
            <span style="font-size: 0.64rem; color: {text_sub}; text-transform: uppercase; font-weight: 700; letter-spacing: 0.03em;">Projected</span><br>
            <span style="font-size: 0.90rem; font-weight: 800; color: #4ade80;">{projected_final:.1f} pts</span>
        </div>"""
        if has_remaining_xp else ""
    )

    def build_player_row(row, is_bench=False, bench_label=""):
        p_name = html.escape(str(row.get("Player", "")))
        pos = str(row.get("Pos", ""))
        mult = int(round(float(row.get("Multiplier", 1)))) if pd.notna(row.get("Multiplier")) else 1
        is_c = (row.get("is_cap") is True or row.get("is_cap") == 1) or mult >= 2
        is_v = (row.get("is_vc") is True or row.get("is_vc") == 1) and not is_c

        cap_badge = ""
        if mult == 3:
            cap_badge = '<span class="trk-cap-badge trk-tc">3x</span>'
        elif is_c:
            cap_badge = '<span class="trk-cap-badge trk-c">C</span>'
        elif is_v:
            cap_badge = '<span class="trk-cap-badge trk-vc">V</span>'

        img_url = get_player_img_url(row.get("photo"), row.get("code"))
        clean_url = html.escape(str(img_url))

        opp = html.escape(str(row.get("Opponent", "-")))
        fdr = int(row.get("FDR", 3))
        fdr_col = "#4ade80" if fdr <= 2 else ("#facc15" if fdr == 3 else "#f87171")

        status = row.get("Match_Status", "upcoming")
        p_mins = int(row.get("Live_Mins") or 0)
        gw_pts = int(row.get("GW_Points", 0))
        xp_val = float(row.get("Proj_Pts", 0.0))

        if status == "finished":
            val_html = f'<span class="trk-val pts">{gw_pts} pts</span>'
            status_badge = f'<span class="trk-badge badge-ft">FT</span>'
        elif status == "live":
            val_html = f'<span class="trk-val pts live">{gw_pts} pts</span>'
            live_label = f"&bull; {p_mins}'" if p_mins > 0 else "&bull; LIVE"
            status_badge = f'<span class="trk-badge badge-live">{live_label}</span>'
        else:
            val_html = f'<span class="trk-val xp">{xp_val:.1f} xP</span>'
            status_badge = f'<span class="trk-badge badge-yet">Yet to play</span>'

        sub_label_html = f'<span class="trk-sub-role">{bench_label} &middot; </span>' if is_bench else ""

        return textwrap.dedent(f"""
        <div class="trk-row">
            <div class="trk-left">
                <div class="trk-avatar" style="background-image: url('{clean_url}'), url('{SILHOUETTE_BASE64}');"></div>
                <div class="trk-meta">
                    <div class="trk-name-row">
                        <span class="trk-name">{p_name}</span>
                        {cap_badge}
                    </div>
                    <div class="trk-sub">
                        {sub_label_html}<span class="trk-pos">{pos}</span> &middot; <span style="color: {fdr_col}; font-weight: 600;">{opp}</span>
                    </div>
                </div>
            </div>
            <div class="trk-right">
                {val_html}
                {status_badge}
            </div>
        </div>
        """).strip()

    starters_html = "\n".join(build_player_row(r) for _, r in starters_df.iterrows())

    bench_html = ""
    if bench_df is not None and not bench_df.empty:
        bench_rows = []
        for idx, (_, b) in enumerate(bench_df.iterrows()):
            role = "Sub GKP" if b.get("Pos") == "GKP" else f"Sub {idx}"
            bench_rows.append(build_player_row(b, is_bench=True, bench_label=role))
        bench_html = textwrap.dedent(f"""
        <div class="trk-bench-hdr">Bench Substitutes</div>
        {"".join(bench_rows)}
        """).strip()

    sidebar_html = textwrap.dedent(f"""
    <style>
    .trk-card {{
        background: {bg_panel};
        border: 1px solid {border_panel};
        border-radius: 12px;
        padding: 12px 14px;
        height: 680px;
        max-height: 680px;
        display: flex;
        flex-direction: column;
        box-sizing: border-box;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    }}
    .trk-header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
        padding-bottom: 6px;
        border-bottom: 1px solid {row_border};
    }}
    .trk-title {{
        font-family: 'Outfit', sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
        color: {text_main};
    }}
    .trk-summary-box {{
        background: {stat_box_bg};
        border: 1px solid {stat_box_border};
        border-radius: 8px;
        padding: 6px 10px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-shrink: 0;
    }}
    .trk-list-container {{
        overflow-y: auto;
        flex: 1;
        padding-right: 4px;
    }}
    .trk-list-container::-webkit-scrollbar {{
        width: 4px;
    }}
    .trk-list-container::-webkit-scrollbar-thumb {{
        background: rgba(255, 255, 255, 0.16);
        border-radius: 2px;
    }}
    .trk-row {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 2px;
        border-bottom: 1px solid {row_border};
        transition: background 0.15s ease;
    }}
    .trk-row:hover {{
        background: rgba(255, 255, 255, 0.02);
    }}
    .trk-row:last-child {{
        border-bottom: none;
    }}
    .trk-left {{
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        flex: 1;
    }}
    .trk-avatar {{
        width: 28px;
        height: 28px;
        min-width: 28px;
        min-height: 28px;
        border-radius: 50%;
        background-size: cover, cover;
        background-position: top center, center;
        background-repeat: no-repeat, no-repeat;
        border: 1.5px solid rgba(255, 255, 255, 0.2);
        background-color: #1e293b;
        flex-shrink: 0;
    }}
    .trk-meta {{
        display: flex;
        flex-direction: column;
        gap: 1px;
        min-width: 0;
    }}
    .trk-name-row {{
        display: flex;
        align-items: center;
        gap: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .trk-name {{
        font-family: 'Inter', sans-serif;
        font-size: 0.80rem;
        font-weight: 700;
        color: {text_main};
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .trk-cap-badge {{
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 0.60rem;
        font-weight: 800;
        line-height: 1;
    }}
    .trk-c {{ background: #22c55e; color: #ffffff; }}
    .trk-tc {{ background: #eab308; color: #000000; }}
    .trk-vc {{ background: #3b82f6; color: #ffffff; }}
    .trk-sub {{
        font-size: 0.68rem;
        color: {text_sub};
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .trk-pos {{
        font-weight: 600;
        color: {text_sub};
    }}
    .trk-sub-role {{
        color: #eab308;
        font-weight: 600;
    }}
    .trk-right {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 2px;
        flex-shrink: 0;
        margin-left: 6px;
    }}
    .trk-val {{
        font-size: 0.80rem;
        font-weight: 800;
        white-space: nowrap;
    }}
    .trk-val.pts {{ color: {text_main}; }}
    .trk-val.pts.live {{ color: #22c55e; }}
    .trk-val.xp {{ color: #60a5fa; }}
    .trk-badge {{
        font-size: 0.60rem;
        font-weight: 700;
        padding: 1px 4px;
        border-radius: 4px;
        white-space: nowrap;
    }}
    .badge-ft {{
        background: rgba(148, 163, 184, 0.15);
        color: {text_sub};
    }}
    .badge-live {{
        background: rgba(34, 197, 94, 0.18);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.35);
        animation: pulseLive 2s infinite;
    }}
    .badge-yet {{
        background: rgba(96, 165, 250, 0.12);
        color: #93c5fd;
    }}
    @keyframes pulseLive {{
        0% {{ opacity: 1; }}
        50% {{ opacity: 0.55; }}
        100% {{ opacity: 1; }}
    }}
    .trk-bench-hdr {{
        font-size: 0.68rem;
        font-weight: 800;
        color: {text_sub};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 8px 0 4px 0;
        padding-top: 6px;
        border-top: 1px solid {row_border};
    }}
    </style>
    <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px;">
        <span style="font-size: 0.92rem; font-weight: 700; color: {text_main};">Match Tracker</span>
        <span style="font-size: 0.80rem; font-weight: 600; color: {text_sub}; margin-left: 6px;">({played_label})</span>
    </div>
    <div class="trk-card">
        <div class="trk-summary-box">
            <div>
                <span style="font-size: 0.64rem; color: {text_sub}; text-transform: uppercase; font-weight: 700; letter-spacing: 0.03em;">{score_label}</span><br>
                <span style="font-size: 0.90rem; font-weight: 800; color: {text_main};">{user_eval_pts} pts{xp_addon}</span>
            </div>
            {projected_html}
        </div>
        <div class="trk-list-container">
            {starters_html}
            {bench_html}
        </div>
    </div>
    """)
    clean_sidebar_html = "\n".join(line.strip() for line in textwrap.dedent(sidebar_html).splitlines() if line.strip())
    st.markdown(clean_sidebar_html, unsafe_allow_html=True)

def render_squad_analyzer_tab(conn, events_df, current_gw):
    col_t4_hdr, col_t4_pop = st.columns([6.2, 0.8], vertical_alignment="center")
    with col_t4_hdr:
        section_header(
            "Squad Analyzer & Best 11",
            "Audit live lineup & solve optimal starting XI for future gameweeks",
        )
    with col_t4_pop:
        render_guide_popover(
            title="Squad Analyzer & Best 11",
            subtitle="Audit live lineup, inspect player rolling metrics, and solve optimal starting XI for future gameweeks",
            items=[
                {"badge": "Global Sync", "title": "Manager Profile Sync", "desc": "Syncs your active 15-man squad, bank balance, and chip availability directly from the official FPL API.", "color": "#38bdf8"},
                {"badge": "Hover Intel", "title": "Pitch Overlay Metrics", "desc": "Hover over any pitch card to inspect rolling form, xGI/90, average minutes, and upcoming 5-GW fixture difficulty.", "color": "#10b981"},
                {"badge": "Chips", "title": "Chip Strategy Simulation", "desc": "Click any active chip pill (Wildcard, Free Hit, Bench Boost, Triple Captain) to project outcomes across future gameweeks.", "color": "#818cf8"},
                {"badge": "View Modes", "title": "Pitch vs. List Layout", "desc": "Toggle between a tactical soccer pitch formation view and dense, sortable list view cards.", "color": "#38bdf8"},
                {"badge": "Benchmarks", "title": "Dream 11 & Super Team", "desc": "Compare your optimal XI head-to-head against the Budget Dream 11 (within your budget) or unconstrained Super Team.", "color": "#f59e0b"},
                {"badge": "Pre-Lock", "title": "Lock Lineup Snapshot", "desc": "Lock your squad pre-deadline to track model performance and compute variance in the Audit Journal.", "color": "#10b981"},
            ],
            tip="Use the Betting Market overlay toggle to blend bookmaker implied goal totals and market line velocity with statistical projection models before locking your lineup.",
            key="guide_pop_squad_analyzer",
        )

    mgr_to_use = st.session_state.get("manager_id", "").strip()

    if not mgr_to_use:
        st.info(":material/arrow_upward:  Click 'Enter FPL ID' in the top-right header to load your squad analysis.")
        return

    try:
        mgr_data = fetch_manager_entry(mgr_to_use)
        if not mgr_data:
            st.error("Could not load team. Verify your FPL ID in the search bar above.")
            return

        rolling_metrics_df = get_rolling_player_metrics(conn)
        teams_fdr_map = get_teams_fdr_map(conn, current_gw)

        mgr_history = fetch_manager_history(mgr_to_use)
        total_points = mgr_data.get("summary_overall_points", 0)
        overall_rank = mgr_data.get("summary_overall_rank", 0)

        current_season_history = mgr_history.get("current", [])
        rank_delta_str = None
        if len(current_season_history) >= 2:
            latest_rank = current_season_history[-1].get("overall_rank", overall_rank)
            prev_rank = current_season_history[-2].get("overall_rank", latest_rank)
            rank_diff = prev_rank - latest_rank
            
            if rank_diff != 0:
                rank_delta_str = f"{rank_diff:+,}"

        import time
        now_epoch = int(time.time())

        finished_gw_ids = []
        ongoing_gw_ids = []
        upcoming_gws = []

        for _, r in events_df.iterrows():
            gw_id = int(r["id"])
            
            # Robust boolean parsing to handle SQLite/Pandas type variations (1, "1", True, "True")
            is_fin = str(r.get("finished", "")).strip().lower() in ["1", "true", "yes"]
            is_cur = str(r.get("is_current", "")).strip().lower() in ["1", "true", "yes"]
            
            try:
                dl_epoch = int(r.get("deadline_time_epoch", 2000000000))
            except (ValueError, TypeError):
                dl_epoch = 2000000000
                
            if is_fin:
                finished_gw_ids.append(gw_id)
            elif is_cur or dl_epoch <= now_epoch:
                ongoing_gw_ids.append(gw_id)
            else:
                upcoming_gws.append(gw_id)

        ongoing_gw = ongoing_gw_ids[0] if ongoing_gw_ids else None
        last_finished_gw = max(finished_gw_ids) if finished_gw_ids else None
        next_gw_id = upcoming_gws[0] if upcoming_gws else current_gw

        all_gw_options = []
        if last_finished_gw is not None:
            all_gw_options.append(last_finished_gw)
        if ongoing_gw is not None:
            all_gw_options.append(ongoing_gw)
        all_gw_options.append(next_gw_id)
        all_gw_options = sorted(list(dict.fromkeys(all_gw_options)))

        def format_gw_label(g):
            if g in finished_gw_ids:
                return f"GW {g} (Finished)"
            elif g == ongoing_gw:
                return f"GW {g} (Live)"
            elif g == next_gw_id:
                return f"GW {g} (Upcoming)"
            else:
                return f"GW {g}"

        default_gw = ongoing_gw if ongoing_gw else next_gw_id

        if "tab4_selected_gw" not in st.session_state or st.session_state["tab4_selected_gw"] not in all_gw_options:
            st.session_state["tab4_selected_gw"] = default_gw

        default_idx = (
            all_gw_options.index(st.session_state["tab4_selected_gw"])
            if st.session_state["tab4_selected_gw"] in all_gw_options
            else 0
        )
        
        # Chip Selector for Upcoming GW
        active_chip = "None"
        if st.session_state["tab4_selected_gw"] == next_gw_id:
            active_chip = st.selectbox("Active Chip This GW:", ["None", "Triple Captain", "Bench Boost", "Free Hit"], key="tab4_active_chip")

        col_gw_sel, col_gw_ref = st.columns([6.2, 0.8], vertical_alignment="center")
        with col_gw_sel:
            selected_eval_gw = st.radio(
                ":material/calendar_month:  **Select Gameweek:**",
                options=all_gw_options,
                index=default_idx,
                format_func=format_gw_label,
                horizontal=True,
                key="tab4_selected_gw",
            )

        with col_gw_ref:
            if st.button(":material/sync:  Refresh", use_container_width=True, help="Sync prices, chip status, and odds snapshots"):
                fetch_manager_entry.clear()
                fetch_manager_transfers.clear()
                fetch_manager_history.clear()
                fetch_manager_picks.clear()
                fetch_live_gameweek_points.clear()
                fetch_motw_manager_data.clear()
                fetch_dream_team_data.clear()
                get_rolling_player_metrics.clear()
                get_teams_fdr_map.clear()
                get_cached_league_eval_df.clear()
                get_cached_league_dream_15.clear()
                get_cached_league_super_15.clear()
                with st.spinner("Syncing latest odds & gameweeks..."):
                    quick_sync_live_prices(conn)
                    odds_key = st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", ""))
                    sync_fixture_odds_snapshots(conn, odds_key)
                st.toast("Dashboard & odds synced!", icon=":material/bolt: ")
                st.rerun()

        picks_data = fetch_manager_picks(mgr_to_use, selected_eval_gw, next_gw_id)
        entry_history = picks_data.get("entry_history", {})
        transfers_cost = entry_history.get("event_transfers_cost", 0)
        base_bank = entry_history.get("bank", mgr_data.get("last_deadline_bank", 0))

        picks_list = picks_data.get("picks", [])
        pick_ids = [p["element"] for p in picks_list]
        
        if selected_eval_gw == next_gw_id:
            pending_transfers = fetch_manager_transfers(mgr_to_use)
            if pending_transfers:
                for t in reversed(pending_transfers):
                    if t.get("event") == next_gw_id:
                        out_id = t.get("element_out")
                        in_id = t.get("element_in")
                        out_cost = t.get("element_out_cost")
                        in_cost = t.get("element_in_cost")
                        if out_id in pick_ids:
                            idx = pick_ids.index(out_id)
                            pick_ids[idx] = in_id
                            base_bank = base_bank + out_cost - in_cost
                            # Also update picks_list so order is maintained
                            for p in picks_list:
                                if p["element"] == out_id:
                                    p["element"] = in_id
                                    break
                                
        bank_balance = base_bank / 10.0
        if not pick_ids:
            st.warning("No squad picks found for this manager.")
            return

        placeholders = ",".join(["?"] * len(pick_ids))
        squad_query = f"""
        SELECT
            p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
            t.short_name AS Team,
            CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
            pos.singular_name AS Position, p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
            p.total_points AS Season_Points, p.expected_goals, p.expected_assists,
            p.form AS Form, p.points_per_game AS PPG, p.expected_goal_involvements_per_90 AS xGI_per_90,
            p.news AS News, p.status AS Status, p.chance_of_playing_next_round AS Chance
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        INNER JOIN positions pos ON p.element_type = pos.id
        WHERE p.id IN ({placeholders})
        """
        squad_df = pd.read_sql(squad_query, conn, params=pick_ids)

        meta_dict = {
            p["element"]: {
                "multiplier": p["multiplier"],
                "is_captain": p["is_captain"],
                "is_vice": p["is_vice_captain"],
                "order": p["position"],
            }
            for p in picks_list
        }
        squad_df["order"] = squad_df["id"].map(lambda x: meta_dict[x]["order"])
        squad_df["Multiplier"] = squad_df["id"].map(lambda x: meta_dict[x]["multiplier"])
        squad_df["is_cap"] = squad_df["id"].map(lambda x: meta_dict[x]["is_captain"])
        squad_df["is_vc"] = squad_df["id"].map(lambda x: meta_dict[x]["is_vice"])

        active_calc_gw = selected_eval_gw
        live_points_map = fetch_live_gameweek_points(active_calc_gw)
        squad_df["Raw_GW_Pts"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("total_points", 0))
        squad_df["Live_Mins"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("minutes", 0))
        squad_df["Live_Bonus"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("bonus", 0))
        squad_df["Live_BPS"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("bps", 0))
        squad_df["Live_Explain"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("explain", []))
        squad_df["GW_Points"] = squad_df["Raw_GW_Pts"] * squad_df["Multiplier"]

        starting_xi_pts = squad_df[squad_df["order"] <= 11]["GW_Points"].sum()
        active_gw_pts = int(starting_xi_pts) - transfers_cost

        squad_value = float(squad_df["Cost"].sum()) if not squad_df.empty else 100.0
        total_team_value = squad_value + bank_balance
        active_score_label = f"{active_gw_pts} pts (Live)" if (selected_eval_gw == ongoing_gw) else f"{active_gw_pts} pts"

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("Manager", mgr_data.get("name", "My Team"))
        m2.metric("Overall Rank", f"{overall_rank:,}", delta=rank_delta_str)
        m3.metric("Total Points", f"{total_points:,}")
        m4.metric(
            "Active GW",
            active_score_label,
            delta=f"-{transfers_cost} hit" if transfers_cost > 0 else None,
            delta_color="inverse",
        )
        m5.metric("Squad Value", f"£{squad_value:.1f}m")
        m6.metric("In The Bank", f"£{bank_balance:.1f}m")

        is_finished_gw = selected_eval_gw in finished_gw_ids
        is_ongoing_gw = (selected_eval_gw == ongoing_gw)
        is_live_or_finished = is_finished_gw or is_ongoing_gw

        market_weight = 0.35
        factor_movement = True
        enable_betting = False
        super_team_mode = False

        if is_live_or_finished:
            col_tgl1, col_tgl2, col_tgl3, col_pad = st.columns([1.2, 1.3, 1.3, 6.2], vertical_alignment="center")
            with col_tgl1:
                pitch_view = st.toggle(":material/stadium: **Pitch View**", value=True, key="tab4_pitch_toggle")
            with col_tgl2:
                enable_comparison = st.toggle(":material/balance:  **Comparison**", value=False, key="tab4_compare_toggle")
            with col_tgl3:
                if enable_comparison:
                    super_team_mode = st.toggle(":material/star:  **Super Team**", value=False, key="tab4_super_team_toggle")
        else:
            col_tgl1, col_tgl2, col_tgl3, col_pad, col_tgl4, col_m1, col_m2 = st.columns(
                [1.3, 1.4, 1.4, 0.5, 1.8, 2.0, 1.6], 
                vertical_alignment="bottom"
            )
            with col_tgl1:
                pitch_view = st.toggle(":material/stadium: **Pitch View**", value=True, key="tab4_pitch_toggle")
            with col_tgl2:
                enable_comparison = st.toggle(":material/balance:  **Comparison**", value=False, key="tab4_compare_toggle")
            with col_tgl3:
                if enable_comparison:
                    super_team_mode = st.toggle(":material/star:  **Super Team**", value=False, key="tab4_super_team_toggle")
            
            with col_tgl4:
                enable_betting = st.toggle(":material/bar_chart:  **Betting Market**", value=True, key="tab4_enable_betting")
                
            if enable_betting:
                with col_m1:
                    market_weight = st.slider(
                        "Market Weight",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.35,
                        step=0.05,
                        format="%.2f",
                        key="tab4_mkt_weight",
                        help="0.0 = 100% Model | 1.0 = 100% Betting Odds",
                    )
                with col_m2:
                    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)
                    factor_movement = st.checkbox(":material/bolt: Line Movement", value=True, key="tab4_factor_movement")

        if is_live_or_finished:
            live_loader = st.empty()
            with live_loader.container():
                render_optimizer_status(
                    title="Syncing Live Match Center...",
                    subtext="Pulling real-time stats and competitor lineup...",
                )
                render_skeleton_cards(count=1)

            if selected_eval_gw != active_calc_gw:
                eval_live_pts_map = fetch_live_gameweek_points(selected_eval_gw)
                squad_df["Raw_GW_Pts"] = squad_df["id"].map(lambda x: eval_live_pts_map.get(x, {}).get("total_points", 0))
                squad_df["Live_Mins"] = squad_df["id"].map(lambda x: eval_live_pts_map.get(x, {}).get("minutes", 0))
                squad_df["Live_Bonus"] = squad_df["id"].map(lambda x: eval_live_pts_map.get(x, {}).get("bonus", 0))
                squad_df["Live_BPS"] = squad_df["id"].map(lambda x: eval_live_pts_map.get(x, {}).get("bps", 0))
                squad_df["GW_Points"] = squad_df["Raw_GW_Pts"] * squad_df["Multiplier"]
                starting_xi_pts = squad_df[squad_df["order"] <= 11]["GW_Points"].sum()
                user_eval_pts = int(starting_xi_pts) - transfers_cost
            else:
                user_eval_pts = active_gw_pts

            squad_df = enrich_live_squad_with_fixtures_and_xp(squad_df, conn, selected_eval_gw, current_gw)

            motw_manager_data = fetch_motw_manager_data(selected_eval_gw)
            dream_team_data = fetch_dream_team_data(selected_eval_gw)

            if super_team_mode:
                comp_data = dream_team_data or motw_manager_data
                raw_title = comp_data.get("manager_name", "Team of the Week") if comp_data else "Super Team"
                comp_title = (raw_title[:20] + "..") if len(raw_title) > 22 else raw_title
            else:
                comp_data = motw_manager_data or dream_team_data
                raw_title = comp_data.get("manager_name", "Manager of the Week") if comp_data else "Top Performer"
                comp_title = (raw_title[:20] + "..") if len(raw_title) > 22 else raw_title

            comp_pts = comp_data["total_score"] if comp_data else 0
            pts_diff = user_eval_pts - comp_pts

            banner_title = f"Gameweek {selected_eval_gw} Live Match Center" if is_ongoing_gw else f"Gameweek {selected_eval_gw} Performance Review"
            score_subtext = f"Your Score: <strong>{user_eval_pts} pts (Live)</strong>" if is_ongoing_gw else f"Your Score: <strong>{user_eval_pts} pts</strong>"
            top_subtext = f"Comparing against <strong>{comp_title}</strong>: <strong>{comp_pts} pts</strong>"

            user_starters = squad_df[squad_df["order"] <= 11].sort_values("order")
            user_bench = squad_df[squad_df["order"] > 11].sort_values("order")

            if enable_comparison and comp_data:
                comp_pick_ids = [p["element"] for p in comp_data["picks"]]
                comp_placeholders = ",".join(["?"] * len(comp_pick_ids))
                comp_df = pd.read_sql(
                    squad_query.replace(placeholders, comp_placeholders),
                    conn,
                    params=comp_pick_ids,
                )
                comp_meta = {p["element"]: p for p in comp_data["picks"]}
                comp_df["order"] = comp_df["id"].map(lambda x: comp_meta[x]["position"])
                comp_df["Multiplier"] = comp_df["id"].map(lambda x: comp_meta[x]["multiplier"])
                comp_df["is_cap"] = comp_df["id"].map(lambda x: comp_meta[x]["is_captain"])
                comp_df["is_vc"] = comp_df["id"].map(lambda x: comp_meta[x]["is_vice_captain"])

                comp_live_pts_map = fetch_live_gameweek_points(selected_eval_gw)
                comp_df["Raw_GW_Pts"] = comp_df["id"].map(lambda x: comp_live_pts_map.get(x, {}).get("total_points", 0))
                comp_df["Live_Mins"] = comp_df["id"].map(lambda x: comp_live_pts_map.get(x, {}).get("minutes", 0))
                comp_df["Live_Bonus"] = comp_df["id"].map(lambda x: comp_live_pts_map.get(x, {}).get("bonus", 0))
                comp_df["Live_BPS"] = comp_df["id"].map(lambda x: comp_live_pts_map.get(x, {}).get("bps", 0))
                comp_df["Live_Explain"] = comp_df["id"].map(lambda x: comp_live_pts_map.get(x, {}).get("explain", []))
                comp_df["GW_Points"] = comp_df["Raw_GW_Pts"] * comp_df["Multiplier"]

                comp_df = enrich_live_squad_with_fixtures_and_xp(comp_df, conn, selected_eval_gw, current_gw)

                comp_starters = comp_df[comp_df["order"] <= 11].sort_values("order")
                comp_bench = comp_df[comp_df["order"] > 11].sort_values("order")

            live_loader.empty()

            is_dark = st.session_state.get("theme_mode", "dark") == "dark"
            banner_bg = "#151d24" if is_dark else "#ffffff"
            banner_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
            banner_title_col = "#f8fafc" if is_dark else "#0f172a"
            banner_sub_col = "#94a3b8" if is_dark else "#64748b"

            st.markdown(
                f"""
                <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; padding: 0.9rem 1.1rem; margin: 0.5rem 0 1.2rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 1rem; font-weight: 700; color: {banner_title_col};">{banner_title}</span><br>
                            <span style="font-size: 0.8rem; color: {banner_sub_col};">{score_subtext} · {top_subtext}</span>
                        </div>
                        <span style="font-size: 1.15rem; font-weight: 800; color: {'#22c55e' if pts_diff >= 0 else '#ef4444'};">{pts_diff:+d} pts vs Comp</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Extract GW Rank
            gw_rank = entry_history.get("rank")
            if not gw_rank:
                gw_rank_str = "Updating..."
            else:
                gw_rank_str = f"{gw_rank:,}"

            # Calculate Players Played (Aligns with Match Tracker fixture status)
            played_count = len(user_starters[user_starters["Match_Status"].isin(["finished", "live"])])
            if is_finished_gw:
                played_str = "All Played"
            else:
                played_str = f"{played_count} / 11"

            # Get Captain Stats
            cap_row = user_starters[user_starters["is_cap"] == True]
            if not cap_row.empty:
                cap_name = cap_row.iloc[0]["Player"]
                cap_pts = cap_row.iloc[0]["GW_Points"]
                cap_label = f"{cap_name} (C)"
            else:
                cap_label = "Captain (C)"
                cap_pts = 0

            # Determine delta/hit for Net GW Points
            if enable_comparison and comp_data:
                pts_delta_str = f"{pts_diff:+d} vs Comp" 
            elif transfers_cost > 0:
                pts_delta_str = f"-{transfers_cost} hit"
            else:
                pts_delta_str = None

            pts_label = "Net GW Points (Live)" if is_ongoing_gw else "Net GW Points (Finished)"
            
            col_met1, col_met2, col_met3, col_met4 = st.columns(4)
            col_met1.metric(pts_label, f"{user_eval_pts} pts", delta=pts_delta_str)
            col_met2.metric("Gameweek Rank", gw_rank_str)
            col_met3.metric("Players Played", played_str)
            col_met4.metric(cap_label, f"{cap_pts} pts")
            
            if enable_comparison and comp_data:
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">Your Squad · GW{selected_eval_gw}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({user_eval_pts} pts)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if pitch_view:
                        render_pitch_component(
                            user_starters,
                            user_bench,
                            is_live=True,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    else:
                        for idx, (_, row) in enumerate(user_starters.iterrows()):
                            tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                            mult = int(round(float(row.get("Multiplier", 1))))
                            mult_label = f" ({mult}x)" if mult > 1 else ""
                            if mult == 3:
                                tags.append(("Triple Captain (3x)", "yellow"))
                            elif row.get("is_cap") is True:
                                tags.append(("Captain (2x)", "green"))
                            elif row.get("is_vc") is True:
                                tags.append(("Vice Captain", "yellow"))
                            
                            pts = int(row.get("GW_Points", 0))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                tags,
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>{mult_label}',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )
                        if not user_bench.empty:
                            st.markdown("##### :material/chair:  Bench")
                            for idx, (_, row) in enumerate(user_bench.iterrows()):
                                sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                                pts = int(row.get("Raw_GW_Pts", 0))
                                render_list_card(
                                    f"{row['Player']} · {row['Team']}",
                                    [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                    f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>',
                                    img_url=get_player_img_url(row.get("photo"), row.get("code")),
                                )
                with col_right:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">{comp_title}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({comp_pts} pts)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if pitch_view:
                        render_pitch_component(
                            comp_starters,
                            comp_bench,
                            is_live=True,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    else:
                        for idx, (_, row) in enumerate(comp_starters.iterrows()):
                            tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                            mult = int(round(float(row.get("Multiplier", 1))))
                            mult_label = f" ({mult}x)" if mult > 1 else ""
                            if mult == 3:
                                tags.append(("Triple Captain (3x)", "yellow"))
                            elif row.get("is_cap") is True:
                                tags.append(("Captain (2x)", "green"))
                            elif row.get("is_vc") is True:
                                tags.append(("Vice Captain", "yellow"))
                            
                            pts = int(row.get("GW_Points", 0))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                tags,
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>{mult_label}',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )
                        if not comp_bench.empty:
                            st.markdown("##### :material/chair:  Bench")
                            for idx, (_, row) in enumerate(comp_bench.iterrows()):
                                sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                                pts = int(row.get("Raw_GW_Pts", 0))
                                render_list_card(
                                    f"{row['Player']} · {row['Team']}",
                                    [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                    f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>',
                                    img_url=get_player_img_url(row.get("photo"), row.get("code")),
                                )
            else:
                if pitch_view:
                    col_pitch, col_side = st.columns([3, 1])
                    with col_pitch:
                        st.markdown(
                            f"""
                            <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px;">
                                <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">Your Squad · GW{selected_eval_gw}</span>
                                <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({user_eval_pts} pts)</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        render_pitch_component(
                            user_starters,
                            user_bench,
                            is_live=True,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    with col_side:
                        render_match_tracker_sidebar(
                            user_starters,
                            user_bench,
                            user_eval_pts=user_eval_pts,
                            is_dark=is_dark,
                        )
                else:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">Your Squad · GW{selected_eval_gw}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({user_eval_pts} pts)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    for idx, (_, row) in enumerate(user_starters.iterrows()):
                        tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                        mult = int(round(float(row.get("Multiplier", 1))))
                        mult_label = f" ({mult}x)" if mult > 1 else ""
                        if mult == 3:
                            tags.append(("Triple Captain (3x)", "yellow"))
                        elif row.get("is_cap") is True:
                            tags.append(("Captain (2x)", "green"))
                        elif row.get("is_vc") is True:
                            tags.append(("Vice Captain", "yellow"))
                        
                        pts = int(row.get("GW_Points", 0))
                        render_list_card(
                            f"{row['Player']} · {row['Team']}",
                            tags,
                            f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>{mult_label}',
                            img_url=get_player_img_url(row.get("photo"), row.get("code")),
                        )
                    if not user_bench.empty:
                        st.markdown("##### :material/chair:  Bench")
                        for idx, (_, row) in enumerate(user_bench.iterrows()):
                            sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                            pts = int(row.get("Raw_GW_Pts", 0))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Live Pts</span> <strong>{pts}</strong>',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )

        else:
            calc_loader = st.empty()
            with calc_loader.container():
                render_optimizer_status(
                    title="Optimizing your squad...",
                    subtext="Evaluating starting XI permutations & fixture baselines...",
                )
                render_skeleton_cards(count=1)

            adv_fixtures_query = """
            SELECT
                f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                th.short_name AS Home_Team, ta.short_name AS Away_Team,
                f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
            FROM fixtures f
            INNER JOIN teams th ON f.team_h = th.id
            INNER JOIN teams ta ON f.team_a = ta.id
            WHERE f.event >= ? AND f.event <= ?
            """
            adv_fix_df = pd.read_sql(adv_fixtures_query, conn, params=[current_gw, max(19, selected_eval_gw)])
            hist_baselines_df = get_historical_player_baselines(conn)

            odds_api_key = st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", ""))
            market_cache = fetch_upcoming_betting_odds(odds_api_key) if enable_betting else {}

            squad_eval_list = []
            disagreements = []
            movements = []

            for _, p_row in squad_df.iterrows():
                fix_data = get_fixture_for_team(adv_fix_df, p_row["team_id"], selected_eval_gw)
                base_proj_pts = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)
                final_proj_pts = base_proj_pts

                if enable_betting and fix_data.get("opponent"):
                    opp_short = fix_data["opponent"].replace(" (H)", "").replace(" (A)", "")
                    final_proj_pts, dis_item, mv_item = apply_market_projection_with_movement(
                        conn,
                        base_proj_pts,
                        p_row["Pos"],
                        fix_data["fdr"],
                        fix_data["is_home"],
                        p_row["Team"],
                        opp_short,
                        market_weight,
                        factor_movement,
                        market_cache,
                    )
                    if dis_item:
                        disagreements.append(dis_item)
                    if mv_item:
                        movements.append(mv_item)

                p_eval = dict(p_row)
                p_eval.update({
                    "Opponent": fix_data["opponent"],
                    "FDR": fix_data["fdr"],
                    "Proj_Pts": round(final_proj_pts, 2),
                })
                squad_eval_list.append(p_eval)

            squad_eval_df = pd.DataFrame(squad_eval_list)
            optimal_xi, optimal_bench, optimal_formation = solve_optimal_xi(squad_eval_df)

            chip_active_on_gw = (active_chip != "None" and selected_eval_gw == next_gw_id)

            # Strictly enforce 1 Captain and 1 Vice Captain

            optimal_xi["is_cap"] = False

            optimal_xi["is_vc"] = False

            optimal_xi["Multiplier"] = 1

            if not optimal_bench.empty:

                optimal_bench["is_cap"] = False

                optimal_bench["is_vc"] = False

                optimal_bench["Multiplier"] = 1

            if len(optimal_xi) > 0:

                top_id = optimal_xi.sort_values("Proj_Pts", ascending=False).iloc[0]["id"]

                optimal_xi.loc[optimal_xi["id"] == top_id, "is_cap"] = True

                optimal_xi.loc[optimal_xi["id"] == top_id, "Multiplier"] = 3 if (chip_active_on_gw and active_chip == "Triple Captain") else 2

            if len(optimal_xi) > 1:

                second_id = optimal_xi.sort_values("Proj_Pts", ascending=False).iloc[1]["id"]

                optimal_xi.loc[optimal_xi["id"] == second_id, "is_vc"] = True

            # Calculate base points

            user_proj_xi_pts = optimal_xi["Proj_Pts"].sum()

            

            # Add normal captain double points (Proj_Pts only has 1x base points)

            if len(optimal_xi) > 0:

                cap_pts = optimal_xi.sort_values("Proj_Pts", ascending=False).iloc[0]["Proj_Pts"]

                user_proj_xi_pts += cap_pts  # Add once for 2x

                

                # Add again if Triple Captain

                if chip_active_on_gw and active_chip == "Triple Captain":

                    user_proj_xi_pts += cap_pts

            if chip_active_on_gw and active_chip == "Bench Boost":

                user_proj_xi_pts += optimal_bench["Proj_Pts"].sum()

            avg_xi_fdr = float(optimal_xi["FDR"].mean())
            fdr_ease_pct = max(0.0, min(100.0, ((5.0 - avg_xi_fdr) / 3.0) * 100.0))
            pts_index_pct = max(0.0, min(100.0, (user_proj_xi_pts / 52.0) * 100.0))
            squad_rating = round((0.50 * fdr_ease_pct) + (0.50 * pts_index_pct), 1)

            # BELOW the row: Lock Lineup
            existing_snap = get_snapshot(conn, mgr_to_use, next_gw_id) if selected_eval_gw == next_gw_id else None
            snap_locked = existing_snap is not None
            
            if selected_eval_gw == next_gw_id and is_owner_manager(mgr_to_use):
                st.markdown("<div style='margin-top: 15px; margin-bottom: 5px;'></div>", unsafe_allow_html=True)
                col_lock_btn, col_lock_info = st.columns([1.5, 8.5], vertical_alignment="center")
                
                with col_lock_btn:
                    if snap_locked:
                        lock_btn = st.button("Re-Lock Lineup", key="tab4_relock_btn")
                    else:
                        lock_btn = st.button("Lock Lineup Snapshot", type="primary", key="tab4_lock_btn")
                
                with col_lock_info:
                    if snap_locked:
                        lock_time = existing_snap.get("created_at", "")[:16].replace("T", " ")
                        st.markdown(
                            f"<div style='font-size: 0.85rem; color: #22c55e; font-weight: 600;'>Locked at {lock_time}</div>",
                            unsafe_allow_html=True
                        )
                    
                if lock_btn:
                    starters_list = optimal_xi.to_dict('records')
                    for p in starters_list:
                        p['is_starter'] = True
                    bench_list = optimal_bench.to_dict('records')
                    for p in bench_list:
                        p['is_starter'] = False
                    lineup_data = starters_list + bench_list
                    
                    save_pre_gw_snapshot(
                        conn=conn, 
                        manager_id=mgr_to_use,
                        gw=next_gw_id, 
                        lineup_data=lineup_data, 
                        formation=optimal_formation,
                        market_weight=market_weight,
                        factor_movement=factor_movement,
                        chip=active_chip if chip_active_on_gw else None,
                        source="Squad Analyzer"
                    )
                    st.toast(f"Snapshot locked for GW{next_gw_id}!", icon=":material/lock:")
                    st.rerun()

            if enable_comparison:
                if super_team_mode:
                    comp_xi, comp_bench, comp_formation = get_cached_league_super_15(
                        conn, current_gw, selected_eval_gw, enable_betting, market_weight, factor_movement
                    )
                    comp_target_label = "Super Team"
                    comp_badge_icon = ""
                else:
                    comp_xi, comp_bench, comp_formation = get_cached_league_dream_15(
                        conn, current_gw, selected_eval_gw, total_team_value, enable_betting, market_weight, factor_movement
                    )
                    comp_target_label = "Budget Dream 11"
                    comp_badge_icon = ""

                comp_xi["is_cap"] = False
                comp_xi["is_vc"] = False
                comp_xi["Multiplier"] = 1
                if len(comp_xi) > 0:
                    top_comp_id = comp_xi.sort_values("Proj_Pts", ascending=False).iloc[0]["id"]
                    comp_xi.loc[comp_xi["id"] == top_comp_id, "is_cap"] = True
                    comp_xi.loc[comp_xi["id"] == top_comp_id, "Multiplier"] = 2
                if len(comp_xi) > 1:
                    sec_comp_id = comp_xi.sort_values("Proj_Pts", ascending=False).iloc[1]["id"]
                    comp_xi.loc[comp_xi["id"] == sec_comp_id, "is_vc"] = True

                comp_proj_xi_pts = comp_xi["Proj_Pts"].sum()

            calc_loader.empty()

            chip_note = f" &bull; <span style=\'color:#eab308;\'>Active Simulation: {active_chip}</span>" if chip_active_on_gw else ""

            is_dark = st.session_state.get("theme_mode", "dark") == "dark"
            banner_bg = "#151d24" if is_dark else "#ffffff"
            banner_border = "rgba(255, 255, 255, 0.08)" if is_dark else "#e2e8f0"
            banner_title_col = "#f8fafc" if is_dark else "#0f172a"

            st.markdown(
                f"""
                <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-radius: 8px; padding: 0.85rem 1.1rem; margin: 0.4rem 0 0.85rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 1rem; font-weight: 700; color: {banner_title_col};">GW{selected_eval_gw} Squad Rating{chip_note}</span>
                        <span style="font-size: 1.25rem; font-weight: 800; color: #22c55e;">{squad_rating}%</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_met1, col_met2, col_met3, col_met4 = st.columns(4)
            col_met1.metric("Optimal Formation", optimal_formation)
            pts_delta_str = f"{user_proj_xi_pts - comp_proj_xi_pts:+.1f} vs {comp_target_label}" if enable_comparison else None
            pts_label = (
                "Projected XI + Bench (BB)"
                if (chip_active_on_gw and active_chip == "Bench Boost")
                else (
                    "Projected XI (3x TC)"
                    if (chip_active_on_gw and active_chip == "Triple Captain")
                    else "Projected XI Points"
                )
            )
            col_met2.metric(pts_label, f"{user_proj_xi_pts:.1f} pts", delta=pts_delta_str)
            col_met3.metric("Avg Starting FDR", f"{avg_xi_fdr:.2f}")
            col_met4.metric(
                "Squad Health",
                f"{len(squad_df[squad_df['Status'] == 'a'])}/15 Fit",
                delta="Available" if len(squad_df[squad_df['Status'] != 'a']) == 0 else "Flagged",
            )

            if enable_comparison:
                col_left, col_right = st.columns(2)
                with col_left:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">Your Optimal XI · GW{selected_eval_gw}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({optimal_formation} · {user_proj_xi_pts:.1f} xP)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if pitch_view:
                        render_pitch_component(
                            optimal_xi,
                            optimal_bench,
                            is_live=False,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    else:
                        for idx, (_, row) in enumerate(optimal_xi.iterrows()):
                            tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                            mult = int(round(float(row.get("Multiplier", 1))))
                            mult_label = f" ({mult}x)" if mult > 1 else ""
                            if mult == 3:
                                tags.append(("Triple Captain (3x)", "yellow"))
                            elif row.get("is_cap") is True:
                                tags.append(("Captain (2x)", "green"))
                            elif row.get("is_vc") is True:
                                tags.append(("Vice Captain", "yellow"))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                tags,
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> <strong>{fmt_num(row["Proj_Pts"], ".1f")}</strong>{mult_label} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )
                        if not optimal_bench.empty:
                            st.markdown("##### :material/chair:  Projected Bench")
                            for idx, (_, row) in enumerate(optimal_bench.iterrows()):
                                sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                                render_list_card(
                                    f"{row['Player']} · {row['Team']}",
                                    [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                    f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> {fmt_num(row["Proj_Pts"], ".1f")} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                                    img_url=get_player_img_url(row.get("photo"), row.get("code")),
                                )

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(":material/save: Save Optimal Squad for Simulator", key="btn_save_opt_sim", use_container_width=True):
                        st.session_state["active_squad_sim_df"] = pd.concat([optimal_xi, optimal_bench], ignore_index=True)
                        st.toast("Saved Optimal Squad to Simulator!", icon=":material/check_circle:")

                with col_right:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">{comp_target_label} · GW{selected_eval_gw}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({comp_formation} · {comp_proj_xi_pts:.1f} xP)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if pitch_view:
                        render_pitch_component(
                            comp_xi,
                            comp_bench,
                            is_live=False,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    else:
                        for idx, (_, row) in enumerate(comp_xi.iterrows()):
                            tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                            mult = int(round(float(row.get("Multiplier", 1))))
                            mult_label = f" ({mult}x)" if mult > 1 else ""
                            if row.get("is_cap") is True:
                                tags.append(("Captain (2x)", "green"))
                            elif row.get("is_vc") is True:
                                tags.append(("Vice Captain", "yellow"))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                tags,
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> <strong>{fmt_num(row["Proj_Pts"], ".1f")}</strong>{mult_label} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )
                        if not comp_bench.empty:
                            st.markdown("##### :material/chair:  Dream Bench")
                            for idx, (_, row) in enumerate(comp_bench.iterrows()):
                                sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                                render_list_card(
                                    f"{row['Player']} · {row['Team']}",
                                    [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                    f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> {fmt_num(row["Proj_Pts"], ".1f")} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                                    img_url=get_player_img_url(row.get("photo"), row.get("code")),
                                )

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(":material/save: Save Budget 15 for Simulator", key="btn_save_budget_sim", use_container_width=True):
                        st.session_state["budget_dream_15_df"] = pd.concat([comp_xi, comp_bench], ignore_index=True)
                        st.toast("Saved Budget 15 to Simulator!", icon=":material/check_circle:")

                if enable_betting:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if disagreements:
                        st.markdown("#### :material/balance:  Model vs Market Disagreements")
                        unique_d = {v["Club"]: v for v in disagreements}.values()
                        st.dataframe(pd.DataFrame(unique_d), hide_index=True, use_container_width=True)

                    if movements:
                        st.markdown("#### :material/bolt:  Market Line Movement (Opening vs Current)")
                        unique_m = {v["Club"]: v for v in movements}.values()
                        st.dataframe(pd.DataFrame(unique_m), hide_index=True, use_container_width=True)

                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("#### :material/newspaper:  Squad News & Availability")
                flagged = squad_df[squad_df["Status"] != "a"]
                if flagged.empty:
                    st.success("All squad players available.")
                else:
                    for _, row in flagged.iterrows():
                        st.warning(f"**{row['Player']}**: {row.get('News', 'Doubtful')}")

            else:
                col_pitch, col_side = st.columns([3, 1])
                with col_pitch:
                    st.markdown(
                        f"""
                        <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                            <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">Optimal Starting XI · GW{selected_eval_gw}</span>
                            <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({optimal_formation} · {user_proj_xi_pts:.1f} xP)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if pitch_view:
                        render_pitch_component(
                            optimal_xi,
                            optimal_bench,
                            is_live=False,
                            rolling_df=rolling_metrics_df,
                            fdr_map=teams_fdr_map,
                        )
                    else:
                        for idx, (_, row) in enumerate(optimal_xi.iterrows()):
                            tags = [(row["Pos"], "blue"), (f"FDR {row['FDR']}", "gray")]
                            mult = int(round(float(row.get("Multiplier", 1))))
                            mult_label = f" ({mult}x)" if mult > 1 else ""
                            if mult == 3:
                                tags.append(("Triple Captain (3x)", "yellow"))
                            elif row.get("is_cap") is True:
                                tags.append(("Captain (2x)", "green"))
                            elif row.get("is_vc") is True:
                                tags.append(("Vice Captain", "yellow"))
                            render_list_card(
                                f"{row['Player']} · {row['Team']}",
                                tags,
                                f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> <strong>{fmt_num(row["Proj_Pts"], ".1f")}</strong>{mult_label}',
                                img_url=get_player_img_url(row.get("photo"), row.get("code")),
                            )
                        if not optimal_bench.empty:
                            st.markdown("##### :material/chair:  Projected Bench")
                            for idx, (_, row) in enumerate(optimal_bench.iterrows()):
                                sub_label = "Sub GKP" if row["Pos"] == "GKP" else f"Sub {idx}"
                                render_list_card(
                                    f"{row['Player']} · {row['Team']}",
                                    [(sub_label, "gray"), (f"FDR {row['FDR']}", "gray")],
                                    f'<span>Fixture</span> {row["Opponent"]} · <span>Proj Pts</span> {fmt_num(row["Proj_Pts"], ".1f")} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                                    img_url=get_player_img_url(row.get("photo"), row.get("code")),
                                )

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(":material/save: Save Optimal Squad for Simulator", key="btn_save_opt_sim", use_container_width=True):
                        st.session_state["active_squad_sim_df"] = pd.concat([optimal_xi, optimal_bench], ignore_index=True)
                        st.toast("Saved Optimal Squad to Simulator!", icon=":material/check_circle:")

                with col_side:
                    if enable_betting:
                        if disagreements:
                            st.markdown("#### :material/balance:  Model vs Market")
                            unique_d = {v["Club"]: v for v in disagreements}.values()
                            st.dataframe(pd.DataFrame(unique_d), hide_index=True, use_container_width=True)

                        if movements:
                            st.markdown("#### :material/bolt:  Line Movement (Open vs Now)")
                            unique_m = {v["Club"]: v for v in movements}.values()
                            st.dataframe(pd.DataFrame(unique_m), hide_index=True, use_container_width=True)

                    st.markdown("#### :material/newspaper:  Squad News")
                    flagged = squad_df[squad_df["Status"] != "a"]
                    if flagged.empty:
                        st.success("All squad players available.")
                    else:
                        for _, row in flagged.iterrows():
                            st.warning(f"**{row['Player']}**: {row.get('News', 'Doubtful')}")

    except Exception as e:
        st.error(f"Could not load team. Verify your FPL ID. (Error: {e})")