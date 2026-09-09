import html
import itertools
import math
import os
from collections import Counter

import pandas as pd
import pulp
import requests
import streamlit as st

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

from betting_engine import (
    load_db_market_odds,
    get_fixture_market_xg_and_movement,
)
from data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)
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
    "IjQ0IiByeD0iMjIiIGZpbGw9IjExZTI5M2IiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjE2IiByPSI3"
    "LjUiIGZpbGw9IjY0NzQ4YiIvPjxwYXRoIGQ9Ik05IDM5YzAtNy4xOCA1LjgyLTEzIDEzLTEzczEz"
    "IDUuODIgMTMgMTMiIGZpbGw9IjY0NzQ4YiIvPjwvc3ZnPg=="
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


def build_player_tooltip(p: pd.Series, horizon_len: int = 1) -> str:
    player_name = html.escape(str(p.get("Player", "")))
    pos = html.escape(str(p.get("Pos", "")))
    team = html.escape(str(p.get("Team", "")))
    cost = p.get("Cost", 0.0)
    cost_str = f"£{fmt_num(cost, '.1f')}m" if cost else "—"

    roll_pts = fmt_num(p.get("roll_pts", 0.0), ".1f")
    roll_xgi90 = fmt_num(p.get("roll_xgi90", 0.0), ".2f")
    roll_mins = int(p.get("roll_mins", 0))
    fdr5 = int(p.get("fdr5", 15))
    fdr5_cls = "tt-fdr-easy" if fdr5 <= 11 else ("tt-fdr-med" if fdr5 <= 14 else "tt-fdr-hard")

    form = fmt_num(p.get("Form", 0.0), ".1f")
    ppg = fmt_num(p.get("PPG", 0.0), ".1f")
    tot_xp = fmt_num(p.get("Horizon_xP", p.get("Proj_Pts", 0.0)), ".1f")
    avg_xp = fmt_num(p.get("Avg_xP", float(tot_xp) / max(1, horizon_len)), ".1f")

    status = str(p.get("Status", "a"))
    news = str(p.get("News", ""))
    news_row = ""
    if status != "a" and news and news != "None":
        clean_news = html.escape(news[:40] + ("..." if len(news) > 40 else ""))
        news_row = f'<div class="tt-row tt-news"><span>[!] {clean_news}</span></div>'

    transfer_badge_row = ""
    if bool(p.get("is_transfer_in") is True):
        if bool(p.get("is_target_in") is True):
            transfer_badge_row = '<div class="tt-row" style="color:#38bdf8; font-weight:700;"><span>Target Signing</span></div>'
        else:
            transfer_badge_row = '<div class="tt-row" style="color:#34d399; font-weight:700;"><span>Proposed Sign</span></div>'
    elif bool(p.get("is_transfer_out") is True):
        if bool(p.get("is_forced_out") is True):
            transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>Forced Sale</span></div>'
        else:
            transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>Proposed Sale</span></div>'

    return (
        f'<div class="player-tooltip-card">'
        f'<div class="tt-header">'
        f'<span class="tt-name">{player_name}</span>'
        f'<span class="tt-badge">{team} · {pos} · {cost_str}</span>'
        f'</div>'
        f'<div class="tt-body">'
        f'<div class="tt-row"><span class="tt-label">{horizon_len}-GW xP:</span><span class="tt-val" style="color:#60a5fa;">{tot_xp} xP</span></div>'
        f'<div class="tt-row"><span class="tt-label">Avg xP / GW:</span><span class="tt-val" style="color:#38bdf8;">{avg_xp} xP</span></div>'
        f'<div class="tt-row"><span class="tt-label">Avg Pts (L5):</span><span class="tt-val">{roll_pts}</span></div>'
        f'<div class="tt-row"><span class="tt-label">xGI / 90 (L5):</span><span class="tt-val">{roll_xgi90}</span></div>'
        f'<div class="tt-row"><span class="tt-label">Avg Mins (L5):</span><span class="tt-val">{roll_mins}m</span></div>'
        f'<div class="tt-row"><span class="tt-label">Next 5 FDR:</span><span class="tt-val {fdr5_cls}">{fdr5}</span></div>'
        f'<div class="tt-row"><span class="tt-label">Form / PPG:</span><span class="tt-val">{form} / {ppg}</span></div>'
        f'{transfer_badge_row}'
        f'{news_row}'
        f'</div></div>'
    )


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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_transfer_manager_entry(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_transfer_manager_history(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def fetch_transfer_manager_transfers(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/transfers/"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_transfer_manager_picks(manager_id: str, next_gw: int):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{next_gw}/picks/"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
        for g in range(next_gw - 1, 0, -1):
            res2 = requests.get(f"https://fantasy.premierleague.com/api/entry/{manager_id}/event/{g}/picks/", timeout=10)
            if res2.status_code == 200:
                return res2.json()
        return {}
    except Exception:
        return {}


def calculate_available_fts(mgr_history: dict) -> int:
    current_season = mgr_history.get("current", []) if mgr_history else []
    if not current_season:
        return 1

    sorted_events = sorted(current_season, key=lambda x: x.get("event", 0))
    chips_played = {c.get("event"): c.get("name") for c in mgr_history.get("chips", [])}

    ft = 1
    for ev in sorted_events[1:]:
        gw = ev.get("event")
        chip = chips_played.get(gw)
        if chip in ("wildcard", "freehit"):
            continue

        transfers_made = ev.get("event_transfers", 0)
        ft = max(0, ft - transfers_made)
        ft = min(5, ft + 1)

    return max(1, min(5, ft))


@st.cache_data(ttl=600, show_spinner=False)
def evaluate_league_multi_gw(
    _conn,
    start_gw: int,
    horizon_len: int,
    enable_betting: bool = True,
    market_weight: float = 0.35,
    factor_movement: bool = True,
) -> pd.DataFrame:
    end_gw = min(38, start_gw + horizon_len - 1)
    fix_query = """
    SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
           th.short_name AS Home_Team, ta.short_name AS Away_Team,
           f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
    FROM fixtures f
    INNER JOIN teams th ON f.team_h = th.id
    INNER JOIN teams ta ON f.team_a = ta.id
    WHERE f.event >= ? AND f.event <= ?
    """
    fix_df = pd.read_sql(fix_query, _conn, params=[start_gw, end_gw])
    all_players_query = """
    SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
           t.short_name AS Team,
           CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
           p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
           p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
           p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
           p.can_select AS can_select,
           p.expected_goal_involvements_per_90 AS xGI_per_90
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    """
    players_df = pd.read_sql(all_players_query, _conn)
    hist_baselines = get_historical_player_baselines(_conn)
    rolling_metrics = get_rolling_player_metrics(_conn)
    market_cache = load_db_market_odds(_conn) if enable_betting else {}

    fixture_map: dict[tuple, list] = {}
    for _, row in fix_df.iterrows():
        gw = row["GW"]
        h_id, a_id = row["team_h_id"], row["team_a_id"]
        fixture_map.setdefault((h_id, gw), []).append({
            "opponent": f"{row['Away_Team']} (H)",
            "fdr": int(row["Home_Diff"]),
            "is_home": True,
        })
        fixture_map.setdefault((a_id, gw), []).append({
            "opponent": f"{row['Home_Team']} (A)",
            "fdr": int(row["Away_Diff"]),
            "is_home": False,
        })

    results = []
    past_gws = max(1, start_gw - 1)

    roll_mins_dict = {}
    if rolling_metrics is not None and not rolling_metrics.empty:
        roll_mins_dict = rolling_metrics["roll_mins"].to_dict()

    for _, p in players_df.iterrows():
        pid = p["id"]
        roll_m = float(roll_mins_dict.get(pid, 0) or 0)
        p_mins = float(p.get("minutes", 0) or 0)
        avg_mins = roll_m if roll_m > 0 else (p_mins / past_gws)

        is_unavailable = (
            p.get("can_select") == 0
            or str(p.get("Status", "")).lower() == "u"
            or p.get("Chance") == 0
        )
        if is_unavailable:
            p_dict = dict(p)
            p_dict["avg_mins"] = 0.0
            p_dict["Horizon_xP"] = 0.0
            p_dict["Proj_Pts"] = 0.0
            p_dict["Target_Horizon_xP"] = 0.0
            p_dict["Avg_xP"] = 0.0
            for gw in range(start_gw, end_gw + 1):
                p_dict[f"GW{gw}"] = 0.0
                p_dict[f"Target_GW{gw}"] = 0.0
            results.append(p_dict)
            continue

        if start_gw > 1:
            if avg_mins >= 65:
                mins_weight = 1.0
            elif avg_mins >= 45:
                mins_weight = 0.80
            elif avg_mins >= 20:
                mins_weight = 0.45
            else:
                mins_weight = max(0.12, (avg_mins + 5.0) / 90.0)
        else:
            mins_weight = 1.0 if p["Cost"] >= 7.0 else 0.85

        if mins_weight <= 0.12 and p["Status"] != "a":
            p_dict = dict(p)
            p_dict["avg_mins"] = round(avg_mins, 0)
            p_dict["Horizon_xP"] = 0.0
            p_dict["Proj_Pts"] = 0.0
            p_dict["Avg_xP"] = 0.0
            for gw in range(start_gw, end_gw + 1):
                p_dict[f"GW{gw}"] = 0.0
            results.append(p_dict)
            continue

        total_horizon_xp = 0.0
        total_target_horizon_xp = 0.0
        gw_breakdown = {}
        target_gw_breakdown = {}
        team_id = p["team_id"]

        p_target = dict(p)
        p_target["is_target"] = True

        for step, gw in enumerate(range(start_gw, end_gw + 1)):
            team_fixtures = fixture_map.get((team_id, gw), [])

            if not team_fixtures:
                gw_breakdown[f"GW{gw}"] = 0.0
                target_gw_breakdown[f"Target_GW{gw}"] = 0.0
            else:
                gw_scaled_xp = 0.0
                target_gw_scaled_xp = 0.0
                for f_data in team_fixtures:
                    base_xp = calculate_projected_points(p, f_data, start_gw, hist_baselines)
                    target_base_xp = calculate_projected_points(p_target, f_data, start_gw, hist_baselines)

                    if enable_betting:
                        opp_short = f_data["opponent"].replace(" (H)", "").replace(" (A)", "")
                        final_xp, _, _ = apply_market_projection_with_movement(
                            _conn, base_xp, p["Pos"], f_data["fdr"], f_data["is_home"],
                            p["Team"], opp_short, market_weight, factor_movement, market_cache,
                        )
                        target_final_xp, _, _ = apply_market_projection_with_movement(
                            _conn, target_base_xp, p["Pos"], f_data["fdr"], f_data["is_home"],
                            p["Team"], opp_short, market_weight, factor_movement, market_cache,
                        )
                    else:
                        final_xp = base_xp
                        target_final_xp = target_base_xp

                    gw_scaled_xp += final_xp
                    target_gw_scaled_xp += target_final_xp

                decay_factor = 0.92 ** step
                total_horizon_xp += (gw_scaled_xp * decay_factor)
                total_target_horizon_xp += (target_gw_scaled_xp * decay_factor)
                gw_breakdown[f"GW{gw}"] = round(gw_scaled_xp, 1)
                target_gw_breakdown[f"Target_GW{gw}"] = round(target_gw_scaled_xp, 1)

        p_dict = dict(p)
        p_dict["avg_mins"] = round(avg_mins, 0)
        p_dict["Horizon_xP"] = round(total_horizon_xp, 2)
        p_dict["Proj_Pts"] = round(total_horizon_xp, 2)
        p_dict["Target_Horizon_xP"] = round(total_target_horizon_xp, 2)
        p_dict["Avg_xP"] = round(total_horizon_xp / max(1, horizon_len), 2)
        p_dict.update(gw_breakdown)
        p_dict.update(target_gw_breakdown)
        results.append(p_dict)

    return pd.DataFrame(results)


def _fast_xi_xp(all_players: list[dict]) -> float:
    """Greedy O(n log n) starting-XI xP estimator with endogenous captaincy doubling."""
    gkps = sorted([p for p in all_players if p.get("Pos") == "GKP"], key=lambda x: -x.get("Horizon_xP", 0))
    defs = sorted([p for p in all_players if p.get("Pos") == "DEF"], key=lambda x: -x.get("Horizon_xP", 0))
    mids = sorted([p for p in all_players if p.get("Pos") == "MID"], key=lambda x: -x.get("Horizon_xP", 0))
    fwds = sorted([p for p in all_players if p.get("Pos") == "FWD"], key=lambda x: -x.get("Horizon_xP", 0))
    mandatory = gkps[:1] + defs[:3] + mids[:2] + fwds[:1]
    rem_pool = sorted(defs[3:] + mids[2:] + fwds[1:], key=lambda x: -x.get("Horizon_xP", 0))
    starters = mandatory + rem_pool[:4]
    
    starting_xp = sum(p.get("Horizon_xP", 0) for p in starters)
    top_starter_xp = max((p.get("Horizon_xP", 0) for p in starters), default=0.0)
    return starting_xp + top_starter_xp


def _fast_xi_player_set(all_players: list[dict]) -> set:
    """Returns the set of player IDs in the optimal starting XI."""
    gkps = sorted([p for p in all_players if p.get("Pos") == "GKP"], key=lambda x: -x.get("Horizon_xP", 0))
    defs = sorted([p for p in all_players if p.get("Pos") == "DEF"], key=lambda x: -x.get("Horizon_xP", 0))
    mids = sorted([p for p in all_players if p.get("Pos") == "MID"], key=lambda x: -x.get("Horizon_xP", 0))
    fwds = sorted([p for p in all_players if p.get("Pos") == "FWD"], key=lambda x: -x.get("Horizon_xP", 0))
    mandatory = gkps[:1] + defs[:3] + mids[:2] + fwds[:1]
    rem_pool = sorted(defs[3:] + mids[2:] + fwds[1:], key=lambda x: -x.get("Horizon_xP", 0))
    starters = mandatory + rem_pool[:4]
    return {p["id"] for p in starters}


def _maximize_leftover_budget(
    in_players_flat: list[dict],
    remaining_squad: pd.DataFrame,
    budget_available: float,
    avail_cands: pd.DataFrame,
    target_in_set: set,
    combo_budget: int = 80000,
) -> tuple[list[dict], float]:
    pos_cand_map: dict[str, pd.DataFrame] = {}
    for pos in avail_cands["Pos"].unique():
        pos_cand_map[pos] = avail_cands[avail_cands["Pos"] == pos].sort_values(
            "Horizon_xP", ascending=False
        )

    initial_in_players = [dict(p) for p in in_players_flat]
    working_in = list(initial_in_players)

    free_slots = [i for i, p in enumerate(working_in) if p["id"] not in target_in_set]
    if not free_slots or avail_cands.empty:
        leftover = round(budget_available - sum(p["Cost"] for p in working_in), 2)
        return working_in, leftover

    locked_idx = [i for i in range(len(working_in)) if i not in free_slots]

    base_team_counts = remaining_squad["team_id"].value_counts().to_dict()
    for i in locked_idx:
        tid = working_in[i]["team_id"]
        base_team_counts[tid] = base_team_counts.get(tid, 0) + 1

    excluded_ids = set(remaining_squad["id"].tolist())
    for i in locked_idx:
        excluded_ids.add(working_in[i]["id"])

    committed_team_counts = dict(base_team_counts)
    committed_ids = set(excluded_ids)

    for slot_i in free_slots:
        cur_p = working_in[slot_i]
        pos = cur_p["Pos"]

        current_total = sum(p["Cost"] for p in working_in)
        headroom = budget_available - current_total
        max_candidate_cost = cur_p["Cost"] + headroom
        cur_xp = cur_p["Horizon_xP"]
        best_cand = None
        best_xp = cur_xp

        cands = pos_cand_map.get(pos, pd.DataFrame())
        for _, cand in cands.iterrows():
            c_xp = cand["Horizon_xP"]
            if c_xp <= best_xp:
                break
            if cand["id"] in committed_ids:
                continue
            if cand["Cost"] > max_candidate_cost + 1e-5:
                continue
            tid = cand["team_id"]
            if tid != cur_p["team_id"] and committed_team_counts.get(tid, 0) >= 3:
                continue
            best_cand = cand
            best_xp = c_xp
            break

        if best_cand is not None:
            working_in[slot_i] = best_cand.to_dict()
            committed_ids.add(best_cand["id"])
            tid = best_cand["team_id"]
            committed_team_counts[tid] = committed_team_counts.get(tid, 0) + 1
        else:
            committed_ids.add(cur_p["id"])
            tid = cur_p["team_id"]
            committed_team_counts[tid] = committed_team_counts.get(tid, 0) + 1

    total_in_cost = sum(p["Cost"] for p in working_in)
    if total_in_cost > budget_available + 1e-5:
        working_in = initial_in_players

    leftover = round(budget_available - sum(p["Cost"] for p in working_in), 2)
    return working_in, leftover


def solve_chip_transfers_pulp(
    current_squad_df,
    candidate_league_df,
    team_value: float,
    locked_player_ids: list = None,
    target_in_player_ids: list = None,
    force_out_player_ids: list = None,
    blocked_in_player_ids: list = None,
    is_free_hit: bool = False,
):
    locked_set = set(locked_player_ids or [])
    blocked_in_set = set(blocked_in_player_ids or [])
    target_in_set = set(target_in_player_ids or []) - blocked_in_set

    prob = pulp.LpProblem("FPL_Chip_Solver", pulp.LpMaximize)

    raw_avail = candidate_league_df[
        (~candidate_league_df["id"].isin(blocked_in_set)) &
        (candidate_league_df["Status"].isin(["a", "d"])) &
        (candidate_league_df["Chance"] != 0) &
        (candidate_league_df["Chance"] != "0")
    ].copy()

    top_cand_list = []
    limits = {"GKP": 8, "DEF": 22, "MID": 25, "FWD": 16}
    for pos, limit in limits.items():
        pos_df = raw_avail[raw_avail["Pos"] == pos]
        if pos_df.empty:
            continue
        top_xp = pos_df.sort_values(by="Horizon_xP", ascending=False).head(limit)
        cheapest = pos_df.sort_values(by="Cost", ascending=True).head(4)
        top_cand_list.extend([top_xp, cheapest])

    current_in_raw = candidate_league_df[candidate_league_df["id"].isin(current_squad_df["id"].tolist())]
    top_cand_list.append(current_in_raw)

    if target_in_set:
        top_cand_list.append(candidate_league_df[candidate_league_df["id"].isin(target_in_set)])
    if locked_set:
        top_cand_list.append(candidate_league_df[candidate_league_df["id"].isin(locked_set)])

    avail = pd.concat(top_cand_list, ignore_index=True).drop_duplicates(subset=["id"])

    player_vars = {}
    starter_vars = {}
    cap_vars = {}

    cost_dict = avail.set_index("id")["Cost"].to_dict()
    xp_dict = avail.set_index("id")["Horizon_xP"].to_dict()

    for pid in avail["id"]:
        x = pulp.LpVariable(f"squad_{pid}", cat="Binary")
        y = pulp.LpVariable(f"start_{pid}", cat="Binary")
        c = pulp.LpVariable(f"cap_{pid}", cat="Binary")
        player_vars[pid] = x
        starter_vars[pid] = y
        cap_vars[pid] = c

        prob += y <= x
        prob += c <= y
        if pid in locked_set or pid in target_in_set:
            prob += x == 1
        if pid in (force_out_player_ids or []) and pid not in locked_set:
            prob += x == 0

    prob += pulp.lpSum(starter_vars[pid] for pid in avail[avail["Pos"] == "GKP"]["id"]) == 1
    prob += pulp.lpSum(starter_vars[pid] for pid in avail[avail["Pos"] == "DEF"]["id"]) >= 3
    prob += pulp.lpSum(starter_vars[pid] for pid in avail[avail["Pos"] == "FWD"]["id"]) >= 1
    prob += pulp.lpSum(starter_vars.values()) == 11

    prob += pulp.lpSum(cap_vars.values()) == 1

    prob += pulp.lpSum(
        starter_vars[pid] * xp_dict[pid] +
        cap_vars[pid] * xp_dict[pid] +
        0.10 * (player_vars[pid] - starter_vars[pid]) * xp_dict[pid]
        for pid in player_vars
    )

    prob += pulp.lpSum(player_vars[pid] for pid in avail[avail["Pos"] == "GKP"]["id"]) == 2
    prob += pulp.lpSum(player_vars[pid] for pid in avail[avail["Pos"] == "DEF"]["id"]) == 5
    prob += pulp.lpSum(player_vars[pid] for pid in avail[avail["Pos"] == "MID"]["id"]) == 5
    prob += pulp.lpSum(player_vars[pid] for pid in avail[avail["Pos"] == "FWD"]["id"]) == 3
    prob += pulp.lpSum(player_vars.values()) == 15

    for team_id in avail["team_id"].unique():
        team_pids = avail[avail["team_id"] == team_id]["id"].tolist()
        prob += pulp.lpSum(player_vars[pid] for pid in team_pids) <= 3

    prob += pulp.lpSum(player_vars[pid] * cost_dict[pid] for pid in player_vars) <= team_value

    prob.solve(pulp.PULP_CBC_CMD(timeLimit=6, gapRel=0.01, msg=False))

    if pulp.LpStatus[prob.status] != "Optimal":
        return current_squad_df.copy(), []

    selected_pids = [pid for pid in player_vars if pulp.value(player_vars[pid]) > 0.5]
    final_squad = avail[avail["id"].isin(selected_pids)].copy()

    final_squad["is_transfer_in"] = ~final_squad["id"].isin(current_squad_df["id"].tolist())
    final_squad["is_target_in"] = final_squad["id"].isin(target_in_set)
    final_squad["is_cap"] = final_squad["id"].apply(lambda pid: pulp.value(cap_vars.get(pid)) > 0.5 if pid in cap_vars else False)
    final_squad["is_vc"] = False

    return final_squad, []


def solve_multi_gw_transfers(
    current_squad_df: pd.DataFrame,
    candidate_league_df: pd.DataFrame,
    bank: float,
    num_transfers: int,
    locked_player_ids: list = None,
    target_in_player_ids: list = None,
    force_out_player_ids: list = None,
    blocked_in_player_ids: list = None,
    min_avg_minutes: float = 30.0,
) -> tuple[pd.DataFrame, list[dict]]:
    if num_transfers <= 0 or current_squad_df.empty:
        curr = current_squad_df.copy()
        curr["is_target_in"] = False
        return curr, []

    curr_squad = current_squad_df.copy()
    curr_ids = set(curr_squad["id"].tolist())
    locked_set = set(locked_player_ids or [])
    blocked_in_set = set(blocked_in_player_ids or [])
    target_in_set = set(target_in_player_ids or []) - blocked_in_set
    force_out_set = (set(force_out_player_ids or []) & curr_ids) - locked_set

    avail_cands = candidate_league_df[
        (~candidate_league_df["id"].isin(curr_ids)) &
        (~candidate_league_df["id"].isin(blocked_in_set)) &
        ((candidate_league_df["avg_mins"] >= min_avg_minutes) | (candidate_league_df["id"].isin(target_in_set)))
    ].copy()

    if target_in_set and "Target_Horizon_xP" in avail_cands.columns:
        t_mask = avail_cands["id"].isin(target_in_set)
        avail_cands.loc[t_mask, "Horizon_xP"] = avail_cands.loc[t_mask, "Target_Horizon_xP"]
        avail_cands.loc[t_mask, "Proj_Pts"] = avail_cands.loc[t_mask, "Target_Horizon_xP"]
        for col in avail_cands.columns:
            if col.startswith("Target_GW"):
                gw_col = col.replace("Target_", "")
                if gw_col in avail_cands.columns:
                    avail_cands.loc[t_mask, gw_col] = avail_cands.loc[t_mask, col]

    top_cand_list = []
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = avail_cands[avail_cands["Pos"] == pos]
        if pos_df.empty:
            continue
        prem_cutoff = 8.5 if pos in ["MID", "FWD"] else 5.5
        mid_min = 6.5 if pos in ["MID", "FWD"] else 4.5
        prem_df = pos_df[pos_df["Cost"] >= prem_cutoff].sort_values(by="Horizon_xP", ascending=False).head(18)
        mid_df = pos_df[(pos_df["Cost"] >= mid_min) & (pos_df["Cost"] < prem_cutoff)].sort_values(by="Horizon_xP", ascending=False).head(18)
        bud_df = pos_df[pos_df["Cost"] < mid_min].sort_values(by="Horizon_xP", ascending=False).head(12)

        top_raw = pos_df.sort_values(by="Horizon_xP", ascending=False).head(8)
        pos_combined = pd.concat([prem_df, mid_df, bud_df, top_raw]).drop_duplicates(subset=["id"])
        top_cand_list.append(pos_combined)

    if target_in_set:
        targets_df = avail_cands[avail_cands["id"].isin(target_in_set)]
        top_cand_list.append(targets_df)

    top_candidates = pd.concat(top_cand_list, ignore_index=True).drop_duplicates(subset=["id"])

    base_xi, _, _ = solve_optimal_xi(curr_squad)
    base_top_cap = base_xi["Proj_Pts"].max() if not base_xi.empty else 0.0
    base_xp = (base_xi["Proj_Pts"].sum() if not base_xi.empty else 0.0) + base_top_cap

    eligible_out_ids = [pid for pid in curr_squad["id"].tolist() if pid not in locked_set]
    forced_out_list = [pid for pid in force_out_set if pid in eligible_out_ids]

    min_k = max(1, min(len(forced_out_list), num_transfers))

    best_overall_plan = None
    best_eval_score = -999.0
    best_starting_gain = 0.0

    for k in range(min_k, num_transfers + 1):
        non_forced_outs = [pid for pid in eligible_out_ids if pid not in forced_out_list]
        needed_others = k - len(forced_out_list)
        if needed_others < 0:
            continue

        out_combos = []
        if needed_others == 0:
            out_combos = [tuple(forced_out_list)]
        else:
            for other_combo in itertools.combinations(non_forced_outs, needed_others):
                out_combos.append(tuple(forced_out_list) + other_combo)

        for out_ids_tuple in out_combos:
            out_players = curr_squad[curr_squad["id"].isin(out_ids_tuple)]
            out_pos_counts = Counter(out_players["Pos"].tolist())
            out_cost_total = out_players["Cost"].sum()
            budget_available = out_cost_total + bank

            remaining_squad = curr_squad[~curr_squad["id"].isin(out_ids_tuple)]
            base_team_counts = remaining_squad["team_id"].value_counts().to_dict()

            pos_cand_lists = []
            for pos, count in out_pos_counts.items():
                pos_cands = top_candidates[top_candidates["Pos"] == pos]
                target_pos_cands = pos_cands[pos_cands["id"].isin(target_in_set)]
                other_pos_cands = pos_cands[~pos_cands["id"].isin(target_in_set)].sort_values(by="Horizon_xP", ascending=False).head(12)
                combined_pos = pd.concat([target_pos_cands, other_pos_cands]).drop_duplicates(subset=["id"])
                pos_cand_lists.append(list(itertools.combinations(combined_pos.to_dict("records"), count)))

            candidate_in_combos = []
            remaining_records = remaining_squad.to_dict("records")

            for in_prod in itertools.product(*pos_cand_lists):
                in_players_flat = [p for sub in in_prod for p in sub]
                in_ids = [p["id"] for p in in_players_flat]
                if len(set(in_ids)) != len(in_ids):
                    continue

                in_cost_total = sum(p["Cost"] for p in in_players_flat)
                if in_cost_total > (budget_available + 1e-5):
                    continue

                temp_team_counts = dict(base_team_counts)
                team_valid = True
                for p in in_players_flat:
                    tid = p["team_id"]
                    temp_team_counts[tid] = temp_team_counts.get(tid, 0) + 1
                    if temp_team_counts[tid] > 3:
                        team_valid = False
                        break
                if not team_valid:
                    continue

                quick_xp = sum(p["Horizon_xP"] for p in in_players_flat) - out_players["Horizon_xP"].sum()
                target_bonus = sum(25.0 for pid in in_ids if pid in target_in_set)
                heuristic_score = quick_xp + target_bonus
                candidate_in_combos.append((heuristic_score, in_players_flat, out_players))

            if not candidate_in_combos:
                continue

            candidate_in_combos.sort(key=lambda x: x[0], reverse=True)
            top_to_eval = candidate_in_combos[:80]

            for heuristic_score, in_players_flat, out_p_df in top_to_eval:
                _starter_ids = _fast_xi_player_set(remaining_records + in_players_flat)
                new_starting_xp = _fast_xi_xp(remaining_records + in_players_flat)

                raw_starter_xp = sum(
                    p.get("Horizon_xP", 0) for p in (remaining_records + in_players_flat) if p["id"] in _starter_ids
                )
                total_squad_xp = (
                    sum(p.get("Horizon_xP", 0) for p in remaining_records)
                    + sum(p.get("Horizon_xP", 0) for p in in_players_flat)
                )
                new_bench_xp = max(0.0, total_squad_xp - raw_starter_xp)

                starting_gain = new_starting_xp - base_xp
                target_matches = sum(1 for p in in_players_flat if p["id"] in target_in_set)
                
                # 1.0 xP transfer friction per transaction to reflect the option value of an FT
                transfer_friction = 1.0 * len(in_players_flat)

                eval_score = (
                    (new_starting_xp * 1.0)
                    + (0.10 * new_bench_xp)
                    + (target_matches * 15.0)
                    - transfer_friction
                )

                if best_overall_plan is None or eval_score > best_eval_score:
                    best_eval_score = eval_score
                    best_starting_gain = starting_gain
                    best_overall_plan = {
                        "out_players": out_p_df,
                        "in_players": in_players_flat,
                        "remaining_squad": remaining_squad,
                        "budget_available": budget_available,
                        "starting_gain": starting_gain,
                        "target_matches": target_matches,
                    }

    if best_overall_plan is None:
        curr = current_squad_df.copy()
        curr["is_transfer_in"] = False
        curr["is_target_in"] = False
        return curr, []

    refined_in_players, _leftover_after_refine = _maximize_leftover_budget(
        best_overall_plan["in_players"],
        best_overall_plan["remaining_squad"],
        best_overall_plan["budget_available"],
        avail_cands,
        target_in_set,
    )

    refined_squad = pd.concat(
        [best_overall_plan["remaining_squad"], pd.DataFrame(refined_in_players)],
        ignore_index=True
    )
    refined_xi, refined_bench, _ = solve_optimal_xi(refined_squad)
    refined_cap = refined_xi["Proj_Pts"].max() if not refined_xi.empty else 0.0
    best_overall_plan["in_players"] = refined_in_players
    best_overall_plan["starting_gain"] = (refined_xi["Proj_Pts"].sum() + refined_cap) - base_xp
    best_overall_plan["target_matches"] = sum(
        1 for p in refined_in_players if p["id"] in target_in_set
    )
    best_overall_plan["new_squad"] = refined_squad

    out_df = best_overall_plan["out_players"].sort_values(by="Cost", ascending=False)
    in_df = pd.DataFrame(best_overall_plan["in_players"]).sort_values(by="Cost", ascending=False)

    paired_transfers = []
    used_in = set()
    for _, p_out in out_df.iterrows():
        match_in = in_df[(in_df["Pos"] == p_out["Pos"]) & (~in_df["id"].isin(used_in))]
        if match_in.empty:
            match_in = in_df[~in_df["id"].isin(used_in)]
        p_in = match_in.iloc[0]
        used_in.add(p_in["id"])

        cost_diff = p_in["Cost"] - p_out["Cost"]
        xp_gain = p_in["Horizon_xP"] - p_out["Horizon_xP"]
        is_target = p_in["id"] in target_in_set
        is_forced = p_out["id"] in force_out_set

        paired_transfers.append({
            "out": p_out,
            "in": p_in,
            "gain": round(xp_gain, 1),
            "cost_diff": round(cost_diff, 1),
            "target": is_target,
            "forced_out": is_forced,
        })

    final_squad = best_overall_plan["new_squad"].copy()
    new_in_ids = {p["id"] for p in best_overall_plan["in_players"]}
    final_squad["is_transfer_in"] = final_squad["id"].isin(new_in_ids)
    final_squad["is_target_in"] = final_squad["id"].map(lambda x: x in target_in_set and x in new_in_ids)

    return final_squad, paired_transfers


def prepare_xi_display(xi_df: pd.DataFrame, bench_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if xi_df is None or xi_df.empty:
        return xi_df, bench_df

    xi = xi_df.copy()
    bench = bench_df.copy() if bench_df is not None and not bench_df.empty else pd.DataFrame()

    xi["is_cap"] = False
    xi["is_vc"] = False
    xi["Multiplier"] = 1

    if not bench.empty:
        bench["is_cap"] = False
        bench["is_vc"] = False
        bench["Multiplier"] = 1

    sorted_xi = xi.sort_values(by="Horizon_xP", ascending=False)
    if len(sorted_xi) > 0:
        top_id = sorted_xi.iloc[0]["id"]
        xi.loc[xi["id"] == top_id, "is_cap"] = True
        xi.loc[xi["id"] == top_id, "Multiplier"] = 2

    if len(sorted_xi) > 1:
        second_id = sorted_xi.iloc[1]["id"]
        xi.loc[xi["id"] == second_id, "is_vc"] = True

    return xi, bench


def render_transfer_pitch_component(
    starters_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    rolling_df: pd.DataFrame = None,
    fdr_map: dict = None,
    horizon_len: int = 1,
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
            is_in = bool(p.get("is_transfer_in") is True)
            is_target = bool(p.get("is_target_in") is True)
            is_out = bool(p.get("is_transfer_out") is True)

            cap_badge = ""
            if is_c:
                cap_badge = '<div class="pitch-cap-badge c">C</div>'
            elif is_v:
                cap_badge = '<div class="pitch-cap-badge vc">V</div>'
            elif is_target:
                cap_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px;">C </div>'
            elif is_in:
                cap_badge = '<div class="pitch-cap-badge" style="background:#10b981; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">IN</div>'
            elif is_out:
                cap_badge = '<div class="pitch-cap-badge" style="background:#ef4444; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">OUT</div>'

            img_url = get_player_img_url(p.get("photo"), p.get("code"))
            player_name = p.get("Player", "")

            proj = p.get("Horizon_xP", p.get("Proj_Pts", 0.0))
            cost = p.get("Cost", 0.0)
            cost_str = f"£{fmt_num(cost, '.1f')}m" if cost else ""
            mult_txt = f" ({mult}x)" if mult > 1 else ""

            tag = ""
            if is_target:
                tag = '<span style="color:#38bdf8; font-weight:800; font-size:0.58rem;"> [TARGET]</span>'
            elif is_in:
                tag = '<span style="color:#34d399; font-weight:800; font-size:0.58rem;"> [IN]</span>'
            elif is_out:
                tag = '<span style="color:#f87171; font-weight:800; font-size:0.58rem;"> [OUT]</span>'

            stat_pill_content = (
                f'<span style="color: #60a5fa; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;">{fmt_num(proj, ".1f")} xP{mult_txt}{tag}</span>'
                f'<span style="color: #94a3b8; font-size: 0.62rem; display: block; line-height: 1.1; margin-top: 1px;">{cost_str}</span>'
            )

            clean_url = html.escape(str(img_url))
            avatar_style = f"background-image: url('{clean_url}'), url('{SILHOUETTE_BASE64}');"
            tooltip_html = build_player_tooltip(p, horizon_len=horizon_len)

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
            is_b_in = bool(b.get("is_transfer_in") is True)
            is_b_target = bool(b.get("is_target_in") is True)
            is_b_out = bool(b.get("is_transfer_out") is True)

            bench_badge = ""
            if is_b_target:
                bench_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px;">B </div>'
            elif is_b_in:
                bench_badge = '<div class="pitch-cap-badge" style="background:#10b981; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">IN</div>'
            elif is_b_out:
                bench_badge = '<div class="pitch-cap-badge" style="background:#ef4444; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">OUT</div>'

            proj = b.get("Horizon_xP", b.get("Proj_Pts", 0.0))
            b_cost = b.get("Cost", 0.0)
            b_cost_str = f"£{fmt_num(b_cost, '.1f')}m" if b_cost else ""

            b_tag = ""
            if is_b_target:
                b_tag = '<span style="color:#38bdf8; font-weight:800; font-size:0.58rem;"> [TARGET]</span>'
            elif is_b_in:
                b_tag = '<span style="color:#34d399; font-weight:800; font-size:0.58rem;"> [IN]</span>'
            elif is_b_out:
                b_tag = '<span style="color:#f87171; font-weight:800; font-size:0.58rem;"> [OUT]</span>'

            b_stat_content = (
                f'<span style="color: #60a5fa; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;">{fmt_num(proj, ".1f")} xP{b_tag}</span>'
                f'<span style="color: #94a3b8; font-size: 0.62rem; display: block; line-height: 1.1; margin-top: 1px;">{b_cost_str}</span>'
            )

            sub_label = "Sub GKP" if pos == "GKP" else f"Sub {idx}"
            clean_url = html.escape(str(img_url))
            bench_avatar_style = f"background-image: url('{clean_url}'), url('{SILHOUETTE_BASE64}');"
            bench_tooltip_html = build_player_tooltip(b, horizon_len=horizon_len)

            bench_html += (
                f'<div class="pitch-player-node bench-node">'
                f'{bench_tooltip_html}'
                f'<div class="bench-order-tag">{sub_label}</div>'
                f'<div class="pitch-avatar-wrap">'
                f'<div class="pitch-player-avatar bench-avatar" style="{bench_avatar_style}"></div>'
                f'{bench_badge}'
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


def render_transfer_analyzer_tab(conn, events_df, current_gw):
    col_hdr, col_pop = st.columns([6.2, 0.8], vertical_alignment="center")
    with col_hdr:
        section_header(
            "Transfer Planner & Horizon Solver",
            "Formulate optimal multi-gameweek transfer routes with customized player locking and budget management",
        )
    with col_pop:
        render_guide_popover(
            title="Transfer Planner & Horizon Solver",
            subtitle="Formulate optimal multi-gameweek transfer routes with customized player locking and budget management",
            items=[
                {"badge": "Horizon", "title": "Multi-GW Optimization Horizon", "desc": "Solve transfers across 1 to 5 gameweeks to maximize cumulative expected points rather than single-week punts.", "color": "#38bdf8"},
                {"badge": "FTs & Hits", "title": "Transfer & Hit Constraints", "desc": "Configure available free transfers (FTs) and cap maximum allowed point deductions (-4, -8, etc.).", "color": "#10b981"},
                {"badge": "Lock/Exclude", "title": "Tactical Constraints", "desc": "Force must-keep players in your squad or exclude unwanted targets from the linear programming solver.", "color": "#818cf8"},
                {"badge": "Chips", "title": "Chip Strategy Simulation", "desc": "Simulate Wildcard or Free Hit setups to model total squad overhauls without transfer penalty points.", "color": "#f59e0b"},
                {"badge": "Market", "title": "Betting Market Blending", "desc": "Incorporate live bookmaker odds and sharp money line movements into player expected point calculations.", "color": "#38bdf8"},
                {"badge": "Lock Plan", "title": "Commit Transfer Snapshot", "desc": "Lock your solved transfer plan before deadline to track decision quality and outcome variance in the Audit Journal.", "color": "#10b981"},
            ],
            tip="Solving across a 3 to 5 gameweek horizon avoids burning transfers on short-term fixture spikes and conserves valuable FTs for unforeseen injuries.",
            key="guide_pop_transfer_analyzer",
        )

    mgr_to_use = st.session_state.get("manager_id", "").strip()
    if not mgr_to_use:
        st.info(":material/arrow_upward:  Enter your FPL ID in the top search bar to load your squad.")
        return

    mgr_data = fetch_transfer_manager_entry(mgr_to_use)
    mgr_history = fetch_transfer_manager_history(mgr_to_use)
    if not mgr_data:
        st.error("Could not fetch FPL manager profile.")
        return

    rolling_metrics_df = get_rolling_player_metrics(conn)
    teams_fdr_map = get_teams_fdr_map(conn, current_gw)

    import time
    now_epoch = int(time.time())
    upcoming_gws = []
    for _, r in events_df.iterrows():
        is_fin = str(r.get("finished", "")).strip().lower() in ["1", "true", "yes"]
        is_cur = str(r.get("is_current", "")).strip().lower() in ["1", "true", "yes"]
        try:
            dl_epoch = int(r.get("deadline_time_epoch", 2000000000))
        except (ValueError, TypeError):
            dl_epoch = 2000000000
        if not is_fin and not (is_cur or dl_epoch <= now_epoch):
            upcoming_gws.append(int(r["id"]))
            
    next_gw = upcoming_gws[0] if upcoming_gws else current_gw

    picks_data = fetch_transfer_manager_picks(mgr_to_use, next_gw)
    entry_hist = picks_data.get("entry_history", {})
    
    # Calculate bank balance adjusted for pending transfers
    base_bank = entry_hist.get("bank", mgr_data.get("last_deadline_bank", 0))
    
    picks_list = picks_data.get("picks", [])
    pick_ids = [p["element"] for p in picks_list]
    pending_transfers = fetch_transfer_manager_transfers(mgr_to_use)
    if pending_transfers:
        for t in reversed(pending_transfers):
            if t.get("event") == next_gw:
                out_id = t.get("element_out")
                in_id = t.get("element_in")
                out_cost = t.get("element_out_cost")
                in_cost = t.get("element_in_cost")
                if out_id in pick_ids:
                    idx = pick_ids.index(out_id)
                    pick_ids[idx] = in_id
                    # Adjust bank
                    base_bank = base_bank + out_cost - in_cost
                    for p in picks_list:
                        if p["element"] == out_id:
                            p["element"] = in_id
                            break
                            
    bank_balance = base_bank / 10.0
    if not pick_ids:
        st.warning("No squad picks retrieved for this manager.")
        return

    calc_ft = calculate_available_fts(mgr_history)

    # ── Horizon & Transfer Parameters ─────────────────────────────────────────
    st.markdown("#### :material/settings:  Parameters & Horizon")

    if pick_ids:
        placeholders = ",".join(["?"] * len(pick_ids))
        cur = conn.cursor()
        cur.execute(f"SELECT SUM(now_cost) FROM players WHERE id IN ({placeholders})", pick_ids)
        squad_sell = round((cur.fetchone()[0] or 1000) / 10.0, 1)
    else:
        squad_sell = 100.0
    itb_val = entry_hist.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
    team_val = round(squad_sell + itb_val, 1)

    chip_mode = st.radio(
        "Strategy Mode:",
        ["Regular Transfers", "Wildcard", "Free Hit"],
        horizontal=True,
        index=0,
    )

    if chip_mode == "Regular Transfers":
        c1, c2, c3, c4 = st.columns([1.6, 1.0, 1.0, 1.4], vertical_alignment="bottom")
        with c1:
            horizon_gws = st.selectbox(
                "Evaluation Horizon",
                options=[1, 2, 3, 5],
                format_func=lambda x: f"Next {x} Gameweek{'s' if x > 1 else ''} (GW{next_gw}–GW{next_gw + x - 1})",
                index=2,
            )
        with c2:
            ft_selected = st.number_input("Free Transfers", min_value=1, max_value=5, value=calc_ft, step=1)
        with c3:
            max_hits = st.number_input("Max Hits (-4)", min_value=0, max_value=5, value=0, step=1)
        with c4:
            total_allowed_transfers = int(ft_selected + max_hits)
            hit_cost_str = f"(-{max_hits * 4} pts)" if max_hits > 0 else "(0 pts)"
            st.metric("Planned Moves", f"{total_allowed_transfers} Transfers", delta=hit_cost_str if max_hits > 0 else None, delta_color="inverse")

    elif chip_mode == "Wildcard":
        horizon_gws = st.selectbox(
            "Evaluation Horizon",
            options=[3, 5, 8],
            format_func=lambda x: f"Next {x} Gameweeks (GW{next_gw}–GW{next_gw + x - 1})",
            index=1,
        )
        ft_selected = 15
        max_hits = 0
        total_allowed_transfers = 15
        st.info(":material/style:  **Wildcard Active**: Optimizing a permanent 15-man squad over the selected horizon with 0 point deductions.")
        st.metric("Available Budget", f"£{team_val:.1f}m", help=f"Squad Sell Value: £{squad_sell:.1f}m | ITB: £{itb_val:.1f}m")
        st.caption(f"Squad Sell Value: £{squad_sell:.1f}m | In The Bank: £{itb_val:.1f}m")

    else:
        horizon_gws = 1
        st.markdown("**Evaluation Horizon:** Next 1 Gameweek (Locked for Free Hit)")
        ft_selected = 15
        max_hits = 0
        total_allowed_transfers = 15
        st.info(":material/bolt:  **Free Hit Active**: Optimizing a single-gameweek £100m+ roster with 0 point deductions. Reverts automatically next gameweek.")
        st.metric("Available Budget", f"£{team_val:.1f}m", help=f"Squad Sell Value: £{squad_sell:.1f}m | ITB: £{itb_val:.1f}m")
        st.caption(f"Squad Sell Value: £{squad_sell:.1f}m | In The Bank: £{itb_val:.1f}m")

    # ── View & Model Controls ─────────────────────────────────────────────────
    col_tgl1, col_tgl2, col_tgl3, col_tgl4 = st.columns([1.3, 1.6, 1.4, 1.7], vertical_alignment="center")
    with col_tgl1:
        pitch_view = st.toggle(":material/stadium: **Pitch View**", value=True, key="transfer_pitch_toggle")
    with col_tgl2:
        enable_betting = st.toggle(":material/bar_chart:  **Betting Market xG**", value=True, key="transfer_betting_toggle")
    with col_tgl3:
        market_weight = 0.35
        if enable_betting:
            market_weight = st.slider(
                "Market Weight",
                min_value=0.0,
                max_value=1.0,
                value=0.35,
                step=0.05,
                key="transfer_mkt_weight",
            )
    with col_tgl4:
        min_avg_mins = st.slider(
            ":material/timer:  Min Avg Mins / GW",
            min_value=0,
            max_value=90,
            value=45,
            step=5,
            help="Filters out fringe players and cameo risks from transfer suggestions",
        )

    placeholders = ",".join(["?"] * len(pick_ids))
    squad_query = f"""
    SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
           t.short_name AS Team,
           CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
           p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
           p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
           p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    WHERE p.id IN ({placeholders})
    """
    squad_df = pd.read_sql(squad_query, conn, params=pick_ids)

    league_eval_df = evaluate_league_multi_gw(
        conn,
        next_gw,
        horizon_gws,
        enable_betting=enable_betting,
        market_weight=market_weight,
        factor_movement=True,
    )

    _is_ui_available = (league_eval_df["can_select"] == 1) & (league_eval_df["Status"] != "u")
    _not_in_squad = ~league_eval_df["id"].isin(pick_ids)

    available_market_df = league_eval_df[
        _not_in_squad & _is_ui_available
    ].sort_values(by="Horizon_xP", ascending=False)

    solver_candidate_df = available_market_df.copy()

    # ── Option Dictionaries for Consolidated Boxes ────────────────────────────
    pos_options = []
    pos_labels = {}
    for _, r in squad_df.iterrows():
        key = f"lock_{r['id']}"
        pos_options.append(key)
        pos_labels[key] = f"[Lock] Keep: {r['Player']} ({r['Team']} · {r['Pos']})"

    for _, r in available_market_df.iterrows():
        key = f"target_{r['id']}"
        pos_options.append(key)
        pos_labels[key] = f"[Target] Target: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m · {r['Horizon_xP']:.1f} xP)"

    neg_options = []
    neg_labels = {}
    for _, r in squad_df.iterrows():
        key = f"sell_{r['id']}"
        neg_options.append(key)
        neg_labels[key] = f"[Sell] Sell: {r['Player']} ({r['Team']} · {r['Pos']})"

    for _, r in available_market_df.iterrows():
        key = f"block_{r['id']}"
        neg_options.append(key)
        neg_labels[key] = f"[Blacklist] Blacklist: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m)"

    col_pos, col_neg = st.columns(2)
    with col_pos:
        selected_positive = st.multiselect("Priorities & Locks",
            options=pos_options,
            format_func=lambda k: pos_labels.get(k, k),
            default=[],
            help="Select squad players you want to lock and market players you want to prioritize buying.",
        )
        locked_players = [int(k.replace("lock_", "")) for k in selected_positive if k.startswith("lock_")]
        targeted_in_players = [int(k.replace("target_", "")) for k in selected_positive if k.startswith("target_")]

    with col_neg:
        selected_negative = st.multiselect("Forced Sales & Blacklist",
            options=neg_options,
            format_func=lambda k: neg_labels.get(k, k),
            default=[],
            help="Select squad players you must sell and market players you refuse to buy.",
        )
        force_out_players = [int(k.replace("sell_", "")) for k in selected_negative if k.startswith("sell_")]
        blocked_in_players = [int(k.replace("block_", "")) for k in selected_negative if k.startswith("block_")]

        if targeted_in_players and len(targeted_in_players) > total_allowed_transfers:
            st.warning(
                f":material/warning:  You targeted {len(targeted_in_players)} players, but only have {total_allowed_transfers} transfer(s) planned. Targets will be prioritized up to your limit."
            )

        submit_solve = st.button(":material/rocket:  Solve Transfers", width="stretch", type="primary")

    state_key = f"transfer_solve_{mgr_to_use}_{chip_mode}_{horizon_gws}_{ft_selected}_{max_hits}_{market_weight}"
    results_slot = st.empty()

    if submit_solve:
        with results_slot.container():
            render_optimizer_status(
                title="Solving optimal transfer path...",
                subtext=f"Evaluating multi-gameweek projections across GW{next_gw} to GW{next_gw + horizon_gws - 1}...",
            )
            render_skeleton_cards(count=1)

        curr_squad_horizon = league_eval_df[league_eval_df["id"].isin(pick_ids)].copy()

        _missing_pick_ids = set(pick_ids) - set(curr_squad_horizon["id"].tolist())
        if _missing_pick_ids:
            _miss_ph = ",".join(["?"] * len(_missing_pick_ids))
            _missing_df = pd.read_sql(
                f"""SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
                       t.short_name AS Team,
                       CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF'
                           WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
                       p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
                       p.total_points AS Season_Points, p.form AS Form,
                       p.points_per_game AS PPG, p.status AS Status,
                       p.chance_of_playing_next_round AS Chance, p.news AS News
                FROM players p INNER JOIN teams t ON p.team = t.id
                WHERE p.id IN ({_miss_ph})""",
                conn,
                params=list(_missing_pick_ids),
            )
            for _col in ["avg_mins", "Horizon_xP", "Proj_Pts", "Avg_xP"]:
                _missing_df[_col] = 0.0
            for _gw in range(next_gw, next_gw + horizon_gws):
                _missing_df[f"GW{_gw}"] = 0.0
            curr_squad_horizon = pd.concat([curr_squad_horizon, _missing_df], ignore_index=True)

        if chip_mode in ["Wildcard", "Free Hit"]:
            transferred_squad_df, swaps = solve_chip_transfers_pulp(
                current_squad_df=curr_squad_horizon,
                candidate_league_df=league_eval_df,
                team_value=team_val,
                locked_player_ids=locked_players,
                target_in_player_ids=targeted_in_players,
                force_out_player_ids=force_out_players,
                blocked_in_player_ids=blocked_in_players,
                is_free_hit=(chip_mode == "Free Hit"),
            )
        else:
            transferred_squad_df, swaps = solve_multi_gw_transfers(
                current_squad_df=curr_squad_horizon,
                candidate_league_df=solver_candidate_df,
                bank=bank_balance,
                num_transfers=total_allowed_transfers,
                locked_player_ids=locked_players,
                target_in_player_ids=targeted_in_players,
                force_out_player_ids=force_out_players,
                blocked_in_player_ids=blocked_in_players,
                min_avg_minutes=min_avg_mins,
            )

        st.session_state[state_key] = {
            "transferred_squad_df": transferred_squad_df,
            "swaps": swaps,
            "curr_squad_horizon": curr_squad_horizon,
            "locked_players": locked_players,
            "targeted_in_players": targeted_in_players,
        }
        st.session_state["transfer_result"] = st.session_state[state_key]
        results_slot.empty()

    if state_key not in st.session_state:
        st.info(":material/arrow_upward:  Adjust settings and click 'Solve Transfers' to begin.")
        return

    res = st.session_state[state_key]
    transferred_squad_df = res["transferred_squad_df"]
    swaps = res["swaps"]
    curr_squad_horizon = res["curr_squad_horizon"]
    locked_players = res["locked_players"]
    targeted_in_players = res["targeted_in_players"]

    out_ids = {s["out"]["id"] for s in swaps}
    in_ids = {s["in"]["id"] for s in swaps}

    curr_squad_horizon["is_transfer_out"] = curr_squad_horizon["id"].isin(out_ids)
    curr_squad_horizon["is_transfer_in"] = False

    raw_base_xi, raw_base_bench, base_formation = solve_optimal_xi(curr_squad_horizon)
    raw_trans_xi, raw_trans_bench, trans_formation = solve_optimal_xi(transferred_squad_df)

    base_xi, base_bench = prepare_xi_display(raw_base_xi, raw_base_bench)
    trans_xi, trans_bench = prepare_xi_display(raw_trans_xi, raw_trans_bench)

    base_pts = (base_xi["Horizon_xP"] * base_xi["Multiplier"]).sum() + 0.10 * (base_bench["Horizon_xP"].sum() if not base_bench.empty else 0)
    trans_pts = (trans_xi["Horizon_xP"] * trans_xi["Multiplier"]).sum() + 0.10 * (trans_bench["Horizon_xP"].sum() if not trans_bench.empty else 0)
    actual_hit_cost = 0 if chip_mode != "Regular Transfers" else max(0, len(swaps) - ft_selected) * 4
    net_pts_gain = (trans_pts - base_pts) - actual_hit_cost

    with results_slot.container():
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"Starting XI {horizon_gws}-GW xP", f"{trans_pts:.1f} xP", delta=f"{trans_pts - base_pts:+.1f} Raw xP")
        m2.metric(
            "Net Projected Gain",
            f"{net_pts_gain:+.1f} xP",
            delta=f"-{actual_hit_cost} Hit Penalty" if actual_hit_cost > 0 else "Free Transfers",
        )
        m3.metric("Remaining In Bank", f"£{(bank_balance - sum(s['cost_diff'] for s in swaps)):.1f}m")
        m4.metric("Moves Executed", f"{len(swaps)} of {total_allowed_transfers}")

        if chip_mode == "Wildcard":
            st.markdown("### :material/style:  Optimal Wildcard Squad (Permanent Overhaul, 0 Hits)")
        elif chip_mode == "Free Hit":
            st.markdown("### :material/bolt:  Optimal Free Hit Squad (1-Week Maximum Ceiling, 0 Hits)")
        else:
            hit_val = max(0, len(swaps) - ft_selected) * 4
            hit_str = f"-{hit_val} pts" if hit_val > 0 else "0 pts"
            st.markdown(f"### :material/my_location: Optimal Transfer Route ({len(swaps)} moves, {hit_str})")

            if not swaps:
                st.success(":material/check_circle:  Your current squad is optimal for this horizon. No transfer yields higher starting points within your budget.")
            else:
                for s in swaps:
                    c_out, c_in, c_delta = st.columns([3, 3, 2])
                    is_target = s.get("target", False)
                    is_forced = s.get("forced_out", False)

                    out_badge_title = "[!] FORCED SALE" if is_forced else "[OUT] TRANSFER OUT"
                    in_badge_title = "[TARGET] TARGET SIGNING" if is_target else "[IN] TRANSFER IN"
                    in_badge_color = "#38bdf8" if is_target else "#4ade80"
                    in_bg_color = "rgba(56, 189, 248, 0.1)" if is_target else "rgba(34, 197, 94, 0.1)"
                    in_border_color = "rgba(56, 189, 248, 0.35)" if is_target else "rgba(34, 197, 94, 0.3)"

                    with c_out:
                        st.markdown(
                            f"""
                            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 8px 12px;">
                                <span style="font-size: 0.72rem; font-weight: 800; color: #f87171;">{out_badge_title}</span><br>
                                <strong>{s['out']['Player']}</strong> ({s['out']['Team']}) · £{s['out']['Cost']:.1f}m<br>
                                <span style="font-size: 0.78rem; color: #94a3b8;">{horizon_gws}-GW xP: {s['out']['Horizon_xP']:.1f} xP</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with c_in:
                        st.markdown(
                            f"""
                            <div style="background: {in_bg_color}; border: 1px solid {in_border_color}; border-radius: 8px; padding: 8px 12px;">
                                <span style="font-size: 0.72rem; font-weight: 800; color: {in_badge_color};">{in_badge_title}</span><br>
                                <strong>{s['in']['Player']}</strong> ({s['in']['Team']}) · £{s['in']['Cost']:.1f}m<br>
                                <span style="font-size: 0.78rem; color: #94a3b8;">{horizon_gws}-GW xP: {s['in']['Horizon_xP']:.1f} xP</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with c_delta:
                        st.markdown(
                            f"""
                            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 8px 12px; height: 100%; display: flex; flex-direction: column; justify-content: center;">
                                <span style="font-size: 0.72rem; color: #94a3b8;">Expected Gain:</span>
                                <span style="font-size: 1.1rem; font-weight: 800; color: #38bdf8;">{s['gain']:+.1f} xP</span>
                                <span style="font-size: 0.72rem; color: #64748b;">Cost: {s['cost_diff']:+.1f}m</span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)

        existing_snap = get_snapshot(conn, mgr_to_use, next_gw)
        snap_locked = existing_snap is not None

        if is_owner_manager(mgr_to_use):
            st.markdown("<div style='margin-top: 15px; margin-bottom: 5px;'></div>", unsafe_allow_html=True)
            col_lock_btn, col_lock_info = st.columns([2.2, 7.8], vertical_alignment="center")

            with col_lock_btn:
                if snap_locked:
                    lock_btn = st.button("Re-Lock Transfer Plan", key="tab3_relock_btn")
                else:
                    lock_btn = st.button("Lock Transfer Plan Snapshot", type="primary", key="tab3_lock_btn")

            with col_lock_info:
                if snap_locked:
                    lock_time = existing_snap.get("created_at", "")[:16].replace("T", " ")
                    src_label = existing_snap.get("source", "Squad Analyzer")
                    st.markdown(
                        f"<div style='font-size: 0.85rem; color: #22c55e; font-weight: 600;'>Locked at {lock_time} ({src_label})</div>",
                        unsafe_allow_html=True,
                    )

            if lock_btn:
                starters_list = trans_xi.to_dict("records")
                for p in starters_list:
                    p["is_starter"] = True
                    if "Proj_Pts" not in p or not p["Proj_Pts"]:
                        p["Proj_Pts"] = p.get("Horizon_xP", p.get("Avg_xP", 0.0))
                bench_list = trans_bench.to_dict("records")
                for p in bench_list:
                    p["is_starter"] = False
                    if "Proj_Pts" not in p or not p["Proj_Pts"]:
                        p["Proj_Pts"] = p.get("Horizon_xP", p.get("Avg_xP", 0.0))
                lineup_data = starters_list + bench_list

                transfers_data = []
                if swaps:
                    for s in swaps:
                        transfers_data.append({
                            "out_name": s["out"]["Player"],
                            "in_name": s["in"]["Player"],
                            "out_cost": s["out"]["Cost"],
                            "in_cost": s["in"]["Cost"],
                            "gain": s.get("gain", 0.0),
                        })

                save_pre_gw_snapshot(
                    conn=conn,
                    manager_id=mgr_to_use,
                    gw=next_gw,
                    lineup_data=lineup_data,
                    transfers_data=transfers_data,
                    formation=trans_formation,
                    market_weight=market_weight,
                    factor_movement=True,
                    chip="Wildcard" if chip_mode == "Wildcard" else ("Free Hit" if chip_mode == "Free Hit" else None),
                    source="Transfer Solver",
                )
                st.toast(f"Transfer plan snapshot locked for GW{next_gw}!", icon=":material/lock:")
                st.rerun()

        st.markdown("### :material/balance:  Squad Visual Comparison (Current vs Transfer)")
        is_dark_theme = st.session_state.get("theme_mode", "dark") == "dark"
        banner_title_col = "#f8fafc" if is_dark_theme else "#0f172a"
        banner_sub_col = "#94a3b8" if is_dark_theme else "#64748b"

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown(
                f"""
                <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    <span style="font-size: 0.92rem; font-weight: 700; color: {banner_title_col};">Current Squad ({horizon_gws}-GW Run)</span>
                    <span style="font-size: 0.80rem; font-weight: 600; color: {banner_sub_col}; margin-left: 6px;">({base_formation} · {base_pts:.1f} xP)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if pitch_view:
                render_transfer_pitch_component(
                    base_xi,
                    base_bench,
                    rolling_df=rolling_metrics_df,
                    fdr_map=teams_fdr_map,
                    horizon_len=horizon_gws,
                )
            else:
                for idx, (_, row) in enumerate(base_xi.iterrows()):
                    tags = [(row["Pos"], "blue")]
                    if bool(row.get("is_forced_out") is True):
                        tags.append(("Transfer Out (Forced)", "red"))
                    elif bool(row.get("is_transfer_out") is True):
                        tags.append(("Transfer Out", "red"))

                    if row.get("is_cap") is True:
                        tags.append(("Captain", "green"))
                    elif row.get("is_vc") is True:
                        tags.append(("Vice Captain", "yellow"))
                    render_list_card(
                        f"{row['Player']} · {row['Team']}",
                        tags,
                        f'<span>Horizon xP</span> <strong>{fmt_num(row["Horizon_xP"], ".1f")}</strong> · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                        img_url=get_player_img_url(row.get("photo"), row.get("code")),
                    )
                if not base_bench.empty:
                    st.markdown("##### :material/chair:  Current Bench")
                    for idx, (_, row) in enumerate(base_bench.iterrows()):
                        pos = row.get("Pos", "")
                        sub_label = "Sub GKP" if pos == "GKP" else f"Sub {idx}"
                        tags = [(pos, "blue"), (sub_label, "gray")]
                        if bool(row.get("is_forced_out") is True):
                            tags.append(("Transfer Out (Forced)", "red"))
                        elif bool(row.get("is_transfer_out") is True):
                            tags.append(("Transfer Out", "red"))
                        render_list_card(
                            f"{row['Player']} · {row['Team']}",
                            tags,
                            f'<span>Horizon xP</span> {fmt_num(row["Horizon_xP"], ".1f")} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                            img_url=get_player_img_url(row.get("photo"), row.get("code")),
                        )

        with col_right:
            squad_title = (
                f"Optimal Wildcard Squad ({horizon_gws}-GW Run)"
                if chip_mode == "Wildcard"
                else (
                    "Optimal Free Hit Squad"
                    if chip_mode == "Free Hit"
                    else f"Transfer Squad ({horizon_gws}-GW Run)"
                )
            )
            st.markdown(
                f"""
                <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    <span style="font-size: 0.92rem; font-weight: 700; color: {banner_title_col};">{squad_title}</span>
                    <span style="font-size: 0.80rem; font-weight: 600; color: {banner_sub_col}; margin-left: 6px;">({trans_formation} · {trans_pts:.1f} xP)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if pitch_view:
                render_transfer_pitch_component(
                    trans_xi,
                    trans_bench,
                    rolling_df=rolling_metrics_df,
                    fdr_map=teams_fdr_map,
                    horizon_len=horizon_gws,
                )
            else:
                for idx, (_, row) in enumerate(trans_xi.iterrows()):
                    tags = [(row["Pos"], "blue")]
                    if bool(row.get("is_target_in") is True):
                        tags.append(("Target In", "yellow"))
                    elif bool(row.get("is_transfer_in") is True):
                        tags.append(("Transfer In", "green"))

                    if row.get("is_cap") is True:
                        tags.append(("Captain", "green"))
                    elif row.get("is_vc") is True:
                        tags.append(("Vice Captain", "yellow"))
                    render_list_card(
                        f"{row['Player']} · {row['Team']}",
                        tags,
                        f'<span>Horizon xP</span> <strong>{fmt_num(row["Horizon_xP"], ".1f")}</strong> · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                        img_url=get_player_img_url(row.get("photo"), row.get("code")),
                    )
                if not trans_bench.empty:
                    st.markdown("##### :material/group:  Transfer Bench")
                    for idx, (_, row) in enumerate(trans_bench.iterrows()):
                        pos = row.get("Pos", "")
                        sub_label = "Sub GKP" if pos == "GKP" else f"Sub {idx}"
                        tags = [(pos, "blue"), (sub_label, "gray")]
                        if bool(row.get("is_target_in") is True):
                            tags.append(("Target In", "yellow"))
                        elif bool(row.get("is_transfer_in") is True):
                            tags.append(("Transfer In", "green"))
                        render_list_card(
                            f"{row['Player']} · {row['Team']}",
                            tags,
                            f'<span>Horizon xP</span> {fmt_num(row["Horizon_xP"], ".1f")} · <span>Cost</span> £{fmt_num(row["Cost"], ".1f")}',
                            img_url=get_player_img_url(row.get("photo"), row.get("code")),
                        )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(":material/save:  Save Transfer Plan for Simulator", key="save_transfer_sim_btn", type="primary", use_container_width=True):
                st.session_state["transfer_result"] = {
                    "transferred_squad_df": transferred_squad_df,
                    "swaps": swaps,
                    "curr_squad_horizon": curr_squad_horizon,
                    "locked_players": locked_players,
                    "targeted_in_players": targeted_in_players,
                }
                st.toast("Transfer Plan Saved! Navigate to Match Simulator to run scenarios.", icon=":material/check_circle: ")

        st.markdown("### :material/content_paste:  Multi-Gameweek Performance Ledger")
        display_ledger = transferred_squad_df.copy()
        display_ledger["Role"] = display_ledger["id"].map(
            lambda x: (
                "Target Signing"
                if x in in_ids and x in (targeted_in_players or [])
                else ("New Signing" if x in in_ids else ("Locked" if x in locked_players else "Retained"))
            )
        )

        gw_cols = [f"GW{g}" for g in range(next_gw, next_gw + horizon_gws)]
        cols_to_show = ["Role", "Player", "Team", "Pos", "Cost", "Horizon_xP", "Avg_xP"] + gw_cols
        cols_to_show = [c for c in cols_to_show if c in display_ledger.columns]

        st.dataframe(display_ledger[cols_to_show], hide_index=True, use_container_width=True)