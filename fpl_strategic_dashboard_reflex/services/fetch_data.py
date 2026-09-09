"""Official FPL API Data Ingestion and Synchronization Engine.
Fetches bootstrap data, fixtures, player match histories, and past seasons.
Completely decoupled from Streamlit.
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from fpl_strategic_dashboard_reflex.services.db import get_connection


def get_odds_api_key() -> str:
    return os.getenv("ODDS_API_KEY", "").strip()


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
        saves INTEGER,
        bonus INTEGER,
        bps INTEGER,
        PRIMARY KEY (element_id, round, fixture_id)
    );
    """)
    conn.commit()


def create_past_seasons_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_past_seasons (
        element_id INTEGER,
        season_name TEXT,
        total_points INTEGER,
        minutes INTEGER,
        goals_scored INTEGER,
        assists INTEGER,
        clean_sheets INTEGER,
        goals_conceded INTEGER,
        bps INTEGER,
        influence TEXT,
        creativity TEXT,
        threat TEXT,
        ict_index TEXT,
        start_cost INTEGER,
        end_cost INTEGER,
        PRIMARY KEY (element_id, season_name)
    );
    """)
    conn.commit()


def fetch_data():
    """Fetches base bootstrap and fixtures data, saving into SQLite."""
    conn = get_connection()
    session, headers = get_session_and_headers()

    url = "https://fantasy.premierleague.com/api/bootstrap-static/"
    response = session.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        print(f"Error fetching bootstrap data: {response.status_code}")
        return

    data = response.json()
    players = pd.DataFrame(data["elements"])
    teams = pd.DataFrame(data["teams"])
    positions = pd.DataFrame(data["element_types"])
    events = pd.DataFrame(data["events"])

    fix_url = "https://fantasy.premierleague.com/api/fixtures/"
    fix_res = session.get(fix_url, headers=headers, timeout=15)
    fixtures = pd.DataFrame(fix_res.json()) if fix_res.status_code == 200 else pd.DataFrame()

    with conn:
        players.to_sql("players", conn, if_exists="replace", index=False)
        teams.to_sql("teams", conn, if_exists="replace", index=False)
        positions.to_sql("positions", conn, if_exists="replace", index=False)
        events.to_sql("events", conn, if_exists="replace", index=False)
        if not fixtures.empty:
            fixtures.to_sql("fixtures", conn, if_exists="replace", index=False)

    create_history_table(conn)
    create_past_seasons_table(conn)
    print("Base FPL data synced successfully.")


def fetch_all_data():
    """Full database sync."""
    fetch_data()


def main():
    fetch_all_data()


if __name__ == "__main__":
    main()

