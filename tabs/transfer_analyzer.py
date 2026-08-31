import html
import math
import os
import pandas as pd
import requests
import streamlit as st

from betting_engine import (
    fetch_upcoming_betting_odds,
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

    transfer_badge_row = ""
    if bool(p.get("is_transfer_in") is True):
        transfer_badge_row = '<div class="tt-row" style="color:#34d399; font-weight:700;"><span>🟢 Proposed Sign</span></div>'
    elif bool(p.get("is_transfer_out") is True):
        transfer_badge_row = '<div class="tt-row" style="color:#f87171; font-weight:700;"><span>🔴 Proposed Sale</span></div>'

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
    ft = 1
    for ev in current_season:
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
           p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    WHERE (p.status = 'a' OR p.chance_of_playing_next_round >= 75)
    """
    players_df = pd.read_sql(all_players_query, _conn)
    hist_baselines = get_historical_player_baselines(_conn)
    market_cache = (
        fetch_upcoming_betting_odds(st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", "")))
        if enable_betting
        else {}
    )

    results = []
    for _, p in players_df.iterrows():
        total_horizon_xp = 0.0
        gw_breakdown = {}
        for gw in range(start_gw, end_gw + 1):
            f_data = get_fixture_for_team(fix_df, p["team_id"], gw)
            base_xp = calculate_projected_points(p, f_data, start_gw, hist_baselines)
            if enable_betting and f_data.get("opponent"):
                opp_short = f_data["opponent"].replace(" (H)", "").replace(" (A)", "")
                final_xp, _, _ = apply_market_projection_with_movement(
                    _conn,
                    base_xp,
                    p["Pos"],
                    f_data["fdr"],
                    f_data["is_home"],
                    p["Team"],
                    opp_short,
                    market_weight,
                    factor_movement,
                    market_cache,
                )
            else:
                final_xp = base_xp
            total_horizon_xp += final_xp
            gw_breakdown[f"GW{gw}"] = round(final_xp, 1)

        p_dict = dict(p)
        p_dict["Horizon_xP"] = round(total_horizon_xp, 2)
        p_dict["Proj_Pts"] = round(total_horizon_xp, 2)
        p_dict["Avg_xP"] = round(total_horizon_xp / max(1, horizon_len), 2)
        p_dict.update(gw_breakdown)
        results.append(p_dict)

    return pd.DataFrame(results)


def solve_multi_gw_transfers(
    current_squad_df: pd.DataFrame,
    candidate_league_df: pd.DataFrame,
    bank: float,
    num_transfers: int,
    locked_player_ids: list,
) -> tuple[pd.DataFrame, list[dict]]:
    curr_squad = current_squad_df.copy()
    curr_ids = set(curr_squad["id"].tolist())
    avail_cands = candidate_league_df[~candidate_league_df["id"].isin(curr_ids)].copy()

    filtered_cands = []
    for pos in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = avail_cands[avail_cands["Pos"] == pos]
        filtered_cands.append(pos_df.sort_values(by="Horizon_xP", ascending=False).head(18))
    top_candidates = pd.concat(filtered_cands, ignore_index=True)

    curr_bank = bank
    transfers_made = []
    new_in_ids = set()

    for _ in range(num_transfers):
        base_xi, _, _ = solve_optimal_xi(curr_squad)
        base_xp = base_xi["Proj_Pts"].sum()

        best_gain = 0.0
        best_swap = None
        best_squad = None
        team_counts = curr_squad["team_id"].value_counts().to_dict()

        for _, p_out in curr_squad.iterrows():
            if p_out["id"] in locked_player_ids:
                continue

            pos_cands = top_candidates[top_candidates["Pos"] == p_out["Pos"]]
            for _, p_in in pos_cands.iterrows():
                if p_in["id"] in curr_squad["id"].values:
                    continue
                cost_diff = p_in["Cost"] - p_out["Cost"]
                if cost_diff > curr_bank:
                    continue
                cand_team = p_in["team_id"]
                out_team = p_out["team_id"]
                if cand_team != out_team and team_counts.get(cand_team, 0) >= 3:
                    continue

                temp_squad = curr_squad[curr_squad["id"] != p_out["id"]].copy()
                temp_squad = pd.concat([temp_squad, pd.DataFrame([p_in])], ignore_index=True)
                temp_xi, _, _ = solve_optimal_xi(temp_squad)
                gain = temp_xi["Proj_Pts"].sum() - base_xp

                if gain > best_gain:
                    best_gain = gain
                    best_swap = (p_out, p_in, cost_diff)
                    best_squad = temp_squad

        if best_swap and best_gain > 0.05:
            p_out, p_in, cost_diff = best_swap
            curr_squad = best_squad
            curr_bank -= cost_diff
            new_in_ids.add(p_in["id"])
            transfers_made.append({
                "out": p_out,
                "in": p_in,
                "gain": round(best_gain, 1),
                "cost_diff": round(cost_diff, 1),
            })
        else:
            break

    curr_squad["is_transfer_in"] = curr_squad["id"].map(lambda x: x in new_in_ids)
    return curr_squad, transfers_made


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
            is_out = bool(p.get("is_transfer_out") is True)

            cap_badge = ""
            if is_c:
                cap_badge = '<div class="pitch-cap-badge c">C</div>'
            elif is_v:
                cap_badge = '<div class="pitch-cap-badge vc">V</div>'
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
            if is_in:
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
            is_b_out = bool(b.get("is_transfer_out") is True)

            bench_in_badge = ""
            if is_b_in:
                bench_in_badge = '<div class="pitch-cap-badge" style="background:#10b981; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">IN</div>'
            elif is_b_out:
                bench_in_badge = '<div class="pitch-cap-badge" style="background:#ef4444; color:#ffffff; font-size:0.58rem; width:18px; height:18px;">OUT</div>'

            proj = b.get("Horizon_xP", b.get("Proj_Pts", 0.0))
            b_cost = b.get("Cost", 0.0)
            b_cost_str = f"£{fmt_num(b_cost, '.1f')}m" if b_cost else ""
            b_tag = ""
            if is_b_in:
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
                f'{bench_in_badge}'
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
    section_header(
        "Transfer Planner & Solver",
        "Formulate optimal multi-gameweek transfer routes with custom player locking and budget management",
    )

    mgr_to_use = st.session_state.get("manager_id", "").strip()
    if not mgr_to_use:
        st.info("👆 Enter your FPL ID in the top search bar to load your squad.")
        return

    mgr_data = fetch_transfer_manager_entry(mgr_to_use)
    mgr_history = fetch_transfer_manager_history(mgr_to_use)
    if not mgr_data:
        st.error("Could not fetch FPL manager profile.")
        return

    rolling_metrics_df = get_rolling_player_metrics(conn)
    teams_fdr_map = get_teams_fdr_map(conn, current_gw)

    next_gw_row = events_df[events_df["is_next"] == 1]
    next_gw = int(next_gw_row["id"].values[0]) if not next_gw_row.empty else current_gw

    picks_data = fetch_transfer_manager_picks(mgr_to_use, next_gw)
    entry_hist = picks_data.get("entry_history", {})
    bank_balance = entry_hist.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
    pick_ids = [p["element"] for p in picks_data.get("picks", [])]
    if not pick_ids:
        st.warning("No squad picks retrieved for this manager.")
        return

    calc_ft = calculate_available_fts(mgr_history)

    st.markdown("### ⚙️ Optimization Horizon & Controls")
    c1, c2, c3, c4 = st.columns([1.5, 1.1, 1.1, 1.8])
    with c1:
        horizon_gws = st.selectbox(
            "Evaluation Horizon",
            options=[1, 2, 3, 5],
            format_func=lambda x: f"Next {x} Gameweek{'s' if x > 1 else ''} (GW{next_gw}–GW{next_gw + x - 1})",
            index=1,
        )
    with c2:
        ft_selected = st.number_input("Free Transfers", min_value=0, max_value=5, value=calc_ft, step=1)
    with c3:
        max_hits = st.number_input("Max Hits (-4)", min_value=0, max_value=4, value=0, step=1)
    with c4:
        total_allowed_transfers = int(ft_selected + max_hits)
        st.markdown(
            f"""
            <div style="margin-top: 24px; padding: 6px 12px; background: rgba(30,41,59,0.7); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px;">
                <span style="font-size: 0.78rem; color: #94a3b8;">Planned Moves:</span>
                <strong style="color: #38bdf8;"> {total_allowed_transfers} Transfers</strong> 
                <span style="font-size: 0.75rem; color: #f87171;">(-{max_hits * 4} pts)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_tgl1, col_tgl2, col_tgl3, col_tgl4 = st.columns([1.5, 1.8, 1.6, 1.2])
    with col_tgl1:
        pitch_view = st.toggle("🏟️ **Pitch View**", value=True, key="transfer_pitch_toggle")
    with col_tgl2:
        enable_betting = st.toggle("📊 **Betting Market xG**", value=True, key="transfer_betting_toggle")
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
                help="0.0 = 100% Model | 1.0 = 100% Betting Odds",
            )
    with col_tgl4:
        factor_movement = True
        if enable_betting:
            factor_movement = st.checkbox("⚡ Movement", value=True, key="transfer_factor_movement")

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

    locked_players = st.multiselect(
        "🔒 Lock Key Players (Will NOT be transferred out)",
        options=squad_df["id"].tolist(),
        format_func=lambda pid: f"{squad_df.loc[squad_df['id'] == pid, 'Player'].values[0]} ({squad_df.loc[squad_df['id'] == pid, 'Team'].values[0]})",
        default=[],
    )

    loader = st.empty()
    with loader.container():
        render_optimizer_status(
            title="Solving optimal transfer path...",
            subtext=f"Evaluating multi-gameweek projections across GW{next_gw} to GW{next_gw + horizon_gws - 1}...",
        )
        render_skeleton_cards(count=1)

    league_eval_df = evaluate_league_multi_gw(
        conn,
        next_gw,
        horizon_gws,
        enable_betting=enable_betting,
        market_weight=market_weight,
        factor_movement=factor_movement,
    )
    curr_squad_horizon = league_eval_df[league_eval_df["id"].isin(pick_ids)].copy()

    transferred_squad_df, swaps = solve_multi_gw_transfers(
        current_squad_df=curr_squad_horizon,
        candidate_league_df=league_eval_df,
        bank=bank_balance,
        num_transfers=total_allowed_transfers,
        locked_player_ids=locked_players,
    )

    out_ids = {s["out"]["id"] for s in swaps}
    in_ids = {s["in"]["id"] for s in swaps}

    curr_squad_horizon["is_transfer_out"] = curr_squad_horizon["id"].isin(out_ids)
    curr_squad_horizon["is_transfer_in"] = False

    raw_base_xi, raw_base_bench, base_formation = solve_optimal_xi(curr_squad_horizon)
    raw_trans_xi, raw_trans_bench, trans_formation = solve_optimal_xi(transferred_squad_df)

    base_xi, base_bench = prepare_xi_display(raw_base_xi, raw_base_bench)
    trans_xi, trans_bench = prepare_xi_display(raw_trans_xi, raw_trans_bench)

    base_pts = base_xi["Horizon_xP"].sum()
    trans_pts = trans_xi["Horizon_xP"].sum()
    net_pts_gain = (trans_pts - base_pts) - (max_hits * 4)

    loader.empty()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Starting XI {horizon_gws}-GW xP", f"{trans_pts:.1f} xP", delta=f"{trans_pts - base_pts:+.1f} Raw xP")
    m2.metric(
        "Net Projected Gain",
        f"{net_pts_gain:+.1f} xP",
        delta=f"-{max_hits * 4} Hit Penalty" if max_hits > 0 else "Free Transfers",
    )
    m3.metric("Remaining In Bank", f"£{(bank_balance - sum(s['cost_diff'] for s in swaps)):.1f}m")
    m4.metric("Moves Executed", f"{len(swaps)} of {total_allowed_transfers}")

    st.markdown("### 🔄 Recommended Transfer Moves")
    if not swaps:
        st.success("✅ Your current squad is optimal for this horizon. No transfer yields higher starting points within your budget.")
    else:
        for s in swaps:
            c_out, c_in, c_delta = st.columns([3, 3, 2])
            with c_out:
                st.markdown(
                    f"""
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 8px 12px;">
                        <span style="font-size: 0.72rem; font-weight: 800; color: #f87171;">🔴 TRANSFER OUT</span><br>
                        <strong>{s['out']['Player']}</strong> ({s['out']['Team']}) · £{s['out']['Cost']:.1f}m<br>
                        <span style="font-size: 0.78rem; color: #94a3b8;">{horizon_gws}-GW xP: {s['out']['Horizon_xP']:.1f} xP</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with c_in:
                st.markdown(
                    f"""
                    <div style="background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); border-radius: 8px; padding: 8px 12px;">
                        <span style="font-size: 0.72rem; font-weight: 800; color: #4ade80;">🟢 TRANSFER IN</span><br>
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
                        <span style="font-size: 1.1rem; font-weight: 800; color: #38bdf8;">+{s['gain']:.1f} xP</span>
                        <span style="font-size: 0.72rem; color: #64748b;">Cost: {s['cost_diff']:+.1f}m</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)

    st.markdown("### ⚖️ Squad Visual Comparison (Current vs Transfer)")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown(
            f"""
            <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">👤 Current Squad ({horizon_gws}-GW Run)</span>
                <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({base_formation} · {base_pts:.1f} xP)</span>
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
                if bool(row.get("is_transfer_out") is True):
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

    with col_right:
        st.markdown(
            f"""
            <div style="height: 28px; display: flex; align-items: center; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                <span style="font-size: 0.92rem; font-weight: 700; color: #f8fafc;">🔄 Transfer Squad ({horizon_gws}-GW Run)</span>
                <span style="font-size: 0.80rem; font-weight: 600; color: #94a3b8; margin-left: 6px;">({trans_formation} · {trans_pts:.1f} xP)</span>
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
                if bool(row.get("is_transfer_in") is True):
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

    st.markdown("### 📋 Multi-Gameweek Performance Ledger")
    display_ledger = transferred_squad_df.copy()
    display_ledger["Role"] = display_ledger["id"].map(
        lambda x: "New Signing" if x in in_ids else ("Locked" if x in locked_players else "Retained")
    )

    gw_cols = [f"GW{g}" for g in range(next_gw, next_gw + horizon_gws)]
    cols_to_show = ["Role", "Player", "Team", "Pos", "Cost", "Horizon_xP", "Avg_xP"] + gw_cols
    cols_to_show = [c for c in cols_to_show if c in display_ledger.columns]

    st.dataframe(
        display_ledger[cols_to_show].sort_values(by="Horizon_xP", ascending=False),
        hide_index=True,
        use_container_width=True,
    )