import re
import unicodedata
import pandas as pd
from rapidfuzz import fuzz
from fpl_strategic_dashboard_reflex.services.db import get_connection, get_manager_squad_ids
from fpl_strategic_dashboard_reflex.services.cache import ttl_cache

TEAM_ALIASES: dict[str, list[str]] = {
    "ARS": ["arsenal", "gunners"],
    "AVL": ["aston villa", "villa"],
    "BOU": ["bournemouth", "afc bournemouth", "cherries"],
    "BRE": ["brentford", "bees"],
    "BHA": ["brighton", "brighton and hove albion", "seagulls"],
    "CHE": ["chelsea", "blues"],
    "COV": ["coventry", "coventry city", "sky blues"],
    "CRY": ["crystal palace", "palace", "eagles"],
    "EVE": ["everton", "toffees"],
    "FUL": ["fulham", "cottagers"],
    "HUL": ["hull", "hull city", "tigers"],
    "IPS": ["ipswich", "ipswich town", "tractor boys"],
    "LEE": ["leeds", "leeds united", "whites"],
    "LIV": ["liverpool", "reds"],
    "MCI": ["man city", "manchester city", "city", "citizens"],
    "MUN": ["man utd", "man united", "manchester united", "united", "utd", "red devils"],
    "NEW": ["newcastle", "newcastle united", "magpies", "toon"],
    "NFO": ["nottingham forest", "forest", "nottm forest", "nott'm forest"],
    "TOT": ["spurs", "tottenham", "tottenham hotspur"],
    "SUN": ["sunderland", "black cats"],
    "WHU": ["west ham", "west ham united", "hammers", "irons"],
    "WOL": ["wolves", "wolverhampton", "wolverhampton wanderers"],
    "LEI": ["leicester", "leicester city", "foxes"],
    "SOU": ["southampton", "saints"],
}


def _normalize_str(text: str) -> str:
    if not text:
        return ""
    text = (
        text.replace("Ø", "O")
        .replace("ø", "o")
        .replace("Æ", "Ae")
        .replace("æ", "ae")
    )
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .lower()
        .strip()
    )


def _get_words(text: str) -> list[str]:
    return [w for w in re.split(r"[^a-zA-Z0-9]+", text) if w]


def _score_team(
    team_code: str,
    q: str,
    team_name: str,
    players: list[dict],
) -> int:
    t_norm = _normalize_str(team_code)
    name_norm = _normalize_str(team_name)
    aliases_norm = [_normalize_str(a) for a in TEAM_ALIASES.get(team_code, [])]

    # 1. Exact matches on team code, name, or aliases
    if q == t_norm or q == name_norm:
        return 100
    if q in aliases_norm:
        return 98

    # 2. Prefix matches on team code, name, or aliases
    if t_norm.startswith(q) or name_norm.startswith(q):
        return 95
    for a in aliases_norm:
        if a.startswith(q):
            return 92

    # 3. Substring in team name or alias
    if q in name_norm:
        return 90
    for a in aliases_norm:
        if q in a:
            return 88

    # 4. Word-prefix matches on team name / alias words
    team_words = _get_words(name_norm)
    for a in aliases_norm:
        team_words.extend(_get_words(a))
    if any(w.startswith(q) for w in team_words):
        return 90

    # 5. Player matches
    for p in players:
        p_web = p["web_norm"]
        p_full = p["full_norm"]
        p_words = p["words"]

        # Exact player name match
        if q == p_web or q == p_full or q in p_words:
            return 85

        # Prefix match on any word in player's name (e.g. 'timber' -> 'J.Timber', 'saka' -> 'Saka')
        if any(w.startswith(q) for w in p_words):
            return 80

        # If query has spaces (e.g. 'alexander arnold' or 'de bruyne'), check substring in full name
        if " " in q and q in p_full:
            return 80

    # 6. Fuzzy match fallback
    # Team name & aliases
    best_fuzzy = fuzz.ratio(q, name_norm)
    for a in aliases_norm:
        best_fuzzy = max(best_fuzzy, fuzz.ratio(q, a))
    if best_fuzzy >= 75:
        return int(best_fuzzy * 0.75)

    # Player fuzzy match (only if query >= 4 chars and ratio >= 85)
    if len(q) >= 4:
        for p in players:
            for w in p["words"]:
                if len(w) >= 4 and fuzz.ratio(q, w) >= 85:
                    return 60

    return 0


def _search_teams(
    query: str,
    candidate_teams: list[str],
    team_name_map: dict[str, str],
    team_players_search: dict[str, list[dict]],
) -> list[str]:
    norm_q = _normalize_str(query)
    if not norm_q:
        return candidate_teams

    scored: list[tuple[str, int]] = []
    for t in candidate_teams:
        score = _score_team(
            t,
            norm_q,
            team_name_map.get(t, ""),
            team_players_search.get(t, []),
        )
        if score > 0:
            scored.append((t, score))

    if not scored:
        return []

    max_score = max(s for _, s in scored)
    # If we have strong matches (>= 75), drop weak fuzzy matches (< 70)
    if max_score >= 75:
        scored = [(t, s) for t, s in scored if s >= 70]

    # Sort descending by score
    scored.sort(key=lambda x: -x[1])
    return [t for t, _ in scored]


@ttl_cache(ttl_seconds=300)
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

    # 5. Search filter & relevance scoring
    search_relevance: dict[str, int] = {}
    has_search = bool(search_query and search_query.strip())

    if has_search:
        team_players_search: dict[str, list[dict]] = {}
        for t, group in pt_lookup.groupby("short_name"):
            if t not in target_teams:
                continue
            records = []
            for _, row in group.iterrows():
                w_norm = _normalize_str(str(row["web_name"]))
                f_norm = _normalize_str(str(row["full_name"]))
                words = set(_get_words(w_norm) + _get_words(f_norm))
                records.append({
                    "web_norm": w_norm,
                    "full_norm": f_norm,
                    "words": list(words),
                })
            team_players_search[t] = records

        matched_teams = _search_teams(
            search_query,
            list(target_teams),
            team_name_map,
            team_players_search,
        )
        if matched_teams:
            target_teams = set(matched_teams)
            search_relevance = {team: idx for idx, team in enumerate(matched_teams)}
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
        t_code = int(team_code_map.get(team, 0))
        crest_url = f"https://resources.premierleague.com/premierleague/badges/50/t{t_code}.png"
        club_display = f"{team_name_map.get(team, team)} ({team})"
        tot_color = "#4ade80" if total_diff <= 11 else ("#facc15" if total_diff <= 14 else "#f87171")

        flat_row: dict = {
            "short_name": team,
            "full_name": team_name_map.get(team, team),
            "club_display": club_display,
            "code": t_code,
            "crest_url": crest_url,
            "difficulty_rating": total_diff,
            "total_fdr_color": tot_color,
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
