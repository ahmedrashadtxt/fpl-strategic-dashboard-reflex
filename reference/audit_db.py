import json
import os
from pathlib import Path
from datetime import datetime, timezone


def is_sql_server(conn) -> bool:
    mod = type(conn).__module__.lower()
    return "pyodbc" in mod or "pymssql" in mod or "mssql" in mod


def init_audit_tables(conn):
    """Creates the audit table and handles schema consistency across Azure SQL and SQLite."""
    cursor = conn.cursor()

    if is_sql_server(conn):
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'gw_audit_snapshots')
        CREATE TABLE gw_audit_snapshots (
            manager_id NVARCHAR(100),
            gw INT,
            version INT DEFAULT 1,
            created_at NVARCHAR(100),
            updated_at NVARCHAR(100),
            status NVARCHAR(50),
            chip_played NVARCHAR(50),
            formation NVARCHAR(20),
            market_weight FLOAT,
            factor_movement INT,
            lineup_json NVARCHAR(MAX),
            transfers_json NVARCHAR(MAX),
            predicted_total FLOAT,
            actual_total INT,
            variance_pts FLOAT,
            bench_points INT,
            captain_id INT,
            captain_name NVARCHAR(100),
            captain_actual_pts INT,
            vice_captain_id INT,
            vice_captain_name NVARCHAR(100),
            vice_actual_pts INT,
            source NVARCHAR(100) DEFAULT 'Squad Analyzer',
            PRIMARY KEY (manager_id, gw, version)
        );
        """)
        conn.commit()
        return

    # SQLite-specific migration fallback
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gw_audit_snapshots'")
    table_exists = cursor.fetchone() is not None

    if table_exists:
        cursor.execute("PRAGMA table_info(gw_audit_snapshots)")
        cols = {row[1] for row in cursor.fetchall()}

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
                  source TEXT DEFAULT 'Squad Analyzer',
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

        if "source" not in cols:
            cursor.execute("ALTER TABLE gw_audit_snapshots ADD COLUMN source TEXT DEFAULT 'Squad Analyzer'")
            conn.commit()

        if "manager_id" not in cols:
            cursor.execute("""
                CREATE TABLE gw_audit_snapshots_v3 (
                  manager_id TEXT DEFAULT 'DEFAULT_MGR',
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
                  source TEXT DEFAULT 'Squad Analyzer',
                  PRIMARY KEY (manager_id, gw, version)
                )
            """)
            cursor.execute("""
                INSERT INTO gw_audit_snapshots_v3 
                SELECT 'DEFAULT_MGR', gw, version, created_at, updated_at, status, chip_played, 
                       formation, market_weight, factor_movement, lineup_json, transfers_json, 
                       predicted_total, actual_total, variance_pts, bench_points, 
                       captain_id, captain_name, captain_actual_pts, vice_captain_id, 
                       vice_captain_name, vice_actual_pts, source 
                FROM gw_audit_snapshots
            """)
            cursor.execute("DROP TABLE gw_audit_snapshots")
            cursor.execute("ALTER TABLE gw_audit_snapshots_v3 RENAME TO gw_audit_snapshots")
            conn.commit()
            return

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gw_audit_snapshots (
      manager_id TEXT,
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
      source TEXT DEFAULT 'Squad Analyzer',
      PRIMARY KEY (manager_id, gw, version)
    )
    """)
    conn.commit()


def save_pre_gw_snapshot(
    conn,
    manager_id: str,
    gw: int,
    lineup_data: list,
    transfers_data: list = None,
    chip: str = None,
    formation: str = "4-4-2",
    market_weight: float = 0.35,
    factor_movement: bool = True,
    source: str = "Squad Analyzer",
) -> int:
    transfers_data = transfers_data or []
    cursor = conn.cursor()
    mgr_str = str(manager_id).strip() if manager_id else "DEFAULT_MGR"

    cursor.execute(
        "SELECT MAX(version) FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ?",
        (mgr_str, gw),
    )
    row = cursor.fetchone()
    current_max_ver = row[0] if (row and row[0] is not None) else 0
    new_version = current_max_ver + 1

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

    cursor.execute(
        """
        INSERT INTO gw_audit_snapshots (
          manager_id, gw, version, created_at, status, chip_played, formation, market_weight, 
          factor_movement, lineup_json, transfers_json, predicted_total, 
          captain_id, captain_name, vice_captain_id, vice_captain_name, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mgr_str,
            gw,
            new_version,
            datetime.now(timezone.utc).isoformat(),
            "LOCKED_PRE",
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
            source,
        ),
    )
    conn.commit()
    return new_version


def get_snapshot(conn, manager_id: str, gw: int, version: int = None):
    cursor = conn.cursor()
    mgr_str = str(manager_id).strip() if manager_id else "DEFAULT_MGR"
    
    if version is not None:
        cursor.execute(
            "SELECT * FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? AND version = ?",
            (mgr_str, gw, version),
        )
    else:
        # T-SQL uses TOP 1, SQLite uses LIMIT 1
        if is_sql_server(conn):
            cursor.execute(
                "SELECT TOP 1 * FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? ORDER BY version DESC",
                (mgr_str, gw),
            )
        else:
            cursor.execute(
                "SELECT * FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? ORDER BY version DESC LIMIT 1",
                (mgr_str, gw),
            )

    row = cursor.fetchone()
    if not row:
        return None

    cols = [col[0] for col in cursor.description]
    data = dict(zip(cols, row))
    data["lineup"] = json.loads(data["lineup_json"]) if data.get("lineup_json") else []
    data["transfers"] = json.loads(data["transfers_json"]) if data.get("transfers_json") else []
    return data


def get_all_gw_versions(conn, manager_id: str, gw: int) -> list[dict]:
    cursor = conn.cursor()
    mgr_str = str(manager_id).strip() if manager_id else "DEFAULT_MGR"
    cursor.execute(
        """
        SELECT version, created_at, status, predicted_total, actual_total, 
            variance_pts, market_weight, formation, captain_name, source 
        FROM gw_audit_snapshots 
        WHERE manager_id = ? AND gw = ? 
        ORDER BY version DESC
        """,
        (mgr_str, gw),
    )
    rows = cursor.fetchall()
    if not rows:
        return []

    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


def settle_post_gw_snapshot(conn, manager_id: str, gw: int, live_player_points: dict, target_version: int = None):
    cursor = conn.cursor()
    mgr_str = str(manager_id).strip() if manager_id else "DEFAULT_MGR"
    
    if target_version is not None:
        cursor.execute(
            "SELECT version, lineup_json, captain_id, vice_captain_id, predicted_total, chip_played FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? AND version = ?",
            (mgr_str, gw, target_version),
        )
    else:
        if is_sql_server(conn):
            cursor.execute(
                "SELECT TOP 1 version, lineup_json, captain_id, vice_captain_id, predicted_total, chip_played FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? ORDER BY version DESC",
                (mgr_str, gw),
            )
        else:
            cursor.execute(
                "SELECT version, lineup_json, captain_id, vice_captain_id, predicted_total, chip_played FROM gw_audit_snapshots WHERE manager_id = ? AND gw = ? ORDER BY version DESC LIMIT 1",
                (mgr_str, gw),
            )

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

    cursor.execute(
        """
        UPDATE gw_audit_snapshots
        SET updated_at = ?,
          status = 'SETTLED',
          lineup_json = ?,
          actual_total = ?,
          bench_points = ?,
          captain_actual_pts = ?,
          vice_actual_pts = ?,
          variance_pts = ?
        WHERE manager_id = ? AND gw = ? AND version = ?
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            json.dumps(lineup),
            actual_total,
            bench_points,
            captain_actual_pts,
            vice_actual_pts,
            variance,
            mgr_str,
            gw,
            version,
        ),
    )
    conn.commit()
    return True


def get_owner_fpl_id() -> str:
    candidate_keys = (
        "OWNER_FPL_ID", "owner_fpl_id",
        "MY_FPL_ID", "my_fpl_id",
        "ADMIN_FPL_ID", "admin_fpl_id",
        "FPL_ID", "fpl_id",
        "MANAGER_ID", "manager_id",
    )

    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for k in candidate_keys:
                if k in st.secrets:
                    val = str(st.secrets[k]).strip()
                    if val:
                        return val
            for sec in ("fpl", "auth", "admin", "general", "owner"):
                if sec in st.secrets and isinstance(st.secrets[sec], dict):
                    for k in candidate_keys:
                        if k in st.secrets[sec]:
                            val = str(st.secrets[sec][k]).strip()
                            if val:
                                return val
    except Exception:
        pass

    for k in candidate_keys:
        val = os.getenv(k, "").strip()
        if val:
            return val

    try:
        secrets_file = Path(".streamlit") / "secrets.toml"
        if not secrets_file.exists():
            root_dir = Path(__file__).resolve().parent
            candidate_path = root_dir / ".streamlit" / "secrets.toml"
            if candidate_path.exists():
                secrets_file = candidate_path

        if secrets_file.exists():
            try:
                import tomllib
                with open(secrets_file, "rb") as f:
                    data = tomllib.load(f)
                for k in candidate_keys:
                    if k in data and data[k]:
                        return str(data[k]).strip()
                for v in data.values():
                    if isinstance(v, dict):
                        for k in candidate_keys:
                            if k in v and v[k]:
                                return str(v[k]).strip()
            except Exception:
                with open(secrets_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line_clean = line.strip()
                        for k in candidate_keys:
                            if line_clean.startswith(k):
                                parts = line_clean.split("=", 1)
                                if len(parts) == 2:
                                    val = parts[1].split("#")[0].strip().strip('"').strip("'")
                                    if val:
                                        return val
    except Exception:
        pass

    return ""


def is_owner_manager(manager_id: str | int | None) -> bool:
    if manager_id is None:
        return False
    mgr_str = str(manager_id).strip()
    if not mgr_str:
        return False
    owner_id = get_owner_fpl_id()
    if not owner_id:
        return False
    return mgr_str == owner_id