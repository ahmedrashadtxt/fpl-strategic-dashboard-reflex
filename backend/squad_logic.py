import html
import math
import os
import pandas as pd
import requests

try:
    from backend.audit_db import save_pre_gw_snapshot, get_snapshot
except ImportError:
    pass

from backend.betting_engine import (
    load_db_market_odds,
    get_fixture_market_xg_and_movement,
    sync_fixture_odds_with_cooldown,
)
from backend.data import (
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

LIVE_EVENT_CONFIG = {
    "minutes": ("Minutes Played", ""),
    "goals_scored": ("Goals Scored", "⚽"),
    "assists": ("Assists", "🅰️"),
    "clean_sheets": ("Clean Sheet", "🧤"),
    "goals_conceded": ("Goals Conceded", "🥅"),
    "saves": ("Saves Made", "🧤"),
    "bonus": ("Bonus Points", "⭐"),
    "yellow_cards": ("Yellow Card", "🟨"),
    "red_cards": ("Red Card", "🟥"),
    "own_goals": ("Own Goal", "⚠️"),
    "penalties_saved": ("Penalty Saved", "🧤"),
    "penalties_missed": ("Penalty Missed", "❌"),
}


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


def extract_itemized_breakdown(live_stats: dict) -> str:
    if not isinstance(live_stats, dict):
        return "Did not play"

    explain_list = live_stats.get("explain", [])
    event_tokens = []

    if explain_list:
        for fix_entry in explain_list:
            for s in fix_entry.get("stats", []):
                pts = s.get("points", 0)
                val = s.get("value", 0)
                ident = s.get("identifier", "")

                if pts == 0 and ident != "minutes":
                    continue

                label, icon = LIVE_EVENT_CONFIG.get(ident, (ident.replace("_", " ").title(), ""))
                sign = f"+{pts}" if pts > 0 else f"{pts}"
                color = "#4ade80" if pts > 0 else ("#f87171" if pts < 0 else "#94a3b8")

                if ident == "minutes":
                    token = f"{val}' (<span style='color:{color}; font-weight:700;'>{sign}</span>)"
                elif ident in ("goals_scored", "assists", "saves") and val > 1:
                    token = f"{icon} {val} {label} (<span style='color:{color}; font-weight:700;'>{sign}</span>)"
                else:
                    prefix = f"{icon} " if icon else ""
                    token = f"{prefix}{label} (<span style='color:{color}; font-weight:700;'>{sign}</span>)"

                event_tokens.append(token)

    if not event_tokens:
        mins = live_stats.get("minutes", 0)
        return "Did not play (0')" if mins == 0 else "No scoring events"

    return " · ".join(event_tokens)


def build_player_tooltip(p: pd.Series, is_live: bool = False) -> str:
    player_name = html.escape(str(p.get("Player", "")))
    pos = html.escape(str(p.get("Pos", "")))
    team = html.escape(str(p.get("Team", "")))
    cost = p.get("Cost", 0.0)
    cost_str = f"£{fmt_num(cost, '.1f')}m" if cost else "—"

    if is_live:
        raw_pts = int(p.get("Raw_GW_Pts", 0))
        mult = int(round(float(p.get("Multiplier", 1)))) if pd.notna(p.get("Multiplier")) else 1
        live_data = p.get("live_stats", {})
        if not isinstance(live_data, dict):
            live_data = {}

        bps = live_data.get("bps", 0)
        explain_list = live_data.get("explain", [])

        point_rows = []
        if explain_list:
            for fix_entry in explain_list:
                for s in fix_entry.get("stats", []):
                    pts = s.get("points", 0)
                    val = s.get("value", 0)
                    ident = s.get("identifier", "")

                    if pts == 0 and ident != "minutes":
                        continue

                    label, icon = LIVE_EVENT_CONFIG.get(ident, (ident.replace("_", " ").title(), ""))
                    if ident == "minutes":
                        detail = f" ({val}')"
                    elif ident in ("goals_scored", "assists", "saves") and val > 1:
                        detail = f" ({val})"
                    else:
                        detail = ""

                    sign = f"+{pts}" if pts > 0 else f"{pts}"
                    color = "#4ade80" if pts > 0 else ("#f87171" if pts < 0 else "#94a3b8")

                    prefix = f"{icon} " if icon else ""
                    point_rows.append(
                        f'<div class="tt-row">'
                        f'<span class="tt-label">{prefix}{label}{detail}</span>'
                        f'<span class="tt-val" style="color:{color};">{sign} pts</span>'
                        f'</div>'
                    )

        if not point_rows:
            mins = live_data.get("minutes", 0)
            if mins == 0:
                point_rows.append(
                    '<div class="tt-row"><span class="tt-label">Status:</span><span class="tt-val" style="color:#94a3b8;">Did not play</span></div>'
                )
            else:
                point_rows.append(
                    f'<div class="tt-row"><span class="tt-label">Total Points:</span><span class="tt-val">{raw_pts} pts</span></div>'
                )

        bps_row = f'<div class="tt-row" style="font-size:0.64rem; color:#64748b; margin-top:3px;"><span>Provisional BPS:</span><span>{bps}</span></div>'

        multiplier_html = ""
        if mult > 1:
            multiplier_html = (
                f'<div class="tt-row" style="border-top: 1px dashed rgba(255,255,255,0.12); margin-top: 4px; padding-top: 4px;">'
                f'<span class="tt-label" style="color:#facc15; font-weight:700;">Cap Multiplier ({mult}x):</span>'
                f'<span class="tt-val" style="color:#facc15; font-weight:800;">{raw_pts * mult} pts</span>'
                f'</div>'
            )

        status = str(p.get("Status", "a"))
        news = str(p.get("News", ""))
        news_row = ""
        if status != "a" and news and news != "None":
            clean_news = html.escape(news[:40] + ("..." if len(news) > 40 else ""))
            news_row = f'<div class="tt-row tt-news"><span>⚠️ {clean_news}</span></div>'

        return (
            f'<div class="player-tooltip-card" style="width: 200px;">'
            f'<div class="tt-header">'
            f'<div style="display:flex; justify-content:space-between; align-items:baseline;">'
            f'<span class="tt-name">{player_name}</span>'
            f'<span style="color:#4ade80; font-weight:800; font-size:0.85rem;">{raw_pts * mult} pts</span>'
            f'</div>'
            f'<span class="tt-badge">{team} · {pos} · {cost_str}</span>'
            f'</div>'
            f'<div class="tt-body">'
            f'{"".join(point_rows)}'
            f'{multiplier_html}'
            f'{bps_row}'
            f'{news_row}'
            f'</div></div>'
        )

    else:
        proj = fmt_num(p.get("Proj_Pts", 0.0), ".1f")
        opp = html.escape(str(p.get("Opponent", "—")))
        roll_pts = fmt_num(p.get("roll_pts", 0.0), ".1f")
        roll_xgi90 = fmt_num(p.get("roll_xgi90", 0.0), ".2f")
        roll_mins = int(p.get("roll_mins", 0))
        fdr5 = int(p.get("fdr5", 15))
        fdr5_cls = "tt-fdr-easy" if fdr5 <= 11 else ("tt-fdr-med" if fdr5 <= 14 else "tt-fdr-hard")

        form = fmt_num(p.get("Form", 0.0), ".1f")
        ppg = fmt_num(p.get("PPG", 0.0), ".1f")

        status = str(p.get("Status", "a"))
        news = str(p.get("News", ""))
        news_row = ""
        if status != "a" and news and news != "None":
            clean_news = html.escape(news[:40] + ("..." if len(news) > 40 else ""))
            news_row = f'<div class="tt-row tt-news"><span>⚠️ {clean_news}</span></div>'

        return (
            f'<div class="player-tooltip-card">'
            f'<div class="tt-header">'
            f'<span class="tt-name">{player_name}</span>'
            f'<span class="tt-badge">{team} · {pos} · {cost_str}</span>'
            f'</div>'
            f'<div class="tt-body">'
            f'<div class="tt-row"><span class="tt-label">Fixture:</span><span class="tt-val">{opp}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Projected xP:</span><span class="tt-val" style="color:#60a5fa;">{proj} xP</span></div>'
            f'<div class="tt-row"><span class="tt-label">Avg Pts (L5):</span><span class="tt-val">{roll_pts}</span></div>'
            f'<div class="tt-row"><span class="tt-label">xGI / 90 (L5):</span><span class="tt-val">{roll_xgi90}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Avg Mins (L5):</span><span class="tt-val">{roll_mins}m</span></div>'
            f'<div class="tt-row"><span class="tt-label">Next 5 FDR:</span><span class="tt-val {fdr5_cls}">{fdr5}</span></div>'
            f'<div class="tt-row"><span class="tt-label">Form / PPG:</span><span class="tt-val">{form} / {ppg}</span></div>'
            f'{news_row}'
            f'</div></div>'
        )


def fetch_manager_entry(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


def fetch_manager_history(manager_id: str):
    try:
        url = f"https://fantasy.premierleague.com/api/entry/{manager_id}/history/"
        res = requests.get(url, timeout=10)
        return res.json() if res.status_code == 200 else {}
    except Exception:
        return {}


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


def fetch_live_gameweek_points(eval_gw: int):
    try:
        live_url = f"https://fantasy.premierleague.com/api/event/{eval_gw}/live/"
        res = requests.get(live_url, timeout=10)
        if res.status_code == 200:
            return {
                item["id"]: {
                    "points": item["stats"].get("total_points", 0),
                    "bps": item["stats"].get("bps", 0),
                    "minutes": item["stats"].get("minutes", 0),
                    "stats": item.get("stats", {}),
                    "explain": item.get("explain", []),
                }
                for item in res.json().get("elements", [])
            }
        return {}
    except Exception:
        return {}


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
            "manager_name": "Super Team",
            "player_name": "Official Dream Team",
            "total_score": top_pts,
            "picks": picks_list,
        }
    except Exception:
        return None


def fetch_motw_manager_data(target_gw: int):
    motw_id = None
    motw_score = None
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

    if motw_id:
        try:
            mgr_info = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{motw_id}/", timeout=10
            ).json()
            mgr_name = mgr_info.get("name", "Top Manager")
            player_name = (
                f"{mgr_info.get('player_first_name', '')}"
                f" {mgr_info.get('player_last_name', '')}".strip()
            )
            picks_res = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{motw_id}/event/{target_gw}/picks/",
                timeout=10,
            ).json()
            picks_list = picks_res.get("picks", [])
            return {
                "type": "motw",
                "manager_name": mgr_name,
                "player_name": player_name,
                "total_score": (
                    motw_score
                    or picks_res.get("entry_history", {}).get("points", 0)
                ),
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
        print(f"Failed to refresh player prices: {e}")
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

    market_cache = load_db_market_odds(_conn) if enable_betting else {}

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


def build_pitch_html(
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
                sub_color = "#4ade80" if pts >= 6 else "#f8fafc"
                stat_pill_content = f'<span style="color: {sub_color};">{pts_sub}</span>'
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
        f'  min-width: 190px;'
        f'  width: max-content;'
        f'  max-width: 225px;'
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
