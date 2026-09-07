import sqlite3
import json
from datetime import datetime, timezone

def init_audit_tables(conn: sqlite3.Connection):
    """Creates the audit table and migrates older single-version schemas to multi-version primary keys."""
    cursor = conn.cursor()
    
    # Check if existing table needs multi-version migration
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gw_audit_snapshots'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        cursor.execute("PRAGMA table_info(gw_audit_snapshots)")
        cols = {row[1] for row in cursor.fetchall()}
        
        # If older schema without version column, migrate safely
        if "version" not in cols:
            cursor.execute("""
                CREATE TABLE gw_audit_snapshots_v2 (
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
            cursor.execute("""
                INSERT OR IGNORE INTO gw_audit_snapshots_v2 (
                    gw, version, created_at, updated_at, status, chip_played, 
                    lineup_json, transfers_json, predicted_total, actual_total, 
                    variance_pts, bench_points, captain_id, captain_name, captain_actual_pts
                ) 
                SELECT gw, 1, created_at, updated_at, status, chip_played, 
                       lineup_json, transfers_json, predicted_total, actual_total, 
                       variance_pts, bench_points, captain_id, captain_name, captain_actual_pts 
                FROM gw_audit_snapshots
            """)
            cursor.execute("DROP TABLE gw_audit_snapshots")
            cursor.execute("ALTER TABLE gw_audit_snapshots_v2 RENAME TO gw_audit_snapshots")
            conn.commit()
            return

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gw_audit_snapshots (
            gw INTEGER,
            version INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT,
            status TEXT, -- 'LOCKED_PRE' or 'SETTLED'
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
    cursor = conn.cursor()
    
    # Determine the next incremental version number
    cursor.execute("SELECT MAX(version) FROM gw_audit_snapshots WHERE gw = ?", (gw,))
    row = cursor.fetchone()
    current_max_ver = row[0] if (row and row[0] is not None) else 0
    new_version = current_max_ver + 1

    # Calculate predicted starting total
    predicted_total = 0.0
    for p in lineup_data:
        if p.get("is_starter", True):
            xp = float(p.get("Proj_Pts", p.get("predicted_xp", 0.0)) or 0.0)
            mult = int(p.get("Multiplier", 1) or 1)
            predicted_total += xp * mult

    captain = next((p for p in lineup_data if p.get("is_cap") or p.get("is_captain")), None)
    vice = next((p for p in lineup_data if p.get("is_vc") or p.get("is_vice_captain")), None)
    
    cap_name = captain.get("Player", captain.get("web_name", "Unknown")) if captain else "Unknown"
    vc_name = vice.get("Player", vice.get("web_name", "Unknown")) if vice else "Unknown"

    cursor.execute("""
        INSERT INTO gw_audit_snapshots (
            gw, version, created_at, status, chip_played, formation, market_weight, 
            factor_movement, lineup_json, transfers_json, predicted_total, 
            captain_id, captain_name, vice_captain_id, vice_captain_name
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        gw,
        new_version,
        datetime.now(timezone.utc).isoformat(),
        'LOCKED_PRE',
        chip,
        formation,
        market_weight,
        1 if factor_movement else 0,
        json.dumps(lineup_data),
        json.dumps(transfers_data),
        round(predicted_total, 2),
        captain["id"] if captain else None,
        cap_name,
        vice["id"] if vice else None,
        vc_name,
    ))
    conn.commit()
    return new_version

def get_snapshot(conn: sqlite3.Connection, gw: int, version: int = None):
    """Retrieves a specific version snapshot, or defaults to the latest version."""
    cursor = conn.cursor()
    if version is not None:
        cursor.execute("SELECT * FROM gw_audit_snapshots WHERE gw = ? AND version = ?", (gw, version))
    else:
        cursor.execute("SELECT * FROM gw_audit_snapshots WHERE gw = ? ORDER BY version DESC LIMIT 1", (gw,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    cols = [col[0] for col in cursor.description]
    data = dict(zip(cols, row))
    data["lineup"] = json.loads(data["lineup_json"]) if data.get("lineup_json") else []
    data["transfers"] = json.loads(data["transfers_json"]) if data.get("transfers_json") else []
    return data

def get_all_gw_versions(conn: sqlite3.Connection, gw: int) -> list[dict]:
    """Retrieves high-level metadata for all saved versions of a given gameweek."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT version, created_at, status, predicted_total, actual_total, 
               variance_pts, market_weight, formation, captain_name 
        FROM gw_audit_snapshots 
        WHERE gw = ? 
        ORDER BY version DESC
    """, (gw,))
    rows = cursor.fetchall()
    if not rows:
        return []
    
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]

def settle_post_gw_snapshot(conn: sqlite3.Connection, gw: int, live_player_points: dict, target_version: int = None):
    """Updates the final (or specified) version with official match results and computes variance."""
    cursor = conn.cursor()
    if target_version is not None:
        cursor.execute("SELECT version, lineup_json, captain_id, vice_captain_id, predicted_total, chip_played FROM gw_audit_snapshots WHERE gw = ? AND version = ?", (gw, target_version))
    else:
        cursor.execute("SELECT version, lineup_json, captain_id, vice_captain_id, predicted_total, chip_played FROM gw_audit_snapshots WHERE gw = ? ORDER BY version DESC LIMIT 1", (gw,))
    
    row = cursor.fetchone()
    if not row:
        return False
    
    version = row[0]
    lineup = json.loads(row[1])
    captain_id = row[2]
    vice_id = row[3]
    predicted_total = row[4] or 0.0
    chip = row[5]

    actual_total = 0
    bench_points = 0
    captain_actual_pts = 0
    vice_actual_pts = 0

    cap_mult = 3 if chip == "Triple Captain" else 2

    for p in lineup:
        pid = p["id"]
        pts = live_player_points.get(pid, 0)
        p["actual_pts"] = pts
        
        is_c = bool(p.get("is_cap") or p.get("is_captain") or pid == captain_id)
        is_v = bool(p.get("is_vc") or p.get("is_vice_captain") or pid == vice_id)

        if p.get("is_starter", True):
            if is_c:
                p_score = pts * cap_mult
                captain_actual_pts = p_score
            else:
                p_score = pts
            actual_total += p_score
        else:
            if chip == "Bench Boost":
                actual_total += pts
            else:
                bench_points += pts

        if is_v:
            vice_actual_pts = pts

    variance = round(actual_total - predicted_total, 2)

    cursor.execute("""
        UPDATE gw_audit_snapshots
        SET updated_at = ?,
            status = 'SETTLED',
            lineup_json = ?,
            actual_total = ?,
            bench_points = ?,
            captain_actual_pts = ?,
            vice_actual_pts = ?,
            variance_pts = ?
        WHERE gw = ? AND version = ?
    """, (
        datetime.now(timezone.utc).isoformat(),
        json.dumps(lineup),
        actual_total,
        bench_points,
        captain_actual_pts,
        vice_actual_pts,
        variance,
        gw,
        version
    ))
    conn.commit()
    return True