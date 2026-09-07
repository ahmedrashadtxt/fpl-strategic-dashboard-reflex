from data import get_manager_squad_ids
import pandas as pd
from rapidfuzz import fuzz, process
from st_keyup import st_keyup
import streamlit as st
from theme import render_sortable_table, section_header


@st.fragment
def render_fixture_ticker_tab(conn, current_gw):
    col_t3_hdr, col_t3_pop = st.columns([6, 1])
    with col_t3_hdr:
        section_header(
            f"Fixture Difficulty · GW{current_gw}–{current_gw + 4}",
            "Upcoming schedule ranked by difficulty",
        )
    with col_t3_pop:
        st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
        with st.popover("📖 Guide"):
            st.markdown(
                """
                **Fixture Ticker Guide**
                
                * **Difficulty Rating:** Sum of official FDR scores across the next 5 gameweeks.
                * **(H) vs. (A):** Designates Home or Away fixtures.
                * 🟢 **Green Run (≤10 pts):** Prime fixture swings.
                * 🔴 **Tough Run (≥15 pts):** Hold off buying assets from these clubs until their schedule clears.
                """
            )

    col_search3, col_sq3 = st.columns([2, 1])
    with col_search3:
        search_query3 = st_keyup(
            "🔍 Search Player / Club",
            placeholder="e.g. Saka, Arsenal, Haaland, MCI...",
            debounce=250,
            key="tab3_search_keyup",
        )

    with col_sq3:
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        only_my_squad_tab3 = st.toggle(
            "🎯 Only My Squad Clubs", key="tab3_only_squad"
        )

    fixtures_query = """
    SELECT
        f.event AS GW,
        th.short_name AS Home_Team,
        ta.short_name AS Away_Team,
        f.team_h_difficulty AS Home_Diff,
        f.team_a_difficulty AS Away_Diff
    FROM fixtures f
    INNER JOIN teams th ON f.team_h = th.id
    INNER JOIN teams ta ON f.team_a = ta.id
    WHERE f.event >= ? AND f.event < ? AND f.finished = 0
    ORDER BY f.event ASC
    """
    fixtures_df = pd.read_sql(
        fixtures_query, conn, params=[current_gw, current_gw + 5]
    )

    pt_lookup = pd.read_sql(
        """
        SELECT 
            p.id AS element_id, 
            p.web_name, 
            p.first_name || ' ' || p.second_name AS full_name,
            t.short_name, 
            t.name AS club_name
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        """,
        conn,
    )

    teams_df = pd.read_sql("SELECT id, code, short_name, name FROM teams ORDER BY name", conn)
    teams_list = teams_df["short_name"].tolist()
    team_name_map = dict(zip(teams_df["short_name"], teams_df["name"]))
    team_code_map = dict(zip(teams_df["short_name"], teams_df["code"]))

    target_team_short_names = set(teams_list)
    team_players_map = {}

    if only_my_squad_tab3:
        active_manager_id_tab3 = st.session_state.get("manager_id", "").strip()
        if not active_manager_id_tab3:
            st.info("💡 Enter your FPL Team ID in the top bar to filter by your squad.")
            target_team_short_names = set()
        else:
            squad_ids_tab3 = get_manager_squad_ids(active_manager_id_tab3, current_gw)
            squad_players_df = pt_lookup[pt_lookup["element_id"].isin(squad_ids_tab3)]
            squad_teams = squad_players_df["short_name"].unique()
            target_team_short_names = target_team_short_names.intersection(set(squad_teams))

            team_players_map = (
                squad_players_df.groupby("short_name")["web_name"]
                .apply(lambda names: ", ".join(names))
                .to_dict()
            )

    # Precompute club string target containing club names + squad player names
    all_team_players = (
        pt_lookup.groupby("short_name")["web_name"]
        .apply(lambda s: " ".join(s))
        .to_dict()
    )
    club_search_dict = {
        team: f"{team} {team_name_map.get(team, '')} {all_team_players.get(team, '')}"
        for team in target_team_short_names
    }

    has_search = bool(search_query3 and search_query3.strip())
    search_relevance_order = {}

    if has_search:
        matches = process.extract(
            query=search_query3.strip(),
            choices=club_search_dict,
            scorer=fuzz.WRatio,
            score_cutoff=55,
            limit=20,
        )
        if matches:
            target_team_short_names = [m[2] for m in matches]
            search_relevance_order = {team: idx for idx, team in enumerate(target_team_short_names)}
        else:
            target_team_short_names = []

    ticker_data = []
    gw_cols = [gw for gw in range(current_gw, current_gw + 5)]

    for team in teams_list:
        if team not in target_team_short_names:
            continue

        t_code = team_code_map.get(team, 0)
        row = {
            "code": t_code,
            "short_name": team,
            "full_name": team_name_map.get(team, team),
            "fixtures": {},
        }

        if only_my_squad_tab3:
            row["my_players"] = team_players_map.get(team, "—")

        total_difficulty = 0
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
                    diff = m["Home_Diff"]
                else:
                    opp = f"{m['Home_Team']} (A)"
                    diff = m["Away_Diff"]
                row["fixtures"][gw] = (diff, f"[{diff}] {opp}")
                total_difficulty += diff
            else:
                row["fixtures"][gw] = (5, "[5] Blank")
                total_difficulty += 5
        row["difficulty_rating"] = total_difficulty
        ticker_data.append(row)

    if has_search:
        ticker_data.sort(key=lambda x: search_relevance_order.get(x["short_name"], 999))
    else:
        ticker_data.sort(key=lambda x: x["difficulty_rating"])

    if not ticker_data:
        st.info("No clubs found matching your search or squad criteria.")
        return

    is_dark = st.session_state.get("theme_mode", "dark") == "dark"

    theme_styles = f"""
    <style>
    .fdr-table-wrapper {{
        width: 100%;
        overflow-x: auto;
        border: 1px solid {"#222222" if is_dark else "#e2e8f0"};
        border-radius: 10px;
        background: {"#141414" if is_dark else "#ffffff"};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-top: 0.5rem;
    }}
    .fdr-table {{
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        font-size: 0.86rem;
        color: {"#ffffff" if is_dark else "#0f172a"};
    }}
    .fdr-table th {{
        background: {"#18181b" if is_dark else "#f8fafc"};
        color: {"#94a3b8" if is_dark else "#64748b"};
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        font-size: 0.8rem;
        letter-spacing: 0.02em;
        padding: 0.75rem 0.9rem;
        border-bottom: 1px solid {"#27272a" if is_dark else "#e2e8f0"};
        text-align: center;
        white-space: nowrap;
    }}
    .fdr-table td {{
        padding: 0.55rem 0.75rem;
        border-bottom: 1px solid {"#1f1f23" if is_dark else "#f1f5f9"};
        vertical-align: middle;
    }}
    .fdr-table tr:last-child td {{
        border-bottom: none;
    }}
    .fdr-table tr:hover td {{
        background: {"rgba(255, 255, 255, 0.02)" if is_dark else "rgba(0, 0, 0, 0.015)"};
    }}
    .club-unified-cell {{
        display: flex;
        align-items: center;
        gap: 10px;
        white-space: nowrap;
    }}
    .club-crest-img {{
        width: 24px;
        height: 24px;
        object-fit: contain;
        flex-shrink: 0;
    }}
    .club-title-text {{
        font-weight: 600;
        color: {"#ffffff" if is_dark else "#0f172a"};
    }}
    .my-players-pill {{
        color: {"#9BBEED" if is_dark else "#1d4ed8"};
        font-weight: 600;
        font-size: 0.83rem;
        white-space: nowrap;
    }}
    .fdr-badge {{
        display: block;
        width: 100%;
        text-align: center;
        padding: 0.35rem 0.55rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        white-space: nowrap;
    }}
    .fdr-2 {{ background: rgba(34, 197, 94, 0.22); color: {"#4ade80" if is_dark else "#15803d"}; }}
    .fdr-3 {{ background: rgba(100, 116, 139, 0.16); color: {"#cbd5e1" if is_dark else "#334155"}; }}
    .fdr-4 {{ background: rgba(249, 115, 22, 0.24); color: {"#fb923c" if is_dark else "#c2410c"}; font-weight: 700; }}
    .fdr-5 {{ background: rgba(239, 68, 68, 0.28); color: {"#f87171" if is_dark else "#b91c1c"}; font-weight: 800; }}
    .fdr-blank {{ background: rgba(15, 23, 42, 0.5); color: #64748b; font-style: italic; }}

    .fdr-total-cell {{
        text-align: center;
        font-weight: 800;
        font-size: 0.9rem;
    }}
    .total-green {{ color: #22c55e; }}
    .total-yellow {{ color: #eab308; }}
    .total-red {{ color: #ef4444; }}
    </style>
    """

    html_out = [theme_styles, '<div class="fdr-table-wrapper"><table class="fdr-table"><thead><tr>']
    html_out.append('<th style="text-align: left; padding-left: 1rem;">Club</th>')

    if only_my_squad_tab3:
        html_out.append('<th style="text-align: left;">My Players</th>')

    for gw in gw_cols:
        html_out.append(f'<th>GW {gw}</th>')

    html_out.append('<th>Total FDR (5 GW)</th></tr></thead><tbody>')

    for row in ticker_data:
        crest_url = f"https://resources.premierleague.com/premierleague/badges/50/t{row['code']}.png"
        club_label = f"{row['full_name']} ({row['short_name']})"

        html_out.append("<tr>")
        html_out.append(
            f'<td style="padding-left: 1rem;">'
            f'<div class="club-unified-cell">'
            f'<img src="{crest_url}" class="club-crest-img" alt="{row["short_name"]}">'
            f'<span class="club-title-text">{club_label}</span>'
            f'</div></td>'
        )

        if only_my_squad_tab3:
            html_out.append(f'<td style="text-align: left;"><span class="my-players-pill">{row.get("my_players", "—")}</span></td>')

        for gw in gw_cols:
            diff, label = row["fixtures"][gw]
            if "Blank" in label:
                cls = "fdr-blank"
            elif diff == 2:
                cls = "fdr-2"
            elif diff == 3:
                cls = "fdr-3"
            elif diff == 4:
                cls = "fdr-4"
            else:
                cls = "fdr-5"
            html_out.append(f'<td><span class="fdr-badge {cls}">{label}</span></td>')

        tot = row["difficulty_rating"]
        tot_cls = "total-green" if tot <= 11 else ("total-yellow" if tot <= 14 else "total-red")
        html_out.append(f'<td class="fdr-total-cell {tot_cls}">{tot}</td>')
        html_out.append("</tr>")

    html_out.append("</tbody></table></div>")

    full_table_height = (len(ticker_data) * 45) + 60
    render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)