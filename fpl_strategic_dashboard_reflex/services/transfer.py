import html
import itertools
import math
import os
from collections import Counter

import pandas as pd
import pulp
import requests

from fpl_strategic_dashboard_reflex.services.cache import ttl_cache
from fpl_strategic_dashboard_reflex.services.betting import (
    load_db_market_odds,
    get_fixture_market_xg_and_movement,
)
from fpl_strategic_dashboard_reflex.services.db import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)
def fmt_num(val, fmt=".1f"):
    try:
        return format(float(val), fmt)
    except (ValueError, TypeError):
        return str(val)


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
        news_row = f'<div class="tt-row tt-news"><span>⚠️ {clean_news}</span></div>'
        news_row = f'<div class="tt-row tt-news"><span>• {clean_news}</span></div>'

    transfer_badge_row = ""
    if bool(p.get("is_transfer_in") is True):
        if bool(p.get("is_target_in") is True):
            transfer_badge_row = '<div class="tt-row" style="color:#38bdf8; font-weight:700;"><span>🎯 Target Signing</span></div>'
            transfer_badge_row = '<div class="tt-row" style="color:#38bdf8; font-weight:700;"><span>Target Signing</span></div>'
        else:
            transfer_badge_row = '<div class="tt-row" style="color:#34d399; font-weight:700;"><span>🟢 Proposed Sign</span></div>'
            transfer_badge_row = '<div class="tt-row" style="color:#34d399; font-weight:700;"><span>Proposed Sign</span></div>'
    elif bool(p.get("is_transfer_out") is True):
        if bool(p.get("is_forced_out") is True):
            transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>🔴 Forced Sale</span></div>'
            transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>Forced Sale</span></div>'
        else:
            transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>🔴 Proposed Sale</span></div>'
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
) -> tuple[float, dict | None, dict | None]:
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
            "Verdict": "Market Bullish 📈" if diff > 0 else "Market Bearish 📉",
            "Verdict": "Market Bullish" if diff > 0 else "Market Bearish",
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


def fetch_transfer_manager_entry(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def fetch_transfer_manager_history(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


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
           p.first_name, p.second_name, p.can_select,
           t.short_name AS Team,
           CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
           p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
           p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
           p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
           p.expected_goal_involvements_per_90 AS xGI_per_90
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    """
    players_df = pd.read_sql(all_players_query, _conn)
    hist_baselines = get_historical_player_baselines(_conn)
    rolling_metrics = get_rolling_player_metrics(_conn)
    market_cache = load_db_market_odds(_conn) if enable_betting else {}

    # Build fixture_map keyed by (team_id, gw) -> list of fixture dicts (supports DGWs)
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
            or p.get("Chance") == "0"
        )
        if is_unavailable:
            p_dict = dict(p)
            p_dict["avg_mins"] = 0.0
            p_dict["Horizon_xP"] = 0.0
            p_dict["Proj_Pts"] = 0.0
            p_dict["Target_Horizon_xP"] = 0.0
            p_dict["Avg_xP"] = 0.0
            first_gw_fixtures = fixture_map.get((p["team_id"], start_gw), [])
            p_dict["Opponent"] = first_gw_fixtures[0]["opponent"] if first_gw_fixtures else "-"
            p_dict["FDR"] = first_gw_fixtures[0]["fdr"] if first_gw_fixtures else 3
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
            p_dict["Target_Horizon_xP"] = 0.0
            p_dict["Avg_xP"] = 0.0
            first_gw_fixtures = fixture_map.get((p["team_id"], start_gw), [])
            p_dict["Opponent"] = first_gw_fixtures[0]["opponent"] if first_gw_fixtures else "-"
            p_dict["FDR"] = first_gw_fixtures[0]["fdr"] if first_gw_fixtures else 3
            for gw in range(start_gw, end_gw + 1):
                p_dict[f"GW{gw}"] = 0.0
                p_dict[f"Target_GW{gw}"] = 0.0
            results.append(p_dict)
            continue

        total_horizon_xp = 0.0
        total_target_horizon_xp = 0.0
        gw_breakdown = {}
        target_gw_breakdown = {}
        team_id = p["team_id"]

        # p_target: same player with is_target=True for calculate_projected_points
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

                    if enable_betting and f_data.get("opponent"):
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
        first_gw_fixtures = fixture_map.get((team_id, start_gw), [])
        if first_gw_fixtures:
            p_dict["Opponent"] = first_gw_fixtures[0]["opponent"]
            p_dict["FDR"] = first_gw_fixtures[0]["fdr"]
        else:
            p_dict["Opponent"] = "-"
            p_dict["FDR"] = 3
        p_dict.update(gw_breakdown)
        p_dict.update(target_gw_breakdown)
        results.append(p_dict)

    return pd.DataFrame(results)


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
    current_squad_df: pd.DataFrame,
    candidate_league_df: pd.DataFrame,
    team_value: float,
    locked_player_ids: list = None,
    target_in_player_ids: list = None,
    force_out_player_ids: list = None,
    blocked_in_player_ids: list = None,
    is_free_hit: bool = False,
) -> tuple[pd.DataFrame, list[dict]]:
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

    # Generate pairwise swaps for UI
    outs = current_squad_df[~current_squad_df["id"].isin(final_squad["id"].tolist())].to_dict("records")
    ins = final_squad[~final_squad["id"].isin(current_squad_df["id"].tolist())].to_dict("records")
    swaps = []
    used_ins = set()
    unmatched_outs = []

    for out_p in outs:
        pos = out_p.get("Pos")
        matched_in = None
        for in_p in ins:
            if in_p.get("Pos") == pos and in_p["id"] not in used_ins:
                matched_in = in_p
                used_ins.add(in_p["id"])
                break
        if matched_in:
            cost_diff = round(float(matched_in.get("Cost", 0.0)) - float(out_p.get("Cost", 0.0)), 1)
            gain = round(float(matched_in.get("Horizon_xP", 0.0)) - float(out_p.get("Horizon_xP", 0.0)), 1)
            swaps.append({
                "out": out_p,
                "in": matched_in,
                "cost_diff": cost_diff,
                "gain": gain,
                "forced_out": out_p.get("id") in (force_out_player_ids or []),
                "target": matched_in.get("id") in target_in_set,
            })
        else:
            unmatched_outs.append(out_p)

    remaining_ins = [in_p for in_p in ins if in_p["id"] not in used_ins]
    for out_p, in_p in zip(unmatched_outs, remaining_ins):
        cost_diff = round(float(in_p.get("Cost", 0.0)) - float(out_p.get("Cost", 0.0)), 1)
        gain = round(float(in_p.get("Horizon_xP", 0.0)) - float(out_p.get("Horizon_xP", 0.0)), 1)
        swaps.append({
            "out": out_p,
            "in": in_p,
            "cost_diff": cost_diff,
            "gain": gain,
            "forced_out": out_p.get("id") in (force_out_player_ids or []),
            "target": in_p.get("id") in target_in_set,
        })

    return final_squad, swaps


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
        curr["is_transfer_in"] = False
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

    # Override Horizon_xP with Target_Horizon_xP for targeted players (matches reference)
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


def enrich_transfer_squad_for_list_view(df: pd.DataFrame, horizon_len: int = 5) -> pd.DataFrame:
    """Enriches transfer squad records with all styling, avatar URLs, and badge labels for List View."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    pos_colors = {"GKP": "amber", "DEF": "blue", "MID": "green", "FWD": "purple"}
    df["Pos_Color"] = df["Pos"].map(lambda p: pos_colors.get(str(p), "gray"))

    def _cap_badge(r):
        mult = int(r.get("Multiplier") or 1)
        if mult == 3:
            return "3x TC"
        if r.get("is_cap"):
            return "Captain (2x)"
        if r.get("is_vc"):
            return "Vice Captain"
        if r.get("is_transfer_in"):
            return "TRANSFER IN"
        if r.get("is_transfer_out"):
            return "TRANSFER OUT"
        return ""

    def _cap_badge_color(r):
        mult = int(r.get("Multiplier") or 1)
        if mult == 3:
            return "purple"
        if r.get("is_cap"):
            return "green"
        if r.get("is_vc"):
            return "amber"
        if r.get("is_transfer_in"):
            return "cyan"
        if r.get("is_transfer_out"):
            return "red"
        return "gray"

    df["Cap_Badge"] = df.apply(_cap_badge, axis=1)
    df["Cap_Badge_Color"] = df.apply(_cap_badge_color, axis=1)

    # Cost display (explicitly formatted with unicode pound symbol)
    df["Cost_Display"] = df["Cost"].map(lambda c: f"\u00a3{float(c):.1f}m" if pd.notna(c) and c != "" else "\u00a30.0m")

    # Projection display: show Horizon xP or Proj_Pts
    pts_col = "Horizon_xP" if "Horizon_xP" in df.columns else ("Proj_Pts" if "Proj_Pts" in df.columns else None)
    if pts_col:
        df["Proj_Pts_Display"] = df[pts_col].map(lambda p: f"{float(p):.1f}" if pd.notna(p) and p != "" else "0.0")
    else:
        df["Proj_Pts_Display"] = "0.0"

    # FDR display & color
    if "Avg_FDR" in df.columns and horizon_len > 1 and "FDR" not in df.columns:
        df["FDR_Color"] = df["Avg_FDR"].map(lambda f: "green" if float(f or 3) <= 2.8 else ("amber" if float(f or 3) <= 3.4 else "red"))
        df["FDR_Display"] = df["Avg_FDR"].map(lambda f: f"Avg FDR {float(f):.1f}" if pd.notna(f) and f != "" else "FDR 3")
    elif "FDR" in df.columns:
        df["FDR_Color"] = df["FDR"].map(lambda f: "green" if float(f or 3) <= 2 else ("amber" if float(f or 3) == 3 else "red"))
        df["FDR_Display"] = df["FDR"].map(lambda f: f"FDR {int(round(float(f)))}" if pd.notna(f) and f != "" else "FDR 3")
    else:
        df["FDR_Color"] = "gray"
        df["FDR_Display"] = f"{horizon_len} GWs"

    # Opponent display
    if "Opponent" in df.columns:
        df["Opponent_Display"] = df["Opponent"].map(
            lambda o: f"vs {str(o).strip()}" if pd.notna(o) and str(o).strip() not in ["", "-"] else f"{horizon_len}-GW Run"
        )
    else:
        df["Opponent_Display"] = f"{horizon_len}-GW Run"

    # News (filter out None, nan, empty string)
    if "News" not in df.columns:
        df["News"] = ""
    else:
        df["News"] = df["News"].fillna("").map(
            lambda n: str(n).strip() if pd.notna(n) and str(n).strip().lower() not in ["", "none", "nan"] else ""
        )

    # photo_url
    df["photo_url"] = df.apply(
        lambda r: f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{int(r['code'])}.png" if pd.notna(r.get("code")) and r.get("code") else "",
        axis=1,
    )

    if "is_transfer_in" not in df.columns:
        df["is_transfer_in"] = False
    if "is_transfer_out" not in df.columns:
        df["is_transfer_out"] = False

    return df


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
                cap_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px;">🎯</div>'
                cap_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px; font-weight:800;">TRG</div>'
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
                tag = '<span style="color:#38bdf8; font-weight:800; font-size:0.58rem;"> [🎯 TARGET]</span>'
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
                bench_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px;">🎯</div>'
                bench_badge = '<div class="pitch-cap-badge" style="background:#0284c7; color:#ffffff; font-size:0.55rem; width:18px; height:18px; font-weight:800;">TRG</div>'
            elif is_b_in:
                bench_badge = '<div class="pitch-cap-badge" style="background:#10b981; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">IN</div>'
            elif is_b_out:
                bench_badge = '<div class="pitch-cap-badge" style="background:#ef4444; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">OUT</div>'

            proj = b.get("Horizon_xP", b.get("Proj_Pts", 0.0))
            b_cost = b.get("Cost", 0.0)
            b_cost_str = f"£{fmt_num(b_cost, '.1f')}m" if b_cost else ""

            b_tag = ""
            if is_b_target:
                b_tag = '<span style="color:#38bdf8; font-weight:800; font-size:0.58rem;"> [🎯 TARGET]</span>'
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
        f'  z-index: 1;'
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
        f'@keyframes pitchRowIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}'
        f'@keyframes capBadgeSpringIn {{ 0% {{ opacity: 0; transform: scale(0); }} 70% {{ opacity: 1; transform: scale(1.18); }} 100% {{ opacity: 1; transform: scale(1); }} }}'
        f'.pitch-formation-row {{ display: flex; justify-content: space-around; align-items: center; z-index: 2; width: 100%; margin: 2px 0; position: relative; animation: pitchRowIn 250ms cubic-bezier(0.16, 1, 0.3, 1) both; }}'
        f'.pitch-formation-row:nth-of-type(1) {{ animation-delay: 0.00s; }}'
        f'.pitch-formation-row:nth-of-type(2) {{ animation-delay: 0.05s; }}'
        f'.pitch-formation-row:nth-of-type(3) {{ animation-delay: 0.10s; }}'
        f'.pitch-formation-row:nth-of-type(4) {{ animation-delay: 0.15s; }}'
        f'.pitch-player-node {{ display: flex; flex-direction: column; align-items: center; flex: 1; max-width: 68px; min-width: 0; text-align: center; position: relative; cursor: pointer; transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), filter 0.18s ease; }}'
        f'.pitch-player-node:hover {{ z-index: 120 !important; transform: translateY(-3px); filter: drop-shadow(0 6px 14px rgba(0, 0, 0, 0.45)); }}'
        f'.pitch-player-node:active {{ transform: scale(0.97); }}'
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
        f'.pitch-cap-badge {{ position: absolute; top: -4px; right: -4px; width: 18px; height: 18px; border-radius: 50%; font-size: 0.65rem; font-weight: 800; display: flex; align-items: center; justify-content: center; border: 1.5px solid #ffffff; box-shadow: 0 1px 3px rgba(0,0,0,0.4); animation: capBadgeSpringIn 300ms cubic-bezier(0.175, 0.885, 0.32, 1.275) both; }}'
        f'.pitch-cap-badge.c {{ background: #22c55e; color: #ffffff; }}'
        f'.pitch-cap-badge.tc {{ background: #eab308; color: #000000; }}'
        f'.pitch-cap-badge.vc {{ background: #3b82f6; color: #ffffff; }}'
        f'.pitch-name-pill {{ background: #0f172a; color: #f8fafc; font-size: 0.70rem; font-weight: 700; padding: 2px 4px; border-radius: 4px; width: 94%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border: 1px solid rgba(255, 255, 255, 0.12); box-shadow: 0 1px 3px rgba(0,0,0,0.25); }}'
        f'.pitch-stat-pill {{ background: rgba(15, 23, 42, 0.85); font-size: 0.66rem; font-weight: 700; padding: 1px 4px; border-radius: 3px; margin-top: 2px; border: 1px solid rgba(255, 255, 255, 0.08); width: 94%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; box-sizing: border-box; }}'
        f'.pitch-dugout {{ background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; margin-top: 8px; padding: 8px 6px 14px 6px; position: relative; z-index: 20; overflow: visible; min-height: 128px !important; height: auto !important; box-sizing: border-box !important; animation: pitchRowIn 250ms cubic-bezier(0.16, 1, 0.3, 1) both; animation-delay: 0.20s; }}'
        f'.pitch-dugout:hover, .pitch-dugout:focus-within {{ z-index: 100 !important; }}'
        f'.bench-node:hover {{ z-index: 150 !important; }}'
        f'.bench-node .player-tooltip-card {{ z-index: 2000 !important; }}'
        f'.dugout-title {{ font-size: 0.7rem; font-weight: 800; color: #94a3b8; letter-spacing: 0.05em; text-align: center; margin-bottom: 6px; }}'
        f'.dugout-row {{ display: flex; justify-content: space-around; align-items: center; }}'
        f'.bench-node {{ flex: 1; max-width: 64px; }}'
        f'.bench-order-tag {{ font-size: 0.65rem; color: #94a3b8; font-weight: 600; margin-bottom: 2px; }}'
        f'@media (prefers-reduced-motion: reduce) {{ .pitch-formation-row, .pitch-dugout, .pitch-cap-badge {{ animation: none !important; }} .pitch-player-node {{ transition: none !important; }} }}'
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
    return full_pitch_html


def _build_pos_neg_options(squad_df: pd.DataFrame, available_market_df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    pos_options = []
    for _, r in squad_df.iterrows():
        first = str(r.get("first_name", "") or "")
        second = str(r.get("second_name", "") or "")
        pos_options.append({
            "id": f"lock_{r['id']}",
            "label": f"🔒 Keep: {r['Player']} ({r['Team']} · {r['Pos']})",
            "label": f"Lock: {r['Player']} ({r['Team']} · {r['Pos']})",
            "name": str(r["Player"]),
            "type": "lock",
            "search_text": f"{r['Player']} {first} {second} {r['Team']} {r['Pos']}".lower(),
            "team": str(r["Team"]),
            "pos": str(r["Pos"]),
            "cost": float(r["Cost"]),
            "xp": float(r.get("Horizon_xP", 0.0)),
        })
    for _, r in available_market_df.iterrows():
        first = str(r.get("first_name", "") or "")
        second = str(r.get("second_name", "") or "")
        pos_options.append({
            "id": f"target_{r['id']}",
            "label": f"🎯 Target: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m · {r.get('Horizon_xP', 0.0):.1f} xP)",
            "label": f"Target: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m · {r.get('Horizon_xP', 0.0):.1f} xP)",
            "name": str(r["Player"]),
            "type": "target",
            "search_text": f"{r['Player']} {first} {second} {r['Team']} {r['Pos']}".lower(),
            "team": str(r["Team"]),
            "pos": str(r["Pos"]),
            "cost": float(r["Cost"]),
            "xp": float(r.get("Horizon_xP", 0.0)),
        })

    neg_options = []
    for _, r in squad_df.iterrows():
        first = str(r.get("first_name", "") or "")
        second = str(r.get("second_name", "") or "")
        neg_options.append({
            "id": f"sell_{r['id']}",
            "label": f"🔴 Sell: {r['Player']} ({r['Team']} · {r['Pos']})",
            "label": f"Sell: {r['Player']} ({r['Team']} · {r['Pos']})",
            "name": str(r["Player"]),
            "type": "sell",
            "search_text": f"{r['Player']} {first} {second} {r['Team']} {r['Pos']}".lower(),
            "team": str(r["Team"]),
            "pos": str(r["Pos"]),
            "cost": float(r["Cost"]),
            "xp": float(r.get("Horizon_xP", 0.0)),
        })
    for _, r in available_market_df.iterrows():
        first = str(r.get("first_name", "") or "")
        second = str(r.get("second_name", "") or "")
        neg_options.append({
            "id": f"block_{r['id']}",
            "label": f"⛔ Blacklist: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m)",
            "label": f"Block: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m)",
            "name": str(r["Player"]),
            "type": "block",
            "search_text": f"{r['Player']} {first} {second} {r['Team']} {r['Pos']}".lower(),
            "team": str(r["Team"]),
            "pos": str(r["Pos"]),
            "cost": float(r["Cost"]),
            "xp": float(r.get("Horizon_xP", 0.0)),
        })
    return pos_options, neg_options


@ttl_cache(ttl_seconds=300)
def fetch_transfer_planner_data(manager_id: str, current_gw: int, horizon: int = 5, betting: bool = True, weight: float = 0.35, mins: int = 45):
    try:
        from fpl_strategic_dashboard_reflex.services.db import (
            get_connection,
            get_global_gameweek_info,
            solve_optimal_xi,
        )
        from fpl_strategic_dashboard_reflex.services.squad import (
            fetch_manager_entry,
            fetch_manager_history,
            fetch_manager_picks,
        )

        conn = get_connection()
        events_df, next_gw, _ = get_global_gameweek_info(conn)

        mgr_data = fetch_manager_entry(manager_id)
        if not mgr_data:
            return None
        mgr_history = fetch_manager_history(manager_id)
        calc_ft = calculate_available_fts(mgr_history)

        finished_gw_ids = [int(r["id"]) for _, r in events_df[events_df["finished"] == 1].iterrows()] if "finished" in events_df.columns else []
        ongoing_gw_ids = [int(r["id"]) for _, r in events_df.iterrows() if int(r["id"]) not in finished_gw_ids and int(r["id"]) < next_gw]
        ongoing_gw = ongoing_gw_ids[0] if ongoing_gw_ids else None
        last_finished_gw = max(finished_gw_ids) if finished_gw_ids else None

        active_calc_gw = ongoing_gw if ongoing_gw else (last_finished_gw or next_gw)
        picks_data = fetch_manager_picks(manager_id, active_calc_gw, next_gw)

        entry_history = picks_data.get("entry_history", {})
        bank_balance = entry_history.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
        picks_list = picks_data.get("picks", [])
        pick_ids = [p["element"] for p in picks_list]

        if not pick_ids:
            return None

        placeholders = ",".join(["?"] * len(pick_ids))
        squad_query = f"""
        SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
               p.first_name, p.second_name, p.can_select,
               t.short_name AS Team,
               CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
               p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
               p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
               p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
               p.expected_goal_involvements_per_90 AS xGI_per_90
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        WHERE p.id IN ({placeholders})
        """
        squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
        squad_sell = round(float(squad_df["Cost"].sum()), 1)
        team_val = round(squad_sell + bank_balance, 1)

        league_eval_df = evaluate_league_multi_gw(
            conn, next_gw, horizon,
            enable_betting=betting, market_weight=weight, factor_movement=True
        )

        _is_ui_available = (league_eval_df["can_select"] == 1) & (league_eval_df["Status"] != "u")
        _not_in_squad = ~league_eval_df["id"].isin(pick_ids)

        available_market_df = league_eval_df[
            _not_in_squad & _is_ui_available
        ].sort_values(by="Horizon_xP", ascending=False)

        pos_options, neg_options = _build_pos_neg_options(squad_df, available_market_df)

        curr_squad_horizon = league_eval_df[league_eval_df["id"].isin(pick_ids)].copy()
        curr_squad_horizon["is_transfer_out"] = False
        curr_squad_horizon["is_forced_out"] = False
        curr_squad_horizon["is_transfer_in"] = False
        curr_squad_horizon["is_target_in"] = False

        raw_base_xi, raw_base_bench, _ = solve_optimal_xi(curr_squad_horizon)
        base_xi, base_bench = prepare_xi_display(raw_base_xi, raw_base_bench)
        base_xi["tooltip_html"] = base_xi.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        base_bench["tooltip_html"] = base_bench.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        base_pitch_html = render_transfer_pitch_component(base_xi, base_bench)

        base_xp = round(
            float(
                (base_xi["Horizon_xP"] * base_xi["Multiplier"]).sum()
                + 0.10 * (base_bench["Horizon_xP"].sum() if not base_bench.empty else 0)
            ),
            1,
        )

        # Enrich for list view
        enriched_base_xi = enrich_transfer_squad_for_list_view(base_xi, horizon_len=horizon)
        enriched_base_bench = enrich_transfer_squad_for_list_view(base_bench, horizon_len=horizon)

        return {
            "next_gw": int(next_gw),
            "calc_ft": int(calc_ft),
            "bank_balance": bank_balance,
            "squad_sell": squad_sell,
            "team_val": team_val,
            "pos_options": pos_options,
            "neg_options": neg_options,
            "base_starters": enriched_base_xi.fillna("").to_dict("records"),
            "base_bench": enriched_base_bench.fillna("").to_dict("records"),
            "base_pitch_html": base_pitch_html,
            "base_xp": base_xp,
        }
    except Exception as e:
        print(f"fetch_transfer_planner_data error: {e}")
        return None


def analyze_transfers(
    manager_id, current_gw, horizon, ft, hits, betting, weight, mins, pos_sel, neg_sel, chip_mode="Regular Transfers"
):
    try:
        from fpl_strategic_dashboard_reflex.services.db import (
            get_connection,
            get_global_gameweek_info,
            solve_optimal_xi,
        )
        from fpl_strategic_dashboard_reflex.services.squad import (
            fetch_manager_entry,
            fetch_manager_history,
            fetch_manager_picks,
        )

        conn = get_connection()
        events_df, next_gw, _ = get_global_gameweek_info(conn)

        mgr_data = fetch_manager_entry(manager_id)
        if not mgr_data:
            return None
        mgr_history = fetch_manager_history(manager_id)

        calc_ft = calculate_available_fts(mgr_history)

        finished_gw_ids = [int(r["id"]) for _, r in events_df[events_df["finished"] == 1].iterrows()] if "finished" in events_df.columns else []
        ongoing_gw_ids = [int(r["id"]) for _, r in events_df.iterrows() if int(r["id"]) not in finished_gw_ids and int(r["id"]) < next_gw]
        ongoing_gw = ongoing_gw_ids[0] if ongoing_gw_ids else None
        last_finished_gw = max(finished_gw_ids) if finished_gw_ids else None

        active_calc_gw = ongoing_gw if ongoing_gw else (last_finished_gw or next_gw)
        picks_data = fetch_manager_picks(manager_id, active_calc_gw, next_gw)

        entry_history = picks_data.get("entry_history", {})
        bank_balance = entry_history.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
        picks_list = picks_data.get("picks", [])
        pick_ids = [p["element"] for p in picks_list]

        if not pick_ids:
            return None

        placeholders = ",".join(["?"] * len(pick_ids))
        squad_query = f"""
        SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
               p.first_name, p.second_name, p.can_select,
               t.short_name AS Team,
               CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
               p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
               p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
               p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
               p.expected_goal_involvements_per_90 AS xGI_per_90
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        WHERE p.id IN ({placeholders})
        """
        squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
        squad_sell = round(float(squad_df["Cost"].sum()), 1)
        team_val = round(squad_sell + bank_balance, 1)

        actual_horizon = 1 if chip_mode == "Free Hit" else horizon
        league_eval_df = evaluate_league_multi_gw(
            conn, next_gw, actual_horizon,
            enable_betting=betting, market_weight=weight, factor_movement=True
        )

        _is_ui_available = (league_eval_df["can_select"] == 1) & (league_eval_df["Status"] != "u")
        _not_in_squad = ~league_eval_df["id"].isin(pick_ids)

        available_market_df = league_eval_df[
            _not_in_squad & _is_ui_available
        ].sort_values(by="Horizon_xP", ascending=False)

        pos_options, neg_options = _build_pos_neg_options(squad_df, available_market_df)

        def _clean_key(k):
            if isinstance(k, dict):
                return k.get("id", "")
            return str(k).split("::")[0].strip()

        locked_players = [int(_clean_key(k).replace("lock_", "")) for k in (pos_sel or []) if _clean_key(k).startswith("lock_")]
        targeted_in_players = [int(_clean_key(k).replace("target_", "")) for k in (pos_sel or []) if _clean_key(k).startswith("target_")]
        force_out_players = [int(_clean_key(k).replace("sell_", "")) for k in (neg_sel or []) if _clean_key(k).startswith("sell_")]
        blocked_in_players = [int(_clean_key(k).replace("block_", "")) for k in (neg_sel or []) if _clean_key(k).startswith("block_")]

        curr_squad_horizon = league_eval_df[league_eval_df["id"].isin(pick_ids)].copy()

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
            actual_hit_cost = 0
        else:
            total_allowed_transfers = int(ft + hits)
            solver_candidate_df = available_market_df.copy()
            transferred_squad_df, swaps = solve_multi_gw_transfers(
                current_squad_df=curr_squad_horizon,
                candidate_league_df=solver_candidate_df,
                bank=bank_balance,
                num_transfers=total_allowed_transfers,
                locked_player_ids=locked_players,
                target_in_player_ids=targeted_in_players,
                force_out_player_ids=force_out_players,
                blocked_in_player_ids=blocked_in_players,
                min_avg_minutes=mins,
            )
            actual_hit_cost = max(0, len(swaps) - int(ft)) * 4

        out_ids = {s["out"]["id"] for s in swaps}
        in_ids = {s["in"]["id"] for s in swaps}
        forced_out_ids = {s["out"]["id"] for s in swaps if s.get("forced_out")}

        curr_squad_horizon["is_transfer_out"] = curr_squad_horizon["id"].isin(out_ids)
        curr_squad_horizon["is_forced_out"] = curr_squad_horizon["id"].isin(forced_out_ids)
        curr_squad_horizon["is_transfer_in"] = False
        curr_squad_horizon["is_target_in"] = False

        transferred_squad_df["is_transfer_out"] = False
        transferred_squad_df["is_forced_out"] = False
        transferred_squad_df["is_transfer_in"] = transferred_squad_df["id"].isin(in_ids)
        transferred_squad_df["is_target_in"] = transferred_squad_df["id"].isin(targeted_in_players)

        raw_base_xi, raw_base_bench, _ = solve_optimal_xi(curr_squad_horizon)
        raw_trans_xi, raw_trans_bench, _ = solve_optimal_xi(transferred_squad_df)

        base_xi, base_bench = prepare_xi_display(raw_base_xi, raw_base_bench)
        trans_xi, trans_bench = prepare_xi_display(raw_trans_xi, raw_trans_bench)

        base_xi["tooltip_html"] = base_xi.apply(lambda r: build_player_tooltip(r, horizon_len=actual_horizon), axis=1)
        base_bench["tooltip_html"] = base_bench.apply(lambda r: build_player_tooltip(r, horizon_len=actual_horizon), axis=1)
        trans_xi["tooltip_html"] = trans_xi.apply(lambda r: build_player_tooltip(r, horizon_len=actual_horizon), axis=1)
        trans_bench["tooltip_html"] = trans_bench.apply(lambda r: build_player_tooltip(r, horizon_len=actual_horizon), axis=1)

        base_pitch_html = render_transfer_pitch_component(base_xi, base_bench)
        comp_pitch_html = render_transfer_pitch_component(trans_xi, trans_bench)

        base_pts = float(
            (base_xi["Horizon_xP"] * base_xi["Multiplier"]).sum()
            + 0.10 * (base_bench["Horizon_xP"].sum() if not base_bench.empty else 0)
        )
        trans_pts = float(
            (trans_xi["Horizon_xP"] * trans_xi["Multiplier"]).sum()
            + 0.10 * (trans_bench["Horizon_xP"].sum() if not trans_bench.empty else 0)
        )

        safe_swaps = []
        for s in swaps:
            safe_swaps.append({
                "out_name": str(s["out"]["Player"]),
                "in_name": str(s["in"]["Player"]),
                "out_team": str(s["out"].get("Team", "")),
                "in_team": str(s["in"].get("Team", "")),
                "out_cost": float(s["out"].get("Cost", 0.0)),
                "in_cost": float(s["in"].get("Cost", 0.0)),
                "out_xp": float(s["out"].get("Horizon_xP", 0.0)),
                "in_xp": float(s["in"].get("Horizon_xP", 0.0)),
                "gain": float(s.get("gain", 0.0)),
                "cost_diff": float(s.get("cost_diff", 0.0)),
                "forced_out": bool(s.get("forced_out", False)),
                "target": bool(s.get("target", False)),
            })

        net_gain = round((trans_pts - base_pts) - actual_hit_cost, 1)

        # Enrich for list view
        enriched_base_xi = enrich_transfer_squad_for_list_view(base_xi, horizon_len=actual_horizon)
        enriched_base_bench = enrich_transfer_squad_for_list_view(base_bench, horizon_len=actual_horizon)
        enriched_trans_xi = enrich_transfer_squad_for_list_view(trans_xi, horizon_len=actual_horizon)
        enriched_trans_bench = enrich_transfer_squad_for_list_view(trans_bench, horizon_len=actual_horizon)

        return {
            "pos_options": pos_options,
            "neg_options": neg_options,
            "bank_balance": bank_balance,
            "squad_sell": squad_sell,
            "team_val": team_val,
            "swaps": safe_swaps,
            "base_starters": enriched_base_xi.fillna("").to_dict("records"),
            "base_bench": enriched_base_bench.fillna("").to_dict("records"),
            "trans_starters": enriched_trans_xi.fillna("").to_dict("records"),
            "trans_bench": enriched_trans_bench.fillna("").to_dict("records"),
            "base_pitch_html": base_pitch_html,
            "comp_pitch_html": comp_pitch_html,
            "init_ft": calc_ft if ft == 1 else None,
            "metrics": {
                "bank_after": round(bank_balance - sum(float(s["cost_diff"]) for s in safe_swaps), 1),
                "team_value": team_val,
                "squad_sell": squad_sell,
                "old_xp": round(base_pts, 1),
                "new_xp": round(trans_pts, 1),
                "xp_diff": round(trans_pts - base_pts, 1),
                "net_gain": net_gain,
                "hit_cost": actual_hit_cost,
                "moves_count": len(swaps),
                "allowed_moves": 15 if chip_mode != "Regular Transfers" else int(ft + hits),
            },
        }
    except Exception as e:
        print(f"Transfer analyzer backend error: {e}")
        return None


