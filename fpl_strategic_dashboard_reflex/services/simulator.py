"""Monte Carlo match outcome simulator and Head-to-Head engine.
Vectorized simulations using Poisson process goal arrivals and bookmaker odds.
Full parity with reference/simulation_engine.py and reference/simulator.py.
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
    get_teams_fdr_map,
    solve_optimal_xi,
)
from fpl_strategic_dashboard_reflex.services.squad import (
    get_cached_league_eval_df,
    get_cached_league_dream_15,
)
from fpl_strategic_dashboard_reflex.services.audit import get_snapshot


def build_odds_map(conn: sqlite3.Connection, target_gw: int, fixtures_df: pd.DataFrame, fdr_map: dict) -> dict:
    """
    Builds a dictionary mapping team_id to a list of fixture expectations (xG, CS Prob).
    Handles Double Gameweeks additively (a list of fixtures per team).
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
    n_sims: int = 10000,
    captain_id: int = None,
    vc_id: int = None,
    chip: str = None,
) -> tuple:
    """
    Executes a vectorized Monte Carlo simulation for a Gameweek across a Starting 11.
    Returns: (simulated_totals_1d, player_distributions_2d, stats_dict)
    """
    st_time = time.perf_counter()

    if squad_df is None or len(squad_df) == 0:
        return np.array([]), np.array([]), {}
    if isinstance(squad_df, list):
        squad_df = pd.DataFrame(squad_df)
    if odds_map is None:
        odds_map = {}

    players = squad_df.to_dict(orient="records")
    n_players = len(players)
    player_distributions = np.zeros((n_players, n_sims), dtype=np.int32)
    player_stats = []

    involved_teams = []
    for p in players:
        tid = p.get("team_id", p.get("team", p.get("Club", 1)))
        try:
            involved_teams.append(int(tid))
        except (ValueError, TypeError):
            pass
    involved_teams = list(set(involved_teams))
    team_outcomes = {}

    for t_id in involved_teams:
        fixtures = odds_map.get(t_id, [])
        team_outcomes[t_id] = []
        for fix in fixtures:
            opp_goals = np.random.poisson(lam=max(0.1, float(fix["opp_xg"])), size=n_sims)
            cs_mask = (opp_goals == 0)
            team_goals = np.random.poisson(lam=max(0.1, float(fix["team_xg"])), size=n_sims)

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
            t_id = 1
        pos = str(p.get("position", p.get("Pos", "MID"))).upper()

        avg_mins = float(p.get("avg_mins", p.get("minutes", 60.0)) or 60.0)
        chance_val = p.get("chance_of_playing_this_round", p.get("chance_of_playing_next_round", p.get("Chance")))
        if chance_val is not None and pd.notna(chance_val):
            try:
                chance = float(chance_val)
                if chance == 0:
                    avg_mins = 0.0
                else:
                    avg_mins = avg_mins * (chance / 100.0)
            except (ValueError, TypeError):
                pass

        xgi_90 = float(p.get("xGI_per_90", p.get("xGI", p.get("roll_xgi90", 0.0))) or 0.0)
        cs_pts = 4 if pos in ["DEF", "GKP"] else (1 if pos == "MID" else 0)

        p_total = np.zeros(n_sims, dtype=np.int32)

        fixtures = team_outcomes.get(t_id, [])
        for fix_data in fixtures:
            team_goals = fix_data["team_goals"]
            opp_goals = fix_data["opp_goals"]
            cs_mask = fix_data["cs_mask"]

            sampled_mins = np.random.normal(loc=avg_mins, scale=20.0, size=n_sims)
            sampled_mins = np.clip(sampled_mins, 0, 90)

            play_mask = np.random.random(n_sims) < (avg_mins / 90.0 if avg_mins > 0 else 0.0)
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

            yc = np.random.binomial(n=1, p=(0.1 * (sampled_mins / 90.0)))
            p_total -= yc

        player_distributions[idx] = p_total

        median_pts = float(np.median(p_total))
        haul_prob = float(np.mean(p_total >= 10)) * 100.0

        if pos in ["DEF", "GKP", "MID"] and len(fixtures) > 0:
            cs_achieved = np.where((sampled_mins >= 60) & cs_mask, True, False)
            cs_prob_display = float(np.mean(cs_achieved)) * 100.0
        else:
            cs_prob_display = 0.0

        player_stats.append({
            "id": int(p.get("id", p.get("Element", idx))),
            "web_name": str(p.get("Player", p.get("web_name", f"Player {idx}"))),
            "team": str(p.get("Club", p.get("Team", str(t_id)))),
            "pos": pos,
            "proj_pts": round(float(p.get("Proj_Pts", median_pts)), 1),
            "median": round(float(median_pts), 1),
            "haul_prob": round(float(haul_prob), 1),
            "cs_prob": round(float(cs_prob_display), 1),
            "photo": p.get("photo"),
        })

    cap_mult = 3 if chip == "TC" else 2
    cap_idx = next((i for i, p in enumerate(players) if p.get("id", p.get("Element")) == captain_id), -1)
    vc_idx = next((i for i, p in enumerate(players) if p.get("id", p.get("Element")) == vc_id), -1)

    if cap_idx != -1:
        cap_pts = player_distributions[cap_idx]
        cap_played = cap_pts > 0
        extra_cap_pts = cap_pts * (cap_mult - 1)

        if vc_idx != -1:
            vc_pts = player_distributions[vc_idx]
            extra_vc_pts = vc_pts * (cap_mult - 1)
            player_distributions[cap_idx] += np.where(cap_played, extra_cap_pts, 0)
            player_distributions[vc_idx] += np.where(~cap_played, extra_vc_pts, 0)
        else:
            player_distributions[cap_idx] += np.where(cap_played, extra_cap_pts, 0)

        # Recompute medians and haul prob for captain/vc
        if cap_idx != -1:
            player_stats[cap_idx]["median"] = round(float(np.median(player_distributions[cap_idx])), 1)
            player_stats[cap_idx]["haul_prob"] = round(float(np.mean(player_distributions[cap_idx] >= 10)) * 100.0, 1)
        if vc_idx != -1:
            player_stats[vc_idx]["median"] = round(float(np.median(player_distributions[vc_idx])), 1)
            player_stats[vc_idx]["haul_prob"] = round(float(np.mean(player_distributions[vc_idx] >= 10)) * 100.0, 1)

    simulated_totals = np.sum(player_distributions, axis=0)

    counts, bin_edges = np.histogram(simulated_totals, bins=25)
    hist_data = []
    for i in range(len(counts)):
        bin_center = str(int(round((bin_edges[i] + bin_edges[i + 1]) / 2.0)))
        hist_data.append({
            "points": bin_center,
            "simulations": int(counts[i]),
        })

    stats_dict = {
        "mean": round(float(np.mean(simulated_totals)), 1),
        "median": round(float(np.median(simulated_totals)), 1),
        "p10_floor": round(float(np.percentile(simulated_totals, 10)), 1),
        "p25": round(float(np.percentile(simulated_totals, 25)), 1),
        "p75": round(float(np.percentile(simulated_totals, 75)), 1),
        "p90_ceiling": round(float(np.percentile(simulated_totals, 90)), 1),
        "std_dev": round(float(np.std(simulated_totals)), 1),
        "player_stats": player_stats,
        "hist_data": hist_data,
        "exec_time_ms": round((time.perf_counter() - st_time) * 1000.0, 1),
    }

    return simulated_totals, player_distributions, stats_dict


def run_head_to_head_simulation(
    squad_a_df: pd.DataFrame,
    squad_b_df: pd.DataFrame,
    odds_map: dict,
    n_sims: int = 10000,
    cap_a=None,
    vc_a=None,
    cap_b=None,
    vc_b=None,
) -> dict:
    """
    Runs two squads against the same macro outcomes and returns direct win probabilities.
    """
    seed = np.random.randint(0, 100000)

    np.random.seed(seed)
    totals_a, _, _ = run_gameweek_simulation(squad_a_df, odds_map, n_sims, cap_a, vc_a)

    np.random.seed(seed)
    totals_b, _, _ = run_gameweek_simulation(squad_b_df, odds_map, n_sims, cap_b, vc_b)

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
        "delta_dist": totals_a - totals_b,
    }


def load_active_squad(conn: sqlite3.Connection, manager_id: str, target_gw: int) -> pd.DataFrame:
    """Fetches manager's current squad for the given gameweek."""
    if not manager_id:
        return pd.DataFrame()
    squad_ids = get_manager_squad_ids(manager_id, target_gw)
    if not squad_ids:
        return pd.DataFrame()

    placeholders = ",".join(["?"] * len(squad_ids))
    players_query = f"""
    SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
           t.short_name AS Club,
           CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
           p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
           p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
           p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
           p.expected_goal_involvements_per_90 AS xGI_per_90
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    WHERE p.id IN ({placeholders})
    """
    return pd.read_sql_query(players_query, conn, params=squad_ids)


def load_post_transfer_squad(
    conn: sqlite3.Connection, manager_id: str, target_gw: int, state_trans_squad: list = None
) -> pd.DataFrame:
    """Loads post-transfer plan from state if present, else from saved audit snapshot."""
    raw_list = []
    if state_trans_squad and len(state_trans_squad) > 0:
        raw_list = state_trans_squad
    else:
        snap = get_snapshot(conn, target_gw)
        if snap and "squad" in snap:
            snap_squad = snap["squad"]
            if isinstance(snap_squad, list) and len(snap_squad) > 0:
                raw_list = snap_squad

    if not raw_list:
        return pd.DataFrame()

    p_ids = [int(p["id"]) for p in raw_list if isinstance(p, dict) and "id" in p and p["id"]]
    if p_ids:
        placeholders = ",".join(["?"] * len(p_ids))
        players_query = f"""
        SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
               t.short_name AS Club,
               CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
               p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
               p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
               p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News,
               p.expected_goal_involvements_per_90 AS xGI_per_90
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        WHERE p.id IN ({placeholders})
        """
        try:
            df = pd.read_sql_query(players_query, conn, params=p_ids)
            if not df.empty:
                return df
        except Exception:
            pass

    return pd.DataFrame(raw_list)


def evaluate_squad_for_gw(
    conn: sqlite3.Connection,
    squad_df: pd.DataFrame,
    target_gw: int,
    fixtures_df: pd.DataFrame,
    odds_map: dict,
    hist_df: pd.DataFrame = None,
) -> tuple[pd.DataFrame, pd.DataFrame, int | None, int | None]:
    """
    Evaluates squad players for the target gameweek, solves the optimal Starting XI,
    and identifies Captain and Vice-Captain.
    Returns: (opt_xi, opt_bench, captain_id, vc_id)
    """
    if squad_df is None or squad_df.empty:
        return pd.DataFrame(), pd.DataFrame(), None, None

    teams_df = pd.read_sql_query("SELECT id, short_name FROM teams", conn)
    team_id_to_name = dict(zip(teams_df["id"], teams_df["short_name"]))
    team_name_to_id = dict(zip(teams_df["short_name"], teams_df["id"]))

    if hist_df is None:
        hist_df = get_historical_player_baselines(conn)

    squad_evaluated = []
    for _, p_row in squad_df.iterrows():
        p_dict = p_row.to_dict()
        team_val = p_dict.get("team_id", p_dict.get("team", p_dict.get("Club", p_dict.get("Team"))))
        if isinstance(team_val, str) and not str(team_val).isdigit():
            team_id = team_name_to_id.get(team_val, 1)
        else:
            try:
                team_id = int(team_val) if team_val is not None else 1
            except (ValueError, TypeError):
                team_id = 1
        p_dict["team"] = team_id

        et = p_dict.get("element_type", 3)
        if "Pos" in p_dict and isinstance(p_dict["Pos"], str):
            pass
        elif et == 1:
            p_dict["Pos"] = "GKP"
        elif et == 2:
            p_dict["Pos"] = "DEF"
        elif et == 4:
            p_dict["Pos"] = "FWD"
        else:
            p_dict["Pos"] = "MID"

        if "Proj_Pts" in p_dict and pd.notna(p_dict["Proj_Pts"]) and float(p_dict["Proj_Pts"]) > 0:
            pts = float(p_dict["Proj_Pts"])
        else:
            fix_info = get_fixture_for_team(fixtures_df, team_id, target_gw)
            team_odds = odds_map.get(team_id, [])
            if team_odds:
                fix_info["team_xg"] = team_odds[0]["team_xg"]
                fix_info["opp_xg"] = team_odds[0]["opp_xg"]
                fix_info["cs_prob"] = team_odds[0]["cs_prob"]
            pts = calculate_projected_points(p_dict, fix_info, target_gw, hist_df)

        photo_val = p_dict.get("photo")
        if pd.notna(photo_val) and str(photo_val).strip() != "" and "Photo-Missing" not in str(photo_val):
            photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(photo_val).replace('.jpg', '.png')}"
        else:
            photo_url = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"

        squad_evaluated.append({
            "id": p_dict.get("id", p_dict.get("element_id")),
            "photo": photo_url,
            "code": p_dict.get("code"),
            "Player": p_dict.get("web_name", p_dict.get("Player", "")),
            "Club": team_id_to_name.get(team_id, str(team_id)),
            "Pos": p_dict["Pos"],
            "Proj_Pts": pts,
            "Cost": float(p_dict.get("now_cost", p_dict.get("Cost", 50.0))) / 10.0
            if p_dict.get("now_cost")
            else float(p_dict.get("Cost", 5.0)),
            "team": team_id,
            "team_id": team_id,
            "minutes": p_dict.get("minutes", 0),
            "xGI_per_90": float(
                p_dict.get("expected_goal_involvements_per_90", p_dict.get("xGI_per_90", p_dict.get("roll_xgi90", 0.0)))
                or 0.0
            ),
            "chance_of_playing_this_round": p_dict.get(
                "chance_of_playing_this_round", p_dict.get("chance_of_playing_next_round", p_dict.get("Chance", 100.0))
            ),
        })

    squad_eval_df = pd.DataFrame(squad_evaluated)

    try:
        opt_xi, opt_bench, _ = solve_optimal_xi(squad_eval_df)
    except Exception:
        opt_xi = squad_eval_df.head(11)
        opt_bench = squad_eval_df.tail(len(squad_eval_df) - 11)

    captain_id = None
    vc_id = None
    if len(opt_xi) > 0:
        top_players = opt_xi.sort_values("Proj_Pts", ascending=False)
        captain_id = int(top_players.iloc[0]["id"])
        if len(top_players) > 1:
            vc_id = int(top_players.iloc[1]["id"])

    return opt_xi, opt_bench, captain_id, vc_id


def generate_random_15(pool_df: pd.DataFrame) -> list[int]:
    """Generates a valid random 15-player squad within £100m budget and <=3 per club."""
    p_df = pool_df.copy()
    p_df["weight"] = p_df["Proj_Pts"].clip(lower=1.0) + (p_df["Cost"] * 0.5)
    for _ in range(1000):
        try:
            sq = pd.concat([
                p_df[p_df["Pos"] == "GKP"].sample(n=2, weights="weight"),
                p_df[p_df["Pos"] == "DEF"].sample(n=5, weights="weight"),
                p_df[p_df["Pos"] == "MID"].sample(n=5, weights="weight"),
                p_df[p_df["Pos"] == "FWD"].sample(n=3, weights="weight"),
            ])
            if sq["Cost"].sum() <= 100.0 and sq["Team"].value_counts().max() <= 3:
                return sq["id"].tolist()
        except Exception:
            continue
    return []
