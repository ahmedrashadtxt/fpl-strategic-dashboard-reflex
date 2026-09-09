import os
from pathlib import Path
import sys
import time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Import centralized DB engine & connection from data.py
try:
    from data import get_engine, get_connection, is_sql_server
except ImportError:
    from sqlalchemy import create_engine
    import sqlite3

    def get_engine():
        return create_engine("sqlite:///fpl.db")

    def get_connection():
        return sqlite3.connect("fpl.db")

    def is_sql_server(conn):
        return False


def get_odds_api_key() -> str:
    key = os.getenv("ODDS_API_KEY", "").strip()
    if key:
        return key

    try:
        import streamlit as st
        key = st.secrets.get("ODDS_API_KEY", "").strip()
        if key:
            return key
    except Exception:
        pass

    try:
        secrets_file = Path(".streamlit") / "secrets.toml"
        if secrets_file.exists():
            with open(secrets_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("ODDS_API_KEY"):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            return key
    except Exception:
        pass

    return ""


def get_session_and_headers():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://fantasy.premierleague.com/",
        "Origin": "https://fantasy.premierleague.com",
    }
    return session, headers


def create_history_table(conn):
    cursor = conn.cursor()
    if is_sql_server(conn):
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'player_match_history')
        CREATE TABLE player_match_history (
            element_id INT,
            round INT,
            fixture_id INT,
            opponent_team INT,
            was_home INT,
            total_points INT,
            minutes INT,
            goals_scored INT,
            assists INT,
            clean_sheets INT,
            goals_conceded INT,
            expected_goals NVARCHAR(50),
            expected_assists NVARCHAR(50),
            expected_goal_involvements NVARCHAR(50),
            expected_goals_conceded NVARCHAR(50),
            influence NVARCHAR(50),
            creativity NVARCHAR(50),
            threat NVARCHAR(50),
            ict_index NVARCHAR(50),
            bps INT,
            bonus INT,
            value INT,
            transfers_in INT,
            transfers_out INT,
            PRIMARY KEY (element_id, round)
        );
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_match_history (
            element_id INTEGER,
            round INTEGER,
            fixture_id INTEGER,
            opponent_team INTEGER,
            was_home INTEGER,
            total_points INTEGER,
            minutes INTEGER,
            goals_scored INTEGER,
            assists INTEGER,
            clean_sheets INTEGER,
            goals_conceded INTEGER,
            expected_goals TEXT,
            expected_assists TEXT,
            expected_goal_involvements TEXT,
            expected_goals_conceded TEXT,
            influence TEXT,
            creativity TEXT,
            threat TEXT,
            ict_index TEXT,
            bps INTEGER,
            bonus INTEGER,
            value INTEGER,
            transfers_in INTEGER,
            transfers_out INTEGER,
            PRIMARY KEY (element_id, round)
        );
        """)
    conn.commit()


def create_past_seasons_table(conn):
    cursor = conn.cursor()
    if is_sql_server(conn):
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'player_past_seasons')
        CREATE TABLE player_past_seasons (
            element_id INT,
            season_name NVARCHAR(50),
            start_cost INT,
            end_cost INT,
            total_points INT,
            minutes INT,
            goals_scored INT,
            assists INT,
            clean_sheets INT,
            goals_conceded INT,
            bonus INT,
            bps INT,
            influence NVARCHAR(50),
            creativity NVARCHAR(50),
            threat NVARCHAR(50),
            ict_index NVARCHAR(50),
            PRIMARY KEY (element_id, season_name)
        );
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_past_seasons (
            element_id INTEGER,
            season_name TEXT,
            start_cost INTEGER,
            end_cost INTEGER,
            total_points INTEGER,
            minutes INTEGER,
            goals_scored INTEGER,
            assists INTEGER,
            clean_sheets INTEGER,
            goals_conceded INTEGER,
            bonus INTEGER,
            bps INTEGER,
            influence TEXT,
            creativity TEXT,
            threat TEXT,
            ict_index TEXT,
            PRIMARY KEY (element_id, season_name)
        );
        """)
    conn.commit()


def create_odds_table(conn):
    cursor = conn.cursor()
    if is_sql_server(conn):
        cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'fixture_odds_snapshots')
        CREATE TABLE fixture_odds_snapshots (
            fixture_id INT,
            event INT,
            home_team NVARCHAR(100),
            away_team NVARCHAR(100),
            snapshot_type NVARCHAR(50),
            home_win_prob FLOAT,
            draw_prob FLOAT,
            away_win_prob FLOAT,
            home_xg FLOAT,
            away_xg FLOAT,
            home_cs_prob FLOAT,
            away_cs_prob FLOAT,
            recorded_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fixture_id, snapshot_type)
        );
        """)
    else:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fixture_odds_snapshots (
            fixture_id INTEGER,
            event INTEGER,
            home_team TEXT,
            away_team TEXT,
            snapshot_type TEXT,
            home_win_prob REAL,
            draw_prob REAL,
            away_win_prob REAL,
            home_xg REAL,
            away_xg REAL,
            home_cs_prob REAL,
            away_cs_prob REAL,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (fixture_id, snapshot_type)
        );
        """)
    conn.commit()


def fetch_all_player_histories(player_ids, engine, conn, session, headers):
    all_history_records = []
    all_past_season_records = []
    total_players = len(player_ids)
    print(f"Fetching match histories and past seasons for {total_players} players...")

    for idx, pid in enumerate(player_ids, start=1):
        url = f"https://fantasy.premierleague.com/api/element-summary/{pid}/"
        try:
            res = session.get(url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for match in data.get("history", []):
                    all_history_records.append({
                        "element_id": match.get("element"),
                        "round": match.get("round"),
                        "fixture_id": match.get("fixture"),
                        "opponent_team": match.get("opponent_team"),
                        "was_home": 1 if match.get("was_home") else 0,
                        "total_points": match.get("total_points", 0),
                        "minutes": match.get("minutes", 0),
                        "goals_scored": match.get("goals_scored", 0),
                        "assists": match.get("assists", 0),
                        "clean_sheets": match.get("clean_sheets", 0),
                        "goals_conceded": match.get("goals_conceded", 0),
                        "expected_goals": str(match.get("expected_goals", "0.0")),
                        "expected_assists": str(match.get("expected_assists", "0.0")),
                        "expected_goal_involvements": str(match.get("expected_goal_involvements", "0.0")),
                        "expected_goals_conceded": str(match.get("expected_goals_conceded", "0.0")),
                        "influence": str(match.get("influence", "0.0")),
                        "creativity": str(match.get("creativity", "0.0")),
                        "threat": str(match.get("threat", "0.0")),
                        "ict_index": str(match.get("ict_index", "0.0")),
                        "bps": match.get("bps", 0),
                        "bonus": match.get("bonus", 0),
                        "value": match.get("value", 0),
                        "transfers_in": match.get("transfers_in", 0),
                        "transfers_out": match.get("transfers_out", 0),
                    })

                for past in data.get("history_past", []):
                    all_past_season_records.append({
                        "element_id": pid,
                        "season_name": past.get("season_name"),
                        "start_cost": past.get("start_cost", 0),
                        "end_cost": past.get("end_cost", 0),
                        "total_points": past.get("total_points", 0),
                        "minutes": past.get("minutes", 0),
                        "goals_scored": past.get("goals_scored", 0),
                        "assists": past.get("assists", 0),
                        "clean_sheets": past.get("clean_sheets", 0),
                        "goals_conceded": past.get("goals_conceded", 0),
                        "bonus": past.get("bonus", 0),
                        "bps": past.get("bps", 0),
                        "influence": str(past.get("influence", "0.0")),
                        "creativity": str(past.get("creativity", "0.0")),
                        "threat": str(past.get("threat", "0.0")),
                        "ict_index": str(past.get("ict_index", "0.0")),
                    })
            elif res.status_code == 404:
                print(f"Player {pid} not found (404), skipping.")
            else:
                print(f"Warning: Player {pid} returned status code {res.status_code}", file=sys.stderr)

            time.sleep(0.05)
        except Exception as e:
            print(f"Error fetching history for player {pid}: {e}", file=sys.stderr)

        if idx % 100 == 0 or idx == total_players:
            print(f"Progress: {idx}/{total_players} players processed.")

    # Truncate and bulk insert cleanly across any DB dialect
    cursor = conn.cursor()
    if all_history_records:
        df_hist = pd.DataFrame(all_history_records)
        cursor.execute("DELETE FROM player_match_history")
        conn.commit()
        df_hist.to_sql("player_match_history", engine, if_exists="append", index=False, chunksize=1000)
        print(f"Successfully upserted {len(all_history_records)} match records into player_match_history.")

    if all_past_season_records:
        df_past = pd.DataFrame(all_past_season_records)
        cursor.execute("DELETE FROM player_past_seasons")
        conn.commit()
        df_past.to_sql("player_past_seasons", engine, if_exists="append", index=False, chunksize=1000)
        print(f"Successfully upserted {len(all_past_season_records)} multi-season records into player_past_seasons.")


def sync_odds_data_with_logging(conn):
    odds_key = get_odds_api_key()
    print("Initiating odds and market line movement snapshot sync...")
    if odds_key:
        masked_key = f"{odds_key[:4]}...{odds_key[-4:]}" if len(odds_key) >= 8 else "***"
        print(f" -> ODDS_API_KEY found ({masked_key}). Querying live market odds from The Odds API...")
    else:
        print(" -> Notice: No ODDS_API_KEY found in environment or secrets. Populating baseline FDR estimates.")

    try:
        from betting_engine import sync_fixture_odds_snapshots
        sync_fixture_odds_snapshots(conn, api_key=odds_key)

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), COUNT(DISTINCT fixture_id) FROM fixture_odds_snapshots")
        row = cursor.fetchone()
        total_snaps, unique_fixtures = row if row else (0, 0)
        print(f" -> Successfully recorded {total_snaps} odds snapshots across {unique_fixtures} upcoming fixtures in 'fixture_odds_snapshots'.")
    except Exception as ex:
        print(f" -> Warning: Odds synchronization encountered an issue: {ex}", file=sys.stderr)


def fetch_transfer_market_data():
    session, headers = get_session_and_headers()
    bootstrap_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    try:
        response = session.get(bootstrap_url, headers=headers, timeout=20)
        if response.status_code == 200:
            bootstrap_res = response.json()
            players_df = pd.DataFrame(bootstrap_res["elements"])
            events_df = pd.DataFrame(bootstrap_res["events"])

            def clean_lists(df):
                return df.map(lambda x: str(x) if isinstance(x, (list, dict)) else x)

            players_df = clean_lists(players_df)
            events_df = clean_lists(events_df)

            engine = get_engine()
            conn = get_connection()
            try:
                players_df.to_sql("players", engine, if_exists="replace", index=False)
                events_df.to_sql("events", engine, if_exists="replace", index=False)
                create_odds_table(conn)
                sync_odds_data_with_logging(conn)
            finally:
                conn.close()

            print("Transfer market data and odds snapshots updated successfully.")
        else:
            print(f"Failed to fetch market data, status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching transfer market data: {e}", file=sys.stderr)


def fetch_data():
    session, headers = get_session_and_headers()

    def get_json(url):
        print(f"Fetching from: {url}")
        try:
            response = session.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"Error: Status code {response.status_code} for {url}", file=sys.stderr)
                response.raise_for_status()
            return response.json()
        except Exception as err:
            print(f"Fetch failed for {url}: {err}", file=sys.stderr)
            raise

    bootstrap_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    bootstrap_res = get_json(bootstrap_url)
    print("Master data retrieved. Processing tables...")

    players_df = pd.DataFrame(bootstrap_res["elements"])
    teams_df = pd.DataFrame(bootstrap_res["teams"])
    positions_df = pd.DataFrame(bootstrap_res["element_types"])
    events_df = pd.DataFrame(bootstrap_res["events"])

    fixtures_url = "https://fantasy.premierleague.com/api/fixtures/"
    fixtures_res = get_json(fixtures_url)
    fixtures_df = pd.DataFrame(fixtures_res)

    def clean_lists(df):
        return df.map(lambda x: str(x) if isinstance(x, (list, dict)) else x)

    players_df = clean_lists(players_df)
    teams_df = clean_lists(teams_df)
    positions_df = clean_lists(positions_df)
    events_df = clean_lists(events_df)
    fixtures_df = clean_lists(fixtures_df)

    engine = get_engine()
    conn = get_connection()

    try:
        print("Writing master data to target database...")
        players_df.to_sql("players", engine, if_exists="replace", index=False)
        teams_df.to_sql("teams", engine, if_exists="replace", index=False)
        positions_df.to_sql("positions", engine, if_exists="replace", index=False)
        events_df.to_sql("events", engine, if_exists="replace", index=False)
        fixtures_df.to_sql("fixtures", engine, if_exists="replace", index=False)

        create_history_table(conn)
        create_past_seasons_table(conn)
        create_odds_table(conn)

        player_ids = players_df["id"].tolist()
        fetch_all_player_histories(player_ids, engine, conn, session, headers)
        sync_odds_data_with_logging(conn)

        print("Database sync completed successfully!")
    finally:
        conn.close()


def get_rolling_match_stats(window=5):
    query = f"""
    WITH ranked_matches AS (
      SELECT
        h.element_id,
        p.web_name AS player_name,
        t.short_name AS team_name,
        pos.singular_name_short AS position,
        p.now_cost / 10.0 AS price,
        h.round AS gameweek,
        h.total_points,
        h.minutes,
        CAST(h.expected_goal_involvements AS FLOAT) AS xgi,
        AVG(h.total_points) OVER (
          PARTITION BY h.element_id
          ORDER BY h.round
          ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW
        ) AS rolling_avg_points,
        SUM(CAST(h.expected_goal_involvements AS FLOAT)) OVER (
          PARTITION BY h.element_id
          ORDER BY h.round
          ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW
        ) AS rolling_sum_xgi,
        AVG(h.minutes) OVER (
          PARTITION BY h.element_id
          ORDER BY h.round
          ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW
        ) AS rolling_avg_minutes,
        ROW_NUMBER() OVER (
          PARTITION BY h.element_id
          ORDER BY h.round DESC
        ) AS rn
      FROM player_match_history h
      INNER JOIN players p ON h.element_id = p.id
      INNER JOIN teams t ON p.team = t.id
      INNER JOIN positions pos ON p.element_type = pos.id
    )
    SELECT
      element_id,
      player_name,
      team_name,
      position,
      price,
      gameweek AS latest_gw,
      ROUND(rolling_avg_points, 2) AS rolling_avg_pts,
      ROUND(rolling_sum_xgi, 2) AS rolling_sum_xgi,
      ROUND(rolling_avg_minutes, 1) AS rolling_avg_mins
    FROM ranked_matches
    WHERE rn = 1
    ORDER BY rolling_sum_xgi DESC;
    """
    engine = get_engine()
    return pd.read_sql(query, engine)


def fetch_all_data():
    fetch_data()


def main():
    fetch_data()


if __name__ == "__main__":
    fetch_data()