import sqlite3
import sys
import time
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


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
    """Creates the match-by-match history table if it does not exist."""
    cursor = conn.cursor()
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
    """Creates the multi-season summary table for historical baselines."""
    cursor = conn.cursor()
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
    """Creates the odds movement snapshot table tracking opening vs current lines."""
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fixture_odds_snapshots (
        fixture_id INTEGER,
        event INTEGER,
        home_team TEXT,
        away_team TEXT,
        snapshot_type TEXT, -- 'OPENING' or 'CURRENT'
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


def fetch_all_player_histories(player_ids, conn, session, headers):
    """Fetches element-summary histories and multi-season aggregates for all player IDs."""
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
                
                # 1. Current Season Match-by-Match Logs
                history_list = data.get("history", [])
                for match in history_list:
                    all_history_records.append((
                        match.get("element"),
                        match.get("round"),
                        match.get("fixture"),
                        match.get("opponent_team"),
                        1 if match.get("was_home") else 0,
                        match.get("total_points", 0),
                        match.get("minutes", 0),
                        match.get("goals_scored", 0),
                        match.get("assists", 0),
                        match.get("clean_sheets", 0),
                        match.get("goals_conceded", 0),
                        str(match.get("expected_goals", "0.0")),
                        str(match.get("expected_assists", "0.0")),
                        str(match.get("expected_goal_involvements", "0.0")),
                        str(match.get("expected_goals_conceded", "0.0")),
                        str(match.get("influence", "0.0")),
                        str(match.get("creativity", "0.0")),
                        str(match.get("threat", "0.0")),
                        str(match.get("ict_index", "0.0")),
                        match.get("bps", 0),
                        match.get("bonus", 0),
                        match.get("value", 0),
                        match.get("transfers_in", 0),
                        match.get("transfers_out", 0),
                    ))

                # 2. Previous Seasons Aggregated Totals
                past_seasons_list = data.get("history_past", [])
                for past in past_seasons_list:
                    all_past_season_records.append((
                        pid,
                        past.get("season_name"),
                        past.get("start_cost", 0),
                        past.get("end_cost", 0),
                        past.get("total_points", 0),
                        past.get("minutes", 0),
                        past.get("goals_scored", 0),
                        past.get("assists", 0),
                        past.get("clean_sheets", 0),
                        past.get("goals_conceded", 0),
                        past.get("bonus", 0),
                        past.get("bps", 0),
                        str(past.get("influence", "0.0")),
                        str(past.get("creativity", "0.0")),
                        str(past.get("threat", "0.0")),
                        str(past.get("ict_index", "0.0")),
                    ))
            elif res.status_code == 404:
                print(f"Player {pid} not found (404), skipping.")
            else:
                print(
                    f"Warning: Player {pid} returned status code {res.status_code}",
                    file=sys.stderr,
                )

            time.sleep(0.05)

        except Exception as e:
            print(f"Error fetching history for player {pid}: {e}", file=sys.stderr)

        if idx % 100 == 0 or idx == total_players:
            print(f"Progress: {idx}/{total_players} players processed.")

    cursor = conn.cursor()
    if all_history_records:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO player_match_history (
                element_id, round, fixture_id, opponent_team, was_home,
                total_points, minutes, goals_scored, assists, clean_sheets,
                goals_conceded, expected_goals, expected_assists,
                expected_goal_involvements, expected_goals_conceded,
                influence, creativity, threat, ict_index, bps, bonus,
                value, transfers_in, transfers_out
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            all_history_records,
        )
        print(f"Successfully upserted {len(all_history_records)} match records into player_match_history.")

    if all_past_season_records:
        cursor.executemany(
            """
            INSERT OR REPLACE INTO player_past_seasons (
                element_id, season_name, start_cost, end_cost, total_points,
                minutes, goals_scored, assists, clean_sheets, goals_conceded,
                bonus, bps, influence, creativity, threat, ict_index
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            all_past_season_records,
        )
        print(f"Successfully upserted {len(all_past_season_records)} multi-season records into player_past_seasons.")

    conn.commit()


def fetch_transfer_market_data(db_path="fpl.db"):
    """Lightweight sync: Updates players, events, and records odds snapshots."""
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

            with sqlite3.connect(db_path) as conn:
                players_df.to_sql("players", conn, if_exists="replace", index=False)
                events_df.to_sql("events", conn, if_exists="replace", index=False)
                create_odds_table(conn)
                
                try:
                    from betting_engine import sync_fixture_odds_snapshots
                    sync_fixture_odds_snapshots(conn)
                except Exception as ex:
                    print(f"Notice: Odds snapshot skipped: {ex}")

            print("Transfer market data and odds snapshots updated successfully.")
        else:
            print(f"Failed to fetch market data, status code: {response.status_code}")
    except Exception as e:
        print(f"Error fetching transfer market data: {e}", file=sys.stderr)


def fetch_data(db_path="fpl.db"):
    """Full sync: Fetches master data, fixtures, match histories, and initializes odds movement."""
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

    # 1. Fetch Master Data
    bootstrap_url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    bootstrap_res = get_json(bootstrap_url)
    print("Master data retrieved. Processing tables...")

    players_df = pd.DataFrame(bootstrap_res["elements"])
    teams_df = pd.DataFrame(bootstrap_res["teams"])
    positions_df = pd.DataFrame(bootstrap_res["element_types"])
    events_df = pd.DataFrame(bootstrap_res["events"])

    # 2. Fetch Fixtures
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

    # 3. Save Master Tables to SQLite
    print(f"Writing master data to {db_path}...")
    conn = sqlite3.connect(db_path)
    try:
        players_df.to_sql("players", conn, if_exists="replace", index=False)
        teams_df.to_sql("teams", conn, if_exists="replace", index=False)
        positions_df.to_sql("positions", conn, if_exists="replace", index=False)
        events_df.to_sql("events", conn, if_exists="replace", index=False)
        fixtures_df.to_sql("fixtures", conn, if_exists="replace", index=False)

        # 4. Create History, Past Seasons, and Odds Tables
        create_history_table(conn)
        create_past_seasons_table(conn)
        create_odds_table(conn)

        player_ids = players_df["id"].tolist()
        fetch_all_player_histories(player_ids, conn, session, headers)

        # 5. Snapshot Odds Movement
        try:
            from betting_engine import sync_fixture_odds_snapshots
            sync_fixture_odds_snapshots(conn)
        except Exception as ex:
            print(f"Notice: Odds snapshot skipped: {ex}")

        print("Database sync completed successfully!")
    finally:
        conn.close()


def get_rolling_match_stats(db_path="fpl.db", window=5):
    """Computes rolling N-gameweek metrics per player using SQL window functions."""
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
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql(query, conn)


def fetch_all_data():
    fetch_data()


def main():
    fetch_data()


if __name__ == "__main__":
    fetch_data()