import os
from pathlib import Path
import sqlite3
import pandas as pd
import requests
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fpl.db"


def get_db_credentials():
    """Extracts DB configuration from environment variables or Streamlit secrets."""
    host = os.getenv("DB_HOST", "").strip()
    dbname = os.getenv("DB_NAME", "").strip()
    user = os.getenv("DB_USER", "").strip()
    password = os.getenv("DB_PASS", "").strip()

    if not (host and user and password):
        try:
            if hasattr(st, "secrets"):
                for sec in ("azure_sql", "database", "sql"):
                    if sec in st.secrets and isinstance(st.secrets[sec], dict):
                        host = host or st.secrets[sec].get("DB_HOST") or st.secrets[sec].get("host", "")
                        dbname = dbname or st.secrets[sec].get("DB_NAME") or st.secrets[sec].get("database", "")
                        user = user or st.secrets[sec].get("DB_USER") or st.secrets[sec].get("user", "")
                        password = password or st.secrets[sec].get("DB_PASS") or st.secrets[sec].get("password", "")
                host = host or st.secrets.get("DB_HOST", "")
                dbname = dbname or st.secrets.get("DB_NAME", "")
                user = user or st.secrets.get("DB_USER", "")
                password = password or st.secrets.get("DB_PASS", "")
        except Exception:
            pass

    return host, dbname, user, password


def is_azure_configured() -> bool:
    host, _, user, password = get_db_credentials()
    return bool(host and user and password)


def get_engine():
    """Returns an SQLAlchemy engine for Azure SQL or local SQLite."""
    host, dbname, user, password = get_db_credentials()
    if host and user and password:
        dbname = dbname or "fpl-production-db"
        try:
            connection_url = URL.create(
                "mssql+pyodbc",
                username=user,
                password=password,
                host=host,
                port=1433,
                database=dbname,
                query={
                    "driver": "ODBC Driver 18 for SQL Server",
                    "Encrypt": "yes",
                    "TrustServerCertificate": "no",
                },
            )
            return create_engine(connection_url, fast_executemany=True)
        except Exception:
            import urllib.parse
            safe_u = urllib.parse.quote_plus(user)
            safe_p = urllib.parse.quote_plus(password)
            return create_engine(f"mssql+pymssql://{safe_u}:{safe_p}@{host}:1433/{dbname}")

    return create_engine(f"sqlite:///{DB_PATH}")


def get_connection():
    """Returns an active DB connection (pyodbc, pymssql, or sqlite3)."""
    host, dbname, user, password = get_db_credentials()
    if host and user and password:
        dbname = dbname or "fpl-production-db"
        try:
            import pyodbc
            odbc_str = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server=tcp:{host},1433;"
                f"Database={dbname};"
                f"Uid={user};"
                f"Pwd={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            return pyodbc.connect(odbc_str)
        except Exception:
            import pymssql
            return pymssql.connect(server=host, user=user, password=password, database=dbname, port=1433)

    return sqlite3.connect(DB_PATH, check_same_thread=False)


def is_sql_server(conn) -> bool:
    """Checks whether the active connection is Azure SQL Server or SQLite."""
    mod = type(conn).__module__.lower()
    return "pyodbc" in mod or "pymssql" in mod or "mssql" in mod


def ensure_database_ready():
    """Checks if the target database contains tables; if not, triggers data ingestion."""
    needs_init = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if is_sql_server(conn):
            cursor.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='events'")
            row = cursor.fetchone()
            if not row:
                needs_init = True
        else:
            if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
                needs_init = True
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
                if not cursor.fetchone():
                    needs_init = True
        conn.close()
    except Exception:
        needs_init = True

    if needs_init:
        with st.spinner("Initializing database from official FPL API..."):
            import fetch_data
            if hasattr(fetch_data, "main"):
                fetch_data.main()
            elif hasattr(fetch_data, "fetch_all_data"):
                fetch_data.fetch_all_data()
            elif hasattr(fetch_data, "fetch_data"):
                fetch_data.fetch_data()


def get_global_gameweek_info(conn):
    events_df = pd.read_sql("SELECT id, name, is_current, is_next, finished FROM events", conn)
    finished_ids = (
        events_df[events_df["finished"] == 1]["id"].tolist()
        if "finished" in events_df.columns
        else []
    )
    next_gw_row = events_df[events_df["is_next"] == 1]
    next_gw = int(next_gw_row["id"].values[0]) if not next_gw_row.empty else 1

    ongoing_rows = events_df[
        (~events_df["id"].isin(finished_ids)) & (events_df["id"] < next_gw)
    ]

    if not ongoing_rows.empty:
        ongoing_id = int(ongoing_rows.iloc[0]["id"])
        gw_name = f"Gameweek {ongoing_id} (Live)"
    elif not next_gw_row.empty:
        gw_name = next_gw_row["name"].values[0]
    else:
        gw_name = f"Gameweek {next_gw}"

    return events_df, next_gw, gw_name


def get_summary_stats(conn):
    return pd.read_sql(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN (expected_goals - goals_scored) >= 0.5 THEN 1 ELSE 0 END) AS buy_signals,
          SUM(CASE WHEN (expected_goals - goals_scored) <= -0.5 THEN 1 ELSE 0 END) AS sell_signals,
          SUM(CASE WHEN (transfers_in_event - transfers_out_event) > 30000 THEN 1 ELSE 0 END) AS heating,
          SUM(CASE WHEN (transfers_in_event - transfers_out_event) < -30000 THEN 1 ELSE 0 END) AS cooling
        FROM players
        WHERE minutes > 0
        """,
        conn,
    )


@st.cache_data(ttl=3600, show_spinner=False)
def get_teams_fdr_map(_conn, current_gw: int):
    fixtures_5gw = pd.read_sql(
        """
        SELECT event, team_h, team_a, team_h_difficulty, team_a_difficulty
        FROM fixtures
        WHERE event >= ? AND event < ? AND finished = 0
        """,
        _conn,
        params=[current_gw, current_gw + 5],
    )

    teams_fdr_map = {}
    for t_id in range(1, 21):
        h_diff = fixtures_5gw[fixtures_5gw["team_h"] == t_id]["team_h_difficulty"].sum()
        a_diff = fixtures_5gw[fixtures_5gw["team_a"] == t_id]["team_a_difficulty"].sum()
        teams_fdr_map[t_id] = int(h_diff + a_diff) if (h_diff + a_diff) > 0 else 15
    return teams_fdr_map


@st.cache_data(ttl=3600, show_spinner=False)
def get_historical_player_baselines(_conn):
    try:
        query = """
        WITH ranked_seasons AS (
          SELECT 
            element_id,
            season_name,
            total_points,
            minutes,
            ROW_NUMBER() OVER (PARTITION BY element_id ORDER BY season_name DESC) AS recency_rank
          FROM player_past_seasons
          WHERE minutes >= 450
        )
        SELECT 
          element_id,
          (SUM(total_points * CASE WHEN recency_rank = 1 THEN 2.0 ELSE 1.0 END) * 1.0 / 
           NULLIF(SUM(minutes * CASE WHEN recency_rank = 1 THEN 2.0 ELSE 1.0 END), 0)) * 90.0 AS hist_pts_per_90,
          SUM(minutes) AS hist_total_mins
        FROM ranked_seasons
        GROUP BY element_id;
        """
        df = pd.read_sql(query, _conn)
        if not df.empty and "element_id" in df.columns:
            return df.set_index("element_id")
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_manager_squad_ids(mgr_id: str, target_gw: int):
    if not mgr_id:
        return []
    try:
        gw = target_gw if target_gw >= 1 else 1
        picks_url = f"https://fantasy.premierleague.com/api/entry/{mgr_id}/event/{gw}/picks/"
        res = requests.get(picks_url, timeout=10)
        if res.status_code != 200 and gw > 1:
            gw -= 1
            picks_url = f"https://fantasy.premierleague.com/api/entry/{mgr_id}/event/{gw}/picks/"
            res = requests.get(picks_url, timeout=10)
        if res.status_code == 200:
            return [p["element"] for p in res.json().get("picks", [])]
    except Exception:
        return []
    return []


@st.cache_data(ttl=600, show_spinner=False)
def get_motw_data(target_gw: int):
    motw_id = None
    motw_score = None
    try:
        bs_res = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/", timeout=10)
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
            mgr_info = requests.get(f"https://fantasy.premierleague.com/api/entry/{motw_id}/", timeout=10).json()
            mgr_name = mgr_info.get("name", "Top Manager")
            player_name = f"{mgr_info.get('player_first_name', '')} {mgr_info.get('player_last_name', '')}".strip()
            picks_res = requests.get(
                f"https://fantasy.premierleague.com/api/entry/{motw_id}/event/{target_gw}/picks/",
                timeout=10,
            ).json()
            picks_list = picks_res.get("picks", [])
            return {
                "type": "motw",
                "manager_name": mgr_name,
                "player_name": player_name,
                "total_score": motw_score or picks_res.get("entry_history", {}).get("points", 0),
                "picks": picks_list,
            }
        except Exception:
            pass

    try:
        dt_res = requests.get(f"https://fantasy.premierleague.com/api/dream-team/{target_gw}/", timeout=10).json()
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
            "manager_name": "Kings of the Gameweek",
            "player_name": "Official Dream Team",
            "total_score": top_pts,
            "picks": picks_list,
        }
    except Exception:
        return None


def get_fixture_for_team(fixtures_df, team_id, target_gw):
    match = fixtures_df[
        (fixtures_df["GW"] == target_gw)
        & ((fixtures_df["team_h_id"] == team_id) | (fixtures_df["team_a_id"] == team_id))
    ]
    if match.empty:
        return {"opponent": "Blank", "fdr": 5, "is_home": False}

    row = match.iloc[0]
    if row["team_h_id"] == team_id:
        return {"opponent": f"{row['Away_Team']} (H)", "fdr": int(row["Home_Diff"]), "is_home": True}
    return {"opponent": f"{row['Home_Team']} (A)", "fdr": int(row["Away_Diff"]), "is_home": False}


def calculate_projected_points(player_row, fix_info, current_gw_num, hist_baselines_df=None):
    pos = str(player_row.get("Pos", "MID")).upper()
    fdr = fix_info.get("fdr", 3)
    is_home = fix_info.get("is_home", False)
    p_id = player_row.get("id")

    elapsed_gws = max(1, current_gw_num - 1)
    season_mins = float(player_row.get("minutes", 0) or 0.0)
    avg_mins_per_gw = season_mins / elapsed_gws if current_gw_num > 1 else 90.0

    roll_mins = player_row.get("roll_mins")
    cost = float(player_row.get("Cost", 5.0) or 5.0)
    curr_ppg = float(player_row.get("PPG", 0.0) or 0.0)
    is_target = player_row.get("is_target", False)

    if is_target:
        exp_mins = 80.0
    elif pd.notna(roll_mins) and float(roll_mins) > 0:
        exp_mins = (float(roll_mins) * 0.65) + (avg_mins_per_gw * 0.35)
    elif current_gw_num > 1:
        exp_mins = avg_mins_per_gw
        status = str(player_row.get("Status", player_row.get("status", "a"))).lower()
        if (cost >= 6.5 or curr_ppg >= 4.0) and (status in ("a", "d")):
            exp_mins = max(exp_mins, 60.0)
    else:
        exp_mins = 85.0 if cost >= 8.0 else (70.0 if cost >= 6.0 else 45.0)

    exp_mins = max(0.0, min(90.0, exp_mins))
    if exp_mins < 5.0:
        return 0.0

    p_60_mins = max(0.0, min(1.0, (exp_mins - 25.0) / 45.0)) if exp_mins >= 25.0 else 0.0
    mins_ratio = exp_mins / 90.0

    pos_default_pts = {"GKP": 3.6, "DEF": 3.5, "MID": 4.1, "FWD": 4.4}
    pos_default_xgi90 = {"GKP": 0.01, "DEF": 0.08, "MID": 0.25, "FWD": 0.38}
    hist_pts_90 = pos_default_pts.get(pos, 4.0)

    if hist_baselines_df is not None and not hist_baselines_df.empty and p_id in hist_baselines_df.index:
        val = hist_baselines_df.loc[p_id, "hist_pts_per_90"]
        if pd.notna(val) and float(val) > 0:
            hist_pts_90 = float(val)

    sample_weight = min(1.0, season_mins / 540.0) if current_gw_num > 1 else 0.0
    form = float(player_row.get("Form", 0.0) or 0.0)

    if curr_ppg > 0:
        if curr_ppg >= 3.5 and (form == 0.0 or form < (curr_ppg * 0.4)):
            curr_base_rate = curr_ppg
        else:
            curr_base_rate = (curr_ppg * 0.7) + (form * 0.3)
    else:
        curr_base_rate = hist_pts_90

    blended_base_rate = (sample_weight * curr_base_rate) + ((1.0 - sample_weight) * hist_pts_90)

    fdr_cs_probs = {2: 0.44, 3: 0.28, 4: 0.16, 5: 0.08}
    cs_prob = fdr_cs_probs.get(fdr, 0.25) * (1.15 if is_home else 0.88)
    atk_mult = max(0.4, (6.0 - fdr) / 3.0) * (1.08 if is_home else 0.94)

    raw_xgi_90 = float(player_row.get("roll_xgi90", player_row.get("xGI_per_90", 0.0)) or 0.0)
    shrunk_xgi_90 = (sample_weight * raw_xgi_90) + ((1.0 - sample_weight) * pos_default_xgi90.get(pos, 0.22))

    app_pts = (2.0 * p_60_mins) + (1.0 * (1.0 - p_60_mins) * min(1.0, exp_mins / 10.0))

    if pos in ("GKP", "DEF"):
        goal_pts, assist_pts = 6.0, 3.0
        cs_pts = 4.0
        def_concede_deduction = (0.55 if fdr >= 4 else 0.20) * p_60_mins
        xp_clean_sheet = (cs_prob * cs_pts) * p_60_mins
        expected_attack_90 = (shrunk_xgi_90 * 0.25 * goal_pts) + (shrunk_xgi_90 * 0.75 * assist_pts)
        xp_attacking = expected_attack_90 * atk_mult * mins_ratio
        xp_saves_bonus = (1.0 if pos == "GKP" else 0.35) * mins_ratio
        xp = app_pts + xp_clean_sheet + xp_attacking + xp_saves_bonus - def_concede_deduction

    elif pos == "MID":
        goal_pts, assist_pts = 5.0, 3.0
        xp_clean_sheet = cs_prob * 1.0 * p_60_mins
        expected_attack_90 = (shrunk_xgi_90 * 0.55 * goal_pts) + (shrunk_xgi_90 * 0.45 * assist_pts)
        xp_attacking = expected_attack_90 * atk_mult * mins_ratio
        xp_bonus = max(0.0, (blended_base_rate - 3.8) * 0.4) * mins_ratio
        xp = app_pts + xp_clean_sheet + xp_attacking + xp_bonus

    else:
        goal_pts, assist_pts = 4.0, 3.0
        expected_attack_90 = (shrunk_xgi_90 * 0.75 * goal_pts) + (shrunk_xgi_90 * 0.25 * assist_pts)
        xp_attacking = expected_attack_90 * atk_mult * mins_ratio
        xp_bonus = max(0.0, (blended_base_rate - 4.0) * 0.4) * mins_ratio
        xp = app_pts + xp_attacking + xp_bonus

    status = str(player_row.get("Status", player_row.get("status", "a"))).lower()
    chance = player_row.get("Chance", player_row.get("chance_of_playing_next_round"))
    if status in ("i", "u", "s"):
        avail_mult = 0.0
    elif pd.notna(chance) and str(chance).strip() not in ("", "None"):
        avail_mult = float(chance) / 100.0
    else:
        avail_mult = 1.0

    return round(max(0.0, xp * avail_mult), 2)


def solve_optimal_xi(squad_df_evaluated):
    gkps = squad_df_evaluated[squad_df_evaluated["Pos"] == "GKP"].sort_values("Proj_Pts", ascending=False)
    defs = squad_df_evaluated[squad_df_evaluated["Pos"] == "DEF"].sort_values("Proj_Pts", ascending=False)
    mids = squad_df_evaluated[squad_df_evaluated["Pos"] == "MID"].sort_values("Proj_Pts", ascending=False)
    fwds = squad_df_evaluated[squad_df_evaluated["Pos"] == "FWD"].sort_values("Proj_Pts", ascending=False)

    starter_gkp = gkps.head(1)
    bench_gkp = gkps.tail(max(0, len(gkps) - 1))

    mandatory_defs = defs.head(3)
    mandatory_mids = mids.head(2)
    mandatory_fwds = fwds.head(1)

    rem_pool = pd.concat([defs.iloc[3:], mids.iloc[2:], fwds.iloc[1:]]).sort_values("Proj_Pts", ascending=False)
    extra_starters = rem_pool.head(4)
    bench_outfield = rem_pool.tail(max(0, len(rem_pool) - 4))

    starters = pd.concat([
        starter_gkp,
        mandatory_defs,
        mandatory_mids,
        mandatory_fwds,
        extra_starters,
    ]).sort_values("Proj_Pts", ascending=False)

    bench = pd.concat([bench_gkp, bench_outfield])
    formation = f"{len(starters[starters['Pos'] == 'DEF'])}-{len(starters[starters['Pos'] == 'MID'])}-{len(starters[starters['Pos'] == 'FWD'])}"
    return starters, bench, formation


def create_price_predictions_table(conn):
    cursor = conn.cursor()
    if is_sql_server(conn):
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'player_price_predictions')
        CREATE TABLE player_price_predictions (
            element_id INT PRIMARY KEY,
            player_name NVARCHAR(100),
            team_short NVARCHAR(10),
            pos NVARCHAR(10),
            now_cost FLOAT,
            selected_by_percent FLOAT,
            net_transfers_event INT,
            transfer_velocity_hourly FLOAT,
            target_progress_pct FLOAT,
            price_status NVARCHAR(50),
            updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
        );
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_price_predictions (
            element_id INTEGER PRIMARY KEY,
            player_name TEXT,
            team_short TEXT,
            pos TEXT,
            now_cost REAL,
            selected_by_percent REAL,
            net_transfers_event INTEGER,
            transfer_velocity_hourly REAL,
            target_progress_pct REAL,
            price_status TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    conn.commit()


def calculate_price_change_predictions(conn) -> pd.DataFrame:
    create_price_predictions_table(conn)

    query = """
    SELECT 
      p.id AS element_id,
      p.web_name AS player_name,
      t.short_name AS team_short,
      CASE p.element_type 
        WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' 
      END AS pos,
      p.now_cost / 10.0 AS now_cost,
      CAST(p.selected_by_percent AS FLOAT) AS selected_by_percent,
      (p.transfers_in_event - p.transfers_out_event) AS net_transfers,
      p.status AS status,
      p.cost_change_event
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    """
    df = pd.read_sql(query, conn)
    if df.empty:
        return pd.DataFrame()

    records = []
    total_fpl_managers = 10_500_000

    for _, row in df.iterrows():
        ownership_pct = max(0.1, float(row["selected_by_percent"] or 0.1))
        owned_count = (ownership_pct / 100.0) * total_fpl_managers
        net_transfers = int(row["net_transfers"] or 0)
        status = str(row["status"] or "a")

        if net_transfers > 0:
            threshold = max(24000.0, owned_count * 0.022)
            if status != "a":
                threshold *= 1.50
            progress = (net_transfers / threshold) * 100.0
        else:
            threshold = max(18000.0, owned_count * 0.016)
            if status in ("i", "u", "s"):
                threshold *= 0.60
            progress = (net_transfers / threshold) * 100.0

        progress = max(-100.0, min(100.0, round(progress, 1)))

        if progress >= 90.0:
            price_status = "RISING_TONIGHT :material/rocket:"
        elif progress >= 70.0:
            price_status = "RISING_SOON :material/trending_up:"
        elif progress <= -90.0:
            price_status = "FALLING_TONIGHT :material/warning:"
        elif progress <= -70.0:
            price_status = "FALLING_SOON :material/trending_down:"
        else:
            price_status = "STABLE "

        records.append({
            "element_id": row["element_id"],
            "player_name": row["player_name"],
            "team_short": row["team_short"],
            "pos": row["pos"],
            "now_cost": row["now_cost"],
            "selected_by_percent": ownership_pct,
            "net_transfers_event": net_transfers,
            "transfer_velocity_hourly": 0.0,
            "target_progress_pct": progress,
            "price_status": price_status,
        })

    pred_df = pd.DataFrame(records)
    engine = get_engine()
    pred_df.to_sql("player_price_predictions", engine, if_exists="replace", index=False)
    return pred_df


@st.cache_data(ttl=600, show_spinner=False)
def get_price_prediction_map(_conn) -> dict:
    query = """
    SELECT element_id, target_progress_pct, price_status, net_transfers_event
    FROM player_price_predictions
    """
    try:
        df = pd.read_sql(query, _conn)
        if df.empty:
            return {}
        return df.set_index("element_id").to_dict(orient="index")
    except Exception:
        return {}