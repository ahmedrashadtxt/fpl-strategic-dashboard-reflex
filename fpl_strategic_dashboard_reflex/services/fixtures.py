import pandas as pd
from rapidfuzz import fuzz, process
from fpl_strategic_dashboard_reflex.services.db import get_connection, get_manager_squad_ids

def _build_ticker_rows(
    current_gw: int,
    search_query: str,
    only_my_squad: bool,
    manager_id: str,
) -> list[dict]:
    """
    Pure-Python version of the Streamlit fixture ticker logic.
    Returns a list of row dicts serialisable to rx.State.

    Each row dict:
        short_name, full_name, code, difficulty_rating, my_players,
        gw_cells: list[{gw, diff, label}]
    """
    gw_cols = list(range(current_gw, current_gw + 5))
    conn = get_connection()

    # 1. Fixtures for the 5-GW window
    fixtures_df = pd.read_sql(
        """
        SELECT f.event AS GW, th.short_name AS Home_Team, ta.short_name AS Away_Team,
               f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
        FROM fixtures f
        INNER JOIN teams th ON f.team_h = th.id
        INNER JOIN teams ta ON f.team_a = ta.id
        WHERE f.event >= ? AND f.event < ? AND f.finished = 0
        ORDER BY f.event ASC
        """,
        conn,
        params=[current_gw, current_gw + 5],
    )

    # 2. Teams master
    teams_df = pd.read_sql(
        "SELECT id, code, short_name, name FROM teams ORDER BY name", conn
    )
    teams_list = teams_df["short_name"].tolist()
    team_name_map = dict(zip(teams_df["short_name"], teams_df["name"]))
    team_code_map = dict(zip(teams_df["short_name"], teams_df["code"]))

    # 3. Player-team lookup (for search & squad filter)
    pt_lookup = pd.read_sql(
        """
        SELECT p.id AS element_id, p.web_name,
               p.first_name || ' ' || p.second_name AS full_name,
               t.short_name, t.name AS club_name
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        """,
        conn,
    )

    target_teams: set | list = set(teams_list)
    team_players_map: dict = {}

    # 4. Optional: squad-only filter
    if only_my_squad:
        if not manager_id:
            return []  # caller shows info message
        squad_ids = get_manager_squad_ids(manager_id, current_gw)
        squad_df = pt_lookup[pt_lookup["element_id"].isin(squad_ids)]
        target_teams = target_teams.intersection(set(squad_df["short_name"].unique()))
        team_players_map = (
            squad_df.groupby("short_name")["web_name"]
            .apply(lambda s: ", ".join(s))
            .to_dict()
        )

    # 5. Build full-text search corpus per team
    all_team_players = (
        pt_lookup.groupby("short_name")["web_name"]
        .apply(lambda s: " ".join(s))
        .to_dict()
    )
    club_search_dict = {
        t: f"{t} {team_name_map.get(t, '')} {all_team_players.get(t, '')}"
        for t in target_teams
    }

    search_relevance: dict[str, int] = {}
    has_search = bool(search_query and search_query.strip())

    if has_search:
        matches = process.extract(
            query=search_query.strip(),
            choices=club_search_dict,
            scorer=fuzz.WRatio,
            score_cutoff=55,
            limit=20,
        )
        if matches:
            target_teams = [m[2] for m in matches]
            search_relevance = {team: idx for idx, team in enumerate(target_teams)}
        else:
            return []

    # 6. Build per-team rows
    rows: list[dict] = []
    for team in teams_list:
        if team not in target_teams:
            continue

        gw_cells: list[dict] = []
        total_diff = 0

        for gw in gw_cols:
            match = fixtures_df[
                (fixtures_df["GW"] == gw)
                & (
                    (fixtures_df["Home_Team"] == team)
                    | (fixtures_df["Away_Team"] == team)
                )
            ]
            if not match.empty:
                m = match.iloc[0]
                if m["Home_Team"] == team:
                    opp = f"{m['Away_Team']} (H)"
                    diff = int(m["Home_Diff"])
                else:
                    opp = f"{m['Home_Team']} (A)"
                    diff = int(m["Away_Diff"])
                label = f"[{diff}] {opp}"
                is_blank = False
            else:
                diff = 5
                label = "Blank"
                is_blank = True

            total_diff += diff
            # Store flattened so we avoid nested list[dict] inside list[dict]
            # (Reflex foreach can't type-check nested Any lists)
            slot = len(gw_cells)  # 0..4
            row_flat_key_diff = f"gw{slot}_diff"
            row_flat_key_label = f"gw{slot}_label"
            row_flat_key_blank = f"gw{slot}_blank"
            gw_cells.append({
                "diff_key": row_flat_key_diff,
                "label_key": row_flat_key_label,
                "blank_key": row_flat_key_blank,
                "diff": diff,
                "label": label,
                "is_blank": is_blank,
            })

        # Build a flat dict — no nested lists
        flat_row: dict = {
            "short_name": team,
            "full_name": team_name_map.get(team, team),
            "code": int(team_code_map.get(team, 0)),
            "difficulty_rating": total_diff,
            "my_players": team_players_map.get(team, "—"),
        }
        for i, cell in enumerate(gw_cells):
            flat_row[f"gw{i}_diff"] = cell["diff"]
            flat_row[f"gw{i}_label"] = cell["label"]
            flat_row[f"gw{i}_blank"] = cell["is_blank"]

        rows.append(flat_row)

    # 7. Sort
    if has_search:
        rows.sort(key=lambda r: search_relevance.get(r["short_name"], 999))
    else:
        rows.sort(key=lambda r: r["difficulty_rating"])

    return rows


# ── State ─────────────────────────────────────────────────────────────────────
