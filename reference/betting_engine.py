import math
import os
import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import streamlit as st

TEAM_MAP = {
  "Arsenal": "ARS", "Arsenal FC": "ARS",
  "Aston Villa": "AVL", "Aston Villa FC": "AVL",
  "Bournemouth": "BOU", "AFC Bournemouth": "BOU",
  "Brentford": "BRE", "Brentford FC": "BRE",
  "Brighton": "BHA", "Brighton and Hove Albion": "BHA", "Brighton & Hove Albion": "BHA",
  "Chelsea": "CHE", "Chelsea FC": "CHE",
  "Crystal Palace": "CRY", "Crystal Palace FC": "CRY",
  "Everton": "EVE", "Everton FC": "EVE",
  "Fulham": "FUL", "Fulham FC": "FUL",
  "Ipswich": "IPS", "Ipswich Town": "IPS", "Ipswich Town FC": "IPS",
  "Leicester": "LEI", "Leicester City": "LEI", "Leicester City FC": "LEI",
  "Liverpool": "LIV", "Liverpool FC": "LIV",
  "Man City": "MCI", "Manchester City": "MCI", "Manchester City FC": "MCI",
  "Man United": "MUN", "Man Utd": "MUN", "Manchester United": "MUN", "Manchester United FC": "MUN",
  "Newcastle": "NEW", "Newcastle United": "NEW", "Newcastle United FC": "NEW",
  "Nott'm Forest": "NFO", "Nottingham Forest": "NFO", "Nottingham Forest FC": "NFO",
  "Southampton": "SOU", "Southampton FC": "SOU",
  "Spurs": "TOT", "Tottenham": "TOT", "Tottenham Hotspur": "TOT",
  "West Ham": "WHU", "West Ham United": "WHU", "West Ham United FC": "WHU",
  "Wolves": "WOL", "Wolverhampton": "WOL", "Wolverhampton Wanderers": "WOL"
}


def is_sql_server(conn) -> bool:
  """Detects whether the connection is targeting Azure SQL (pyodbc/pymssql) or SQLite."""
  mod = type(conn).__module__.lower()
  return "pyodbc" in mod or "pymssql" in mod or "mssql" in mod


def init_odds_table(conn):
  """Dialect-agnostic table initializer for odds snapshots."""
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


# ── De-vigging ────────────────────────────────────────────────────────────────
def devig_basic(odds_list: list[float]) -> list[float]:
  raw = [1.0 / max(o, 1.001) for o in odds_list]
  total = sum(raw)
  return [p / total for p in raw] if total > 0 else [1.0 / len(odds_list)] * len(odds_list)


# ── Poisson Matrix & Goal Estimation ──────────────────────────────────────────
def poisson_prob(k: int, lamb: float) -> float:
  return (math.exp(-lamb) * (lamb ** k)) / math.factorial(k)


def score_matrix(l_h: float, l_a: float, max_g: int = 7) -> np.ndarray:
  h_probs = np.array([poisson_prob(i, l_h) for i in range(max_g + 1)])
  a_probs = np.array([poisson_prob(j, l_a) for j in range(max_g + 1)])
  mat = np.outer(h_probs, a_probs)

  rho = -0.05
  if mat.shape[0] > 1 and mat.shape[1] > 1:
    mat[0, 0] *= max(0.0, 1.0 - l_h * l_a * rho)
    mat[0, 1] *= max(0.0, 1.0 + l_h * rho)
    mat[1, 0] *= max(0.0, 1.0 + l_a * rho)
    mat[1, 1] *= max(0.0, 1.0 - rho)
  return mat / mat.sum()


def derive_lambdas_from_odds(
  home_odds: float,
  draw_odds: float,
  away_odds: float,
  over_25_odds: float = 1.90,
  under_25_odds: float = 1.95,
) -> tuple[float, float, float, float, float, float, float]:
  p_h, p_d, p_a = devig_basic([home_odds, draw_odds, away_odds])
  p_over, _ = devig_basic([over_25_odds, under_25_odds])

  def loss(lambdas):
    lh, la = max(lambdas[0], 0.1), max(lambdas[1], 0.1)
    mat = score_matrix(lh, la)
    sim_h = np.sum(np.tril(mat, -1))
    sim_d = np.sum(np.diag(mat))
    sim_a = np.sum(np.triu(mat, 1))
    sim_over = sum(mat[r, c] for r in range(mat.shape[0]) for c in range(mat.shape[1]) if r + c >= 3)
    return (sim_h - p_h) ** 2 + (sim_d - p_d) ** 2 + (sim_a - p_a) ** 2 + 0.5 * (sim_over - p_over) ** 2

  res = minimize(loss, [1.5, 1.1], bounds=[(0.2, 4.0), (0.2, 4.0)], method="L-BFGS-B")
  lh, la = round(float(res.x[0]), 2), round(float(res.x[1]), 2)
  cs_home = round(math.exp(-la), 2)
  cs_away = round(math.exp(-lh), 2)

  return lh, la, cs_home, cs_away, round(p_h, 3), round(p_d, 3), round(p_a, 3)


# ── Live API Fetcher ──────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_upcoming_betting_odds(api_key: str = "") -> dict:
  odds_lookup = {}
  if not api_key:
    return odds_lookup

  try:
    url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/"
    params = {
      "apiKey": api_key,
      "regions": "uk,eu",
      "markets": "h2h,totals",
      "oddsFormat": "decimal",
    }
    res = requests.get(url, params=params, timeout=8)
    if res.status_code == 200:
      for game in res.json():
        h_team = TEAM_MAP.get(game.get("home_team"))
        a_team = TEAM_MAP.get(game.get("away_team"))
        if not (h_team and a_team):
          continue

        h_odds, d_odds, a_odds, o25_odds, u25_odds = [], [], [], [], []
        for bookmaker in game.get("bookmakers", []):
          for mkt in bookmaker.get("markets", []):
            if mkt["key"] == "h2h":
              for outcome in mkt.get("outcomes", []):
                if outcome["name"] == game["home_team"]:
                  h_odds.append(outcome["price"])
                elif outcome["name"] == "Draw":
                  d_odds.append(outcome["price"])
                elif outcome["name"] == game["away_team"]:
                  a_odds.append(outcome["price"])
            elif mkt["key"] == "totals":
              for outcome in mkt.get("outcomes", []):
                if outcome["name"] == "Over" and outcome.get("point") == 2.5:
                  o25_odds.append(outcome["price"])
                elif outcome["name"] == "Under" and outcome.get("point") == 2.5:
                  u25_odds.append(outcome["price"])

        if h_odds and d_odds and a_odds:
          lh, la, cs_h, cs_a, ph, pd_, pa = derive_lambdas_from_odds(
            float(np.median(h_odds)),
            float(np.median(d_odds)),
            float(np.median(a_odds)),
            float(np.median(o25_odds)) if o25_odds else 1.90,
            float(np.median(u25_odds)) if u25_odds else 1.95,
          )
          odds_lookup[f"{h_team}_{a_team}"] = {
            "home_xg": lh,
            "away_xg": la,
            "home_cs": cs_h,
            "away_cs": cs_a,
            "p_home": ph,
            "p_draw": pd_,
            "p_away": pa,
            "market_found": True,
          }
  except Exception:
    pass

  return odds_lookup


# ── Database Read (Zero API Cost, In-Memory Cached) ───────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_db_market_odds(_conn) -> dict:
  """Reads both CURRENT and OPENING market snapshots into memory."""
  query = """
  SELECT home_team, away_team, snapshot_type, home_win_prob, draw_prob, away_win_prob,
      home_xg, away_xg, home_cs_prob, away_cs_prob
  FROM fixture_odds_snapshots
  """
  try:
    df = pd.read_sql(query, _conn)
    if df.empty:
      return {}

    lookup = {}
    for _, r in df.iterrows():
      key = f"{r['home_team']}_{r['away_team']}"
      stype = str(r["snapshot_type"]).upper()
      if key not in lookup:
        lookup[key] = {}

      lookup[key][stype] = {
        "home_xg": float(r["home_xg"]),
        "away_xg": float(r["away_xg"]),
        "home_cs": float(r["home_cs_prob"]),
        "away_cs": float(r["away_cs_prob"]),
        "p_home": float(r["home_win_prob"]),
        "p_draw": float(r["draw_prob"]),
        "p_away": float(r["away_win_prob"]),
        "market_found": True,
      }

    flat_lookup = {}
    for key, snapshots in lookup.items():
      curr = snapshots.get("CURRENT", snapshots.get("OPENING", {}))
      opn = snapshots.get("OPENING", curr)
      if curr:
        entry = dict(curr)
        entry["open_home_xg"] = opn.get("home_xg", curr.get("home_xg", 1.4))
        entry["open_away_xg"] = opn.get("away_xg", curr.get("away_xg", 1.2))
        entry["open_p_home"] = opn.get("p_home", curr.get("p_home", 0.45))
        entry["open_p_away"] = opn.get("p_away", curr.get("p_away", 0.27))
        flat_lookup[key] = entry

    return flat_lookup
  except Exception:
    return {}


# ── Cooldown-Protected Sync Function ──────────────────────────────────────────
def sync_fixture_odds_with_cooldown(conn, api_key: str = "", min_interval_hours: int = 6) -> bool:
  """Syncs live odds to DB only if the last recorded snapshot is older than min_interval_hours."""
  if not api_key:
    return False

  cursor = conn.cursor()
  try:
    cursor.execute("""
      SELECT MAX(recorded_at)
      FROM fixture_odds_snapshots
      WHERE snapshot_type = 'CURRENT'
    """)
    row = cursor.fetchone()
    if row and row[0]:
      last_sync = pd.to_datetime(row[0], utc=True)
      now = pd.Timestamp.now(tz="UTC")
      if (now - last_sync).total_seconds() < min_interval_hours * 3600:
        return False
  except Exception:
    pass

  sync_fixture_odds_snapshots(conn, api_key)
  return True


# ── Snapshot Persistence (Opening vs Current) ─────────────────────────────────
def sync_fixture_odds_snapshots(conn, api_key: str = ""):
  """Records initial odds as 'OPENING' (preserved) and upserts latest odds as 'CURRENT'."""
  init_odds_table(conn)
  cursor = conn.cursor()

  fixtures_query = """
  SELECT f.id, f.event, th.short_name AS home_team, ta.short_name AS away_team,
      f.team_h_difficulty, f.team_a_difficulty
  FROM fixtures f
  INNER JOIN teams th ON f.team_h = th.id
  INNER JOIN teams ta ON f.team_a = ta.id
  WHERE f.finished = 0 AND f.event IS NOT NULL
  ORDER BY f.event ASC, f.id ASC
  """
  fixtures_df = pd.read_sql(fixtures_query, conn)
  live_odds = fetch_upcoming_betting_odds(api_key)

  for _, fix in fixtures_df.iterrows():
    fix_id = int(fix["id"])
    event = int(fix["event"])
    h_team = fix["home_team"]
    a_team = fix["away_team"]
    fdr_h = int(fix["team_h_difficulty"])
    fdr_a = int(fix["team_a_difficulty"])

    key = f"{h_team}_{a_team}"
    if key in live_odds:
      od = live_odds[key]
      h_xg, a_xg, h_cs, a_cs = od["home_xg"], od["away_xg"], od["home_cs"], od["away_cs"]
      p_h, p_d, p_a = od["p_home"], od["p_draw"], od["p_away"]
    else:
      fdr_to_xg = {1: 2.30, 2: 2.05, 3: 1.45, 4: 1.05, 5: 0.70}
      h_xg = round(fdr_to_xg.get(fdr_a, 1.40) * 1.12, 2)
      a_xg = round(fdr_to_xg.get(fdr_h, 1.30) * 0.90, 2)
      h_cs = round(math.exp(-a_xg), 2)
      a_cs = round(math.exp(-h_xg), 2)
      p_h, p_d, p_a = 0.45, 0.28, 0.27

    # 1. Preserve OPENING line
    cursor.execute(
      "SELECT 1 FROM fixture_odds_snapshots WHERE fixture_id = ? AND snapshot_type = 'OPENING'",
      (fix_id,),
    )
    if not cursor.fetchone():
      cursor.execute(
        """
        INSERT INTO fixture_odds_snapshots (
          fixture_id, event, home_team, away_team, snapshot_type,
          home_win_prob, draw_prob, away_win_prob, home_xg, away_xg,
          home_cs_prob, away_cs_prob
        ) VALUES (?, ?, ?, ?, 'OPENING', ?, ?, ?, ?, ?, ?, ?)
        """,
        (fix_id, event, h_team, a_team, p_h, p_d, p_a, h_xg, a_xg, h_cs, a_cs),
      )

    # 2. Universal Upsert for CURRENT line (works on both T-SQL and SQLite)
    cursor.execute(
      "DELETE FROM fixture_odds_snapshots WHERE fixture_id = ? AND snapshot_type = 'CURRENT'",
      (fix_id,),
    )
    cursor.execute(
      """
      INSERT INTO fixture_odds_snapshots (
        fixture_id, event, home_team, away_team, snapshot_type,
        home_win_prob, draw_prob, away_win_prob, home_xg, away_xg,
        home_cs_prob, away_cs_prob, recorded_at
      ) VALUES (?, ?, ?, ?, 'CURRENT', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
      """,
      (fix_id, event, h_team, a_team, p_h, p_d, p_a, h_xg, a_xg, h_cs, a_cs),
    )

  conn.commit()


# ── Unified Market & Movement Retriever ───────────────────────────────────────
def get_fixture_market_xg_and_movement(
  conn,
  home_team: str,
  away_team: str,
  fdr_h: int,
  fdr_a: int,
  market_odds_cache: dict,
) -> tuple[float, float, float, float, dict]:
  key = f"{home_team}_{away_team}"
  if key in market_odds_cache:
    d = market_odds_cache[key]
    curr_h_xg, curr_a_xg, curr_h_cs, curr_a_cs = d["home_xg"], d["away_xg"], d["home_cs"], d["away_cs"]
    curr_p_h, curr_p_a = d["p_home"], d["p_away"]
    open_h_xg = d.get("open_home_xg", curr_h_xg)
    open_a_xg = d.get("open_away_xg", curr_a_xg)
    open_p_h = d.get("open_p_home", curr_p_h)
    open_p_a = d.get("open_p_away", curr_p_a)
  else:
    fdr_to_xg = {1: 2.30, 2: 2.05, 3: 1.45, 4: 1.05, 5: 0.70}
    curr_h_xg = round(fdr_to_xg.get(fdr_a, 1.40) * 1.12, 2)
    curr_a_xg = round(fdr_to_xg.get(fdr_h, 1.30) * 0.90, 2)
    curr_h_cs = round(math.exp(-curr_a_xg), 2)
    curr_a_cs = round(math.exp(-curr_h_xg), 2)
    curr_p_h, curr_p_a = 0.45, 0.27
    open_h_xg, open_a_xg = curr_h_xg, curr_a_xg
    open_p_h, open_p_a = curr_p_h, curr_p_a

  delta_h_xg = round(curr_h_xg - open_h_xg, 2)
  delta_a_xg = round(curr_a_xg - open_a_xg, 2)
  delta_h_p = round(curr_p_h - open_p_h, 3)
  delta_a_p = round(curr_p_a - open_p_a, 3)

  def classify(dxg, dp):
    if dxg >= 0.20 or dp >= 0.05:
      return "Steam ↑", "Lineup / Leak Target"
    elif dxg <= -0.20 or dp <= -0.05:
      return "Drift ↓", "Rotation / Fade Risk"
    return "Stable —", "Fair Value"

  h_move, h_note = classify(delta_h_xg, delta_h_p)
  a_move, a_note = classify(delta_a_xg, delta_a_p)

  movement = {
    "home": {
      "open_xg": open_h_xg,
      "curr_xg": curr_h_xg,
      "delta_xg": delta_h_xg,
      "delta_win": delta_h_p,
      "trend": h_move,
      "note": h_note,
    },
    "away": {
      "open_xg": open_a_xg,
      "curr_xg": curr_a_xg,
      "delta_xg": delta_a_xg,
      "delta_win": delta_a_p,
      "trend": a_move,
      "note": a_note,
    },
  }

  return curr_h_xg, curr_a_xg, curr_h_cs, curr_a_cs, movement