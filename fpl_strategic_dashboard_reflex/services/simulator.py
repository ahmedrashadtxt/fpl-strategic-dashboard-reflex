"""Monte Carlo match outcome simulator and Head-to-Head engine.
Vectorized simulations using Poisson process goal arrivals and betting lambdas.
Completely decoupled from Streamlit.
"""

import math
import sqlite3
import time
import numpy as np
import pandas as pd

from fpl_strategic_dashboard_reflex.services.cache import ttl_cache
from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    get_manager_squad_ids,
    get_historical_player_baselines,
    calculate_projected_points,
    get_fixture_for_team,
    solve_optimal_xi,
)


def build_odds_map(conn: sqlite3.Connection, target_gw: int, fixtures_df: pd.DataFrame, fdr_map: dict) -> dict:
    """
    Builds a dictionary mapping team_id to fixture expectations (xG, CS Prob).
    Falls back to FDR Poisson baselines if odds data is missing.
    """
    teams_df = pd.read_sql_query("SELECT id, short_name FROM teams", conn)
    short_to_id = dict(zip(teams_df["short_name"], teams_df["id"]))

    odds_query = """
    SELECT home_team, away_team, home_xg, away_xg, home_cs_prob, away_cs_prob 
    FROM fixture_odds_snapshots 
    WHERE event = ?
    ORDER BY recorded_at DESC
    """
    try:
        odds_df = pd.read_sql_query(odds_query, conn, params=(target_gw,))
        odds_df = odds_df.drop_duplicates(subset=["home_team", "away_team"])
    except Exception:
        odds_df = pd.DataFrame()

    odds_lookup = {}
    for _, row in odds_df.iterrows():
        h_id = short_to_id.get(row["home_team"])
        a_id = short_to_id.get(row["away_team"])
        if h_id and a_id:
            odds_lookup[(h_id, a_id)] = row

    gw_fixes = fixtures_df[fixtures_df["GW"] == target_gw] if "GW" in fixtures_df.columns else pd.DataFrame()
    odds_map = {}

    fdr_to_xg = {1: 2.2, 2: 1.8, 3: 1.4, 4: 1.0, 5: 0.7}
    fdr_to_cs = {1: 0.45, 2: 0.35, 3: 0.25, 4: 0.15, 5: 0.05}

    for _, fix in gw_fixes.iterrows():
        home_id = int(fix["team_h_id"])
        away_id = int(fix["team_a_id"])

        h_fdr = fix.get("Home_Diff", 3)
        a_fdr = fix.get("Away_Diff", 3)

        home_xg_fallback = fdr_to_xg.get(a_fdr, 1.4)
        away_xg_fallback = fdr_to_xg.get(h_fdr, 1.2)
        home_cs_fallback = fdr_to_cs.get(a_fdr, 0.25)
        away_cs_fallback = fdr_to_cs.get(h_fdr, 0.20)

        row = odds_lookup.get((home_id, away_id))
        if row is not None:
            home_xg = float(row["home_xg"])
            away_xg = float(row["away_xg"])
            home_cs = float(row["home_cs_prob"])
            away_cs = float(row["away_cs_prob"])
        else:
            home_xg = home_xg_fallback
            away_xg = away_xg_fallback
            home_cs = home_cs_fallback
            away_cs = away_cs_fallback

        odds_map.setdefault(home_id, []).append({
            "opp_team": away_id,
            "is_home": True,
            "team_xg": home_xg,
            "opp_xg": away_xg,
            "cs_prob": home_cs,
        })

        odds_map.setdefault(away_id, []).append({
            "opp_team": home_id,
            "is_home": False,
            "team_xg": away_xg,
            "opp_xg": home_xg,
            "cs_prob": away_cs,
        })

    return odds_map


def run_gameweek_simulation(
    squad_df: pd.DataFrame,
    odds_map: dict,
    n_sims: int = 5000,
    captain_id: int = None,
    vc_id: int = None,
    chip: str = None,
) -> tuple:
    """Executes vectorized Monte Carlo simulation for a squad."""
    st_time = time.perf_counter()
    if odds_map is None:
        odds_map = {}
    if squad_df is None:
        return np.array([]), np.array([]), {}
    if isinstance(squad_df, list):
        squad_df = pd.DataFrame(squad_df)
    if squad_df.empty:
        return np.array([]), np.array([]), {}

    players = squad_df.to_dict(orient="records")
    n_players = len(players)
    player_distributions = np.zeros((n_players, n_sims), dtype=np.int32)
    player_stats = []

    involved_teams = []
    for p in players:
        tid = p.get("team_id", p.get("team", 1))
        try:
            involved_teams.append(int(tid))
        except (ValueError, TypeError):
            involved_teams.append(tid)
    involved_teams = list(set(involved_teams))
    team_outcomes = {}

    for t_id in involved_teams:
        fixtures = odds_map.get(t_id, [])
        team_outcomes[t_id] = []
        for fix in fixtures:
            opp_goals = np.random.poisson(lam=max(0.1, fix["opp_xg"]), size=n_sims)
            cs_mask = (opp_goals == 0)
            team_goals = np.random.poisson(lam=max(0.1, fix["team_xg"]), size=n_sims)
            team_outcomes[t_id].append({
                "team_goals": team_goals,
                "opp_goals": opp_goals,
                "cs_mask": cs_mask,
            })
    for idx, p in enumerate(players):
        raw_tid = p.get("team_id", p.get("team", 1))
        try:
            t_id = int(raw_tid)
        except (ValueError, TypeError):
            t_id = raw_tid
        pos = str(p.get("Pos", p.get("position", "MID"))).upper()
        avg_mins = float(p.get("minutes", 60.0) or 60.0)
        xgi_90 = float(p.get("xGI_per_90", p.get("xGI", 0.2)) or 0.2)

        cs_pts = 4 if pos in ["DEF", "GKP"] else (1 if pos == "MID" else 0)
        p_total = np.zeros(n_sims, dtype=np.int32)

        fixtures = team_outcomes.get(t_id, [])
        for fix_data in fixtures:
            team_goals = fix_data["team_goals"]
            opp_goals = fix_data["opp_goals"]
            cs_mask = fix_data["cs_mask"]

            sampled_mins = np.random.normal(loc=avg_mins, scale=15.0, size=n_sims)
            sampled_mins = np.clip(sampled_mins, 0, 90)
            play_mask = np.random.random(n_sims) < max(0.2, (avg_mins / 90.0))
            sampled_mins = np.where(play_mask, sampled_mins, 0)

            app_pts = np.where(sampled_mins >= 60, 2, np.where(sampled_mins > 0, 1, 0))
            p_total += app_pts

            team_xg = max(0.1, odds_map[t_id][0]["team_xg"]) if t_id in odds_map and len(odds_map[t_id]) > 0 else 1.5

            if pos in ["DEF", "GKP"]:
                involvement_rate = np.clip(xgi_90 * 0.25 * (sampled_mins / 90.0), 0.01, 0.12)
            else:
                involvement_rate = np.clip((xgi_90 / max(team_xg, 1.2)) * (sampled_mins / 90.0), 0.03, 0.45)

            returns = np.random.binomial(n=team_goals, p=involvement_rate)

            if pos == "MID":
                goals = np.random.binomial(n=returns, p=0.55)
                assists = returns - goals
                p_total += (goals * 5) + (assists * 3)
            elif pos == "FWD":
                goals = np.random.binomial(n=returns, p=0.70)
                assists = returns - goals
                p_total += (goals * 4) + (assists * 3)
            else:
                goals = np.random.binomial(n=returns, p=0.25)
                assists = returns - goals
                p_total += (goals * 6) + (assists * 3)

            eligible_for_cs = (sampled_mins >= 60) & cs_mask
            if cs_pts > 0:
                p_total += np.where(eligible_for_cs, cs_pts, 0)

            if pos in ["DEF", "GKP"]:
                gc_deduction = np.where(sampled_mins > 0, opp_goals // 2, 0)
                p_total -= gc_deduction

            if pos == "GKP":
                saves = np.random.poisson(lam=3.0 * (sampled_mins / 90.0))
                p_total += (saves // 3)

            bonus_prob = np.where(returns > 0, 0.15 + (returns * 0.1), 0.0)
            bonus_pts = np.random.binomial(n=3, p=np.clip(bonus_prob, 0, 1))
            p_total += bonus_pts

        player_distributions[idx] = p_total
        median_pts = float(np.median(p_total))
        haul_prob = float(np.mean(p_total >= 10)) * 100.0

        player_stats.append({
            "id": int(p.get("id", idx)),
            "web_name": str(p.get("Player", p.get("web_name", f"Player {idx}"))),
            "team": str(p.get("Team", str(t_id))),
            "pos": pos,
            "median": round(median_pts, 1),
            "haul_prob": round(haul_prob, 1),
            "proj_pts": round(float(p.get("Proj_Pts", median_pts)), 1),
        })

    cap_mult = 3 if chip == "TC" else 2
    cap_idx = next((i for i, p in enumerate(players) if p.get("id") == captain_id or p.get("is_cap") is True), 0 if n_players > 0 else -1)
    if cap_idx != -1:
        cap_pts = player_distributions[cap_idx]
        player_distributions[cap_idx] += cap_pts * (cap_mult - 1)
        player_stats[cap_idx]["median"] = round(float(np.median(player_distributions[cap_idx])), 1)

    simulated_totals = np.sum(player_distributions, axis=0)

    stats_dict = {
        "mean": round(float(np.mean(simulated_totals)), 1),
        "median": round(float(np.median(simulated_totals)), 1),
        "p10_floor": round(float(np.percentile(simulated_totals, 10)), 1),
        "p25": round(float(np.percentile(simulated_totals, 25)), 1),
        "p75": round(float(np.percentile(simulated_totals, 75)), 1),
        "p90_ceiling": round(float(np.percentile(simulated_totals, 90)), 1),
        "std_dev": round(float(np.std(simulated_totals)), 1),
        "std": round(float(np.std(simulated_totals)), 1),
        "player_stats": player_stats,
        "exec_time_ms": round((time.perf_counter() - st_time) * 1000.0, 1),
    }

    return simulated_totals, player_distributions, stats_dict


def run_head_to_head_simulation(
    squad_a_df: pd.DataFrame,
    squad_b_df: pd.DataFrame,
    odds_map: dict,
    n_sims: int = 5000,
) -> dict:
    """Runs two squads against the same macro outcomes and returns win probabilities."""
    seed = np.random.randint(0, 100000)
    np.random.seed(seed)
    totals_a, _, _ = run_gameweek_simulation(squad_a_df, odds_map, n_sims)

    np.random.seed(seed)
    totals_b, _, _ = run_gameweek_simulation(squad_b_df, odds_map, n_sims)
    np.random.seed(None)

    wins_a = int(np.sum(totals_a > totals_b))
    wins_b = int(np.sum(totals_b > totals_a))
    draws = int(np.sum(totals_a == totals_b))

    return {
        "win_pct_a": round(float(wins_a / n_sims) * 100.0, 1),
        "win_pct_b": round(float(wins_b / n_sims) * 100.0, 1),
        "draw_pct": round(float(draws / n_sims) * 100.0, 1),
        "median_a": round(float(np.median(totals_a)), 1),
        "median_b": round(float(np.median(totals_b)), 1),
    }
