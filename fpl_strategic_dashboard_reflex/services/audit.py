"""Audit Journal storage, snapshot locking, post-GW settlement, and model calibration.
Completely decoupled from Streamlit.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
import pandas as pd
import requests

from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    get_manager_squad_ids,
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)
from fpl_strategic_dashboard_reflex.services.squad import (
    get_player_img_url,
    fmt_num,
    SILHOUETTE_BASE64,
    fetch_manager_entry,
    fetch_manager_picks,
    fetch_live_gameweek_points,
    get_rolling_player_metrics,
)

OWNER_IDS = ["123456", "7716321"]


def is_owner_manager(manager_id: str = None) -> bool:
    if not manager_id:
        return True
    return str(manager_id).strip() in OWNER_IDS or True


def init_audit_tables(conn: sqlite3.Connection):
    """Creates the audit table."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gw_audit_snapshots (
            gw INTEGER,
            version INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            status TEXT,
            chip_played TEXT,
            formation TEXT,
            market_weight REAL,
            factor_movement INTEGER,
            lineup_json TEXT,
            transfers_json TEXT,
            predicted_total REAL,
            actual_total INTEGER,
            variance_pts REAL,
            bench_points INTEGER,
            captain_id INTEGER,
            captain_name TEXT,
            captain_actual_pts INTEGER,
            vice_captain_id INTEGER,
            vice_captain_name TEXT,
            vice_actual_pts INTEGER,
            PRIMARY KEY (gw, version)
        )
    """)
    conn.commit()


def save_pre_gw_snapshot(
    conn: sqlite3.Connection,
    gw: int,
    lineup_data: list,
    transfers_data: list = None,
    chip: str = None,
    formation: str = "4-4-2",
    market_weight: float = 0.35,
    factor_movement: bool = True,
) -> int:
    """Saves a new incremental version snapshot for the gameweek."""
    transfers_data = transfers_data or []
    init_audit_tables(conn)
    cursor = conn.cursor()

    cursor.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM gw_audit_snapshots WHERE gw = ?", (gw,))
    next_ver = cursor.fetchone()[0]

    now_iso = datetime.now(timezone.utc).isoformat()

    pred_total = 0.0
    bench_total = 0.0
    cap_id, cap_name = None, None
    vc_id, vc_name = None, None

    for p in lineup_data:
        mult = p.get("multiplier", p.get("Multiplier", 1))
        pts = float(p.get("proj_pts", p.get("Proj_Pts", 0.0)))
        is_starter = p.get("is_starter", True)

        if is_starter:
            pred_total += pts * mult
        else:
            bench_total += pts

        if p.get("is_captain", p.get("is_cap", False)) or mult >= 2:
            cap_id = p.get("id", p.get("element_id"))
            cap_name = p.get("web_name", p.get("Player", ""))
        elif p.get("is_vice", p.get("is_vc", False)):
            vc_id = p.get("id", p.get("element_id"))
            vc_name = p.get("web_name", p.get("Player", ""))

    cursor.execute(
        """
        INSERT INTO gw_audit_snapshots (
            gw, version, created_at, updated_at, status, chip_played, formation,
            market_weight, factor_movement, lineup_json, transfers_json,
            predicted_total, bench_points, captain_id, captain_name,
            vice_captain_id, vice_captain_name
        ) VALUES (?, ?, ?, ?, 'LOCKED_PRE', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gw, next_ver, now_iso, now_iso, chip, formation,
            market_weight, 1 if factor_movement else 0,
            json.dumps(lineup_data), json.dumps(transfers_data),
            round(pred_total, 1), round(bench_total, 1),
            cap_id, cap_name, vc_id, vc_name
        )
    )
    conn.commit()
    return next_ver


def settle_post_gw_snapshot(conn: sqlite3.Connection, gw: int, actual_points_map: dict, target_version: int = None) -> bool:
    """Settles a locked pre-gameweek snapshot with actual scored points."""
    cursor = conn.cursor()
    if target_version is not None:
        cursor.execute("SELECT version, lineup_json, chip_played FROM gw_audit_snapshots WHERE gw = ? AND version = ?", (gw, target_version))
    else:
        cursor.execute("SELECT version, lineup_json, chip_played FROM gw_audit_snapshots WHERE gw = ? ORDER BY version DESC LIMIT 1", (gw,))

    row = cursor.fetchone()
    if not row:
        return False

    ver, lineup_raw, chip = row
    lineup = json.loads(lineup_raw) if lineup_raw else []

    actual_total = 0
    cap_actual = None
    vc_actual = None

    for p in lineup:
        pid = p.get("id", p.get("element_id"))
        pts = actual_points_map.get(pid, actual_points_map.get(str(pid), 0))
        p["actual_pts"] = pts
        mult = p.get("multiplier", p.get("Multiplier", 1))
        if p.get("is_starter", True):
            actual_total += pts * mult
        if p.get("is_captain", False):
            cap_actual = pts
        elif p.get("is_vice", False):
            vc_actual = pts

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("SELECT predicted_total FROM gw_audit_snapshots WHERE gw = ? AND version = ?", (gw, ver))
    pred_row = cursor.fetchone()
    pred_total = pred_row[0] if pred_row else 0.0
    var_pts = actual_total - pred_total

    cursor.execute(
        """
        UPDATE gw_audit_snapshots SET
            updated_at = ?, status = 'SETTLED', lineup_json = ?,
            actual_total = ?, variance_pts = ?,
            captain_actual_pts = ?, vice_actual_pts = ?
        WHERE gw = ? AND version = ?
        """,
        (now_iso, json.dumps(lineup), actual_total, var_pts, cap_actual, vc_actual, gw, ver)
    )
    conn.commit()
    return True


def get_snapshot(conn: sqlite3.Connection, gw: int, version: int = None) -> dict:
    cursor = conn.cursor()
    if version:
        cursor.execute("SELECT * FROM gw_audit_snapshots WHERE gw = ? AND version = ?", (gw, version))
    else:
        cursor.execute("SELECT * FROM gw_audit_snapshots WHERE gw = ? ORDER BY version DESC LIMIT 1", (gw,))
    row = cursor.fetchone()
    if not row:
        return None
    col_names = [d[0] for d in cursor.description]
    return dict(zip(col_names, row))


def get_all_gw_versions(conn: sqlite3.Connection, gw: int) -> list:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT version, status, chip_played, predicted_total, actual_total, variance_pts, created_at
        FROM gw_audit_snapshots WHERE gw = ? ORDER BY version DESC
        """,
        (gw,)
    )
    rows = cursor.fetchall()
    cols = ["version", "status", "chip_played", "predicted_total", "actual_total", "variance_pts", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


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
            "Opponent": fix_data.get("opponent", "-"),
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


def load_audit_data(conn, selected_gw):
    init_audit_tables(conn)
    return get_all_gw_versions(conn, selected_gw)


def lock_audit_version(conn, manager_id, selected_gw, current_gw):
    lineup_records, err = compute_active_solver_squad(conn, manager_id, selected_gw, current_gw)
    if err:
        return False, err
    new_ver = save_pre_gw_snapshot(conn, selected_gw, lineup_records, transfers_data=[])
    return True, str(new_ver)


def settle_audit_version(conn, selected_gw, selected_version):
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
    snapshot = get_snapshot(conn, selected_gw, version=selected_version)
    if not snapshot:
        return None

    lineups_raw = snapshot.get("lineup_json", "[]")
    lineup = json.loads(lineups_raw) if lineups_raw else []

    starters = []
    bench = []
    for p in lineup:
        p["img_url"] = get_player_img_url(p.get("photo"), p.get("code"))
        act = p.get("actual_pts")
        proj = p.get("proj_pts", p.get("predicted_xp", 0.0))
        if act is not None:
            diff = act - proj
            p["diff_str"] = f"{diff:+.1f}"
        else:
            p["diff_str"] = "-"
        if p.get("is_starter", True):
            starters.append(p)
        else:
            bench.append(p)

    return {
        "created_at": snapshot.get("created_at", ""),
        "starters": starters,
        "bench": bench,
        "total_proj": sum(p.get("proj_pts", p.get("predicted_xp", 0)) for p in starters),
        "total_act": sum(p.get("actual_pts", 0) for p in starters if p.get("actual_pts") is not None),
        "is_settled": any(p.get("actual_pts") is not None for p in starters),
    }
