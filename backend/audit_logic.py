from backend.squad_logic import get_player_img_url, fmt_num, SILHOUETTE_BASE64, fetch_manager_entry, fetch_manager_picks, get_rolling_player_metrics
from backend.data import get_manager_squad_ids, calculate_projected_points, get_fixture_for_team, get_historical_player_baselines, get_teams_fdr_map, solve_optimal_xi
import pandas as pd
import requests
import json
from datetime import datetime

# ── Local Imports ─────────────────────────────────────────────────────────────
from backend.data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)


try:
    from audit_db import (
        init_audit_tables,
        save_pre_gw_snapshot,
        settle_post_gw_snapshot,
        get_snapshot,
        get_all_gw_versions,
    )
except (ImportError, ModuleNotFoundError):
    from .audit_db import (
        init_audit_tables,
        save_pre_gw_snapshot,
        settle_post_gw_snapshot,
        get_snapshot,
        get_all_gw_versions,
    )

POS_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# ── Solver Helper ─────────────────────────────────────────────────────────────
def compute_active_solver_squad(conn, manager_id: str, target_gw: int, current_gw: int):
    picks_data = fetch_manager_picks(manager_id, target_gw, current_gw)
    picks_list = picks_data.get("picks", [])
    if not picks_list:
        return None, "No squad picks found for this FPL ID."

    pick_ids = [p["element"] for p in picks_list]
    placeholders = ",".join(["?"] * len(pick_ids))

    squad_query = f"""
    SELECT
        p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
        t.short_name AS Team,
        CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
        p.element_type, pos.singular_name AS Position, p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
        p.total_points AS Season_Points, p.expected_goals, p.expected_assists,
        p.form AS Form, p.points_per_game AS PPG, p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.news AS News, p.status AS Status, p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE p.id IN ({placeholders})
    """
    squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
    if squad_df.empty:
        return None, "Failed to load player data from database."

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
    adv_fix_df = pd.read_sql(adv_fixtures_query, conn, params=[current_gw, max(19, target_gw)])
    hist_baselines_df = get_historical_player_baselines(conn)

    squad_eval_list = []
    for _, p_row in squad_df.iterrows():
        fix_data = get_fixture_for_team(adv_fix_df, p_row["team_id"], target_gw)
        proj_pts = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)

        p_eval = dict(p_row)
        p_eval.update({
            "Opponent": fix_data.get("opponent", "—"),
            "FDR": fix_data.get("fdr", 3),
            "Proj_Pts": round(proj_pts, 2),
            "predicted_xp": round(proj_pts, 2),
            "web_name": p_row["Player"],
            "Player": p_row["Player"],
            "Pos": p_row["Pos"],
        })
        squad_eval_list.append(p_eval)

    eval_df = pd.DataFrame(squad_eval_list)
    optimal_xi, optimal_bench, formation = solve_optimal_xi(eval_df)

    optimal_xi = optimal_xi.sort_values("Proj_Pts", ascending=False).reset_index(drop=True)
    optimal_xi["is_starter"] = True
    optimal_xi["is_cap"] = False
    optimal_xi["is_vc"] = False
    optimal_xi["Multiplier"] = 1

    if len(optimal_xi) > 0:
        optimal_xi.loc[0, "is_cap"] = True
        optimal_xi.loc[0, "Multiplier"] = 2
    if len(optimal_xi) > 1:
        optimal_xi.loc[1, "is_vc"] = True

    optimal_bench["is_starter"] = False
    optimal_bench["is_cap"] = False
    optimal_bench["is_vc"] = False
    optimal_bench["Multiplier"] = 1

    full_lineup_df = pd.concat([optimal_xi, optimal_bench], ignore_index=True)
    full_lineup_records = full_lineup_df.to_dict(orient="records")

    for r in full_lineup_records:
        r["is_captain"] = bool(r.get("is_cap", False))
        r["is_vice"] = bool(r.get("is_vc", False))

    return full_lineup_records, None


# ── Tab Renderer ─────────────────────────────────────────────────────────────


def load_audit_data(conn, selected_gw):
    from backend.audit_db import init_audit_tables, get_all_gw_versions
    init_audit_tables(conn)
    versions = get_all_gw_versions(conn, selected_gw)
    return versions

def lock_audit_version(conn, manager_id, selected_gw, current_gw):
    from backend.audit_logic import compute_active_solver_squad
    from backend.audit_db import save_pre_gw_snapshot
    lineup_records, err = compute_active_solver_squad(conn, manager_id, selected_gw, current_gw)
    if err:
        return False, err
    new_ver = save_pre_gw_snapshot(conn, selected_gw, lineup_records, transfers_data=[])
    return True, new_ver

def settle_audit_version(conn, selected_gw, selected_version):
    from backend.squad_logic import fetch_live_gameweek_points
    from backend.audit_db import settle_post_gw_snapshot
    raw_live_map = fetch_live_gameweek_points(selected_gw)
    if not raw_live_map:
        return False, "Live data not available"
    clean_points_map = {
        pid: data["points"] if isinstance(data, dict) else data 
        for pid, data in raw_live_map.items()
    }
    settle_post_gw_snapshot(conn, selected_gw, clean_points_map, target_version=selected_version)
    return True, ""

def get_audit_snapshot(conn, selected_gw, selected_version):
    from backend.audit_db import get_snapshot
    import json
    snapshot = get_snapshot(conn, selected_gw, version=selected_version)
    if not snapshot:
        return None
    
    lineups_raw = snapshot.get("lineups_json", "[]")
    lineup = json.loads(lineups_raw) if lineups_raw else []
    
    # Process for UI
    starters = []
    bench = []
    for p in lineup:
        p["img_url"] = get_player_img_url(p.get("photo"), p.get("code"))
        if p.get("bench_order", 0) == 0:
            starters.append(p)
        else:
            bench.append(p)
            
    return {
        "created_at": snapshot.get("created_at"),
        "starters": starters,
        "bench": bench,
        "total_proj": sum(p.get("proj_pts", 0) for p in starters),
        "total_act": sum(p.get("actual_pts", 0) for p in starters if p.get("actual_pts") is not None),
        "is_settled": any(p.get("actual_pts") is not None for p in starters)
    }
