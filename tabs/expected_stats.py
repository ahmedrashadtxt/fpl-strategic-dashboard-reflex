from data import get_manager_squad_ids
import pandas as pd
from rapidfuzz import fuzz, process
from st_keyup import st_keyup
import streamlit as st
from theme import SILHOUETTE_BASE64, fmt_num, render_list_card, render_sortable_table, section_header

pos_map = {"GKP": 1, "DEF": 2, "MID": 3, "FWD": 4}


def get_player_img_url(photo, code=None):
    photo_str = str(photo) if pd.notna(photo) else ""
    if not photo_str or "Photo-Missing" in photo_str or photo_str == "None":
        if pd.notna(code) and str(code).strip():
            return f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{int(code)}.png"
        return SILHOUETTE_BASE64

    base_name = photo_str.replace(".jpg", "").replace(".png", "")
    if not base_name.startswith("p"):
        base_name = f"p{base_name}"
    return f"https://resources.premierleague.com/premierleague/photos/players/110x140/{base_name}.png"


@st.cache_data(ttl=600, show_spinner=False)
def fetch_expected_stats_base_data(_conn):
    """Fetches all player attacking data and precomputes xP/90 metrics to eliminate keystroke lag."""
    table_check = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_past_seasons'",
        _conn,
    )
    has_history = not table_check.empty

    hist_join = """
        LEFT JOIN (
            SELECT 
                element_id,
                ROUND((SUM(goals_scored + assists) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_GI_90,
                ROUND((SUM(total_points) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_Pts_90,
                SUM(minutes) AS Career_Mins
            FROM player_past_seasons
            GROUP BY element_id
        ) hist ON p.id = hist.element_id
    """ if has_history else ""

    hist_select = """
        hist.Career_GI_90,
        hist.Career_Pts_90,
        hist.Career_Mins,
    """ if has_history else """
        NULL AS Career_GI_90,
        NULL AS Career_Pts_90,
        NULL AS Career_Mins,
    """

    query = f"""
    SELECT
        p.id AS element_id,
        p.code,
        p.photo,
        p.web_name AS Player,
        p.first_name || ' ' || p.second_name AS Full_Name,
        t.short_name AS Team,
        t.name AS Club_Name,
        CASE p.element_type
            WHEN 1 THEN 'GKP'
            WHEN 2 THEN 'DEF'
            WHEN 3 THEN 'MID'
            WHEN 4 THEN 'FWD'
        END AS Pos,
        p.element_type AS element_type,
        p.now_cost / 10.0 AS Price,
        p.minutes AS Minutes,
        p.total_points AS Total_Points,
        p.goals_scored AS Goals,
        p.assists AS Assists,
        p.clean_sheets AS Clean_Sheets,
        p.saves AS Saves,
        p.expected_goals AS xG,
        p.expected_assists AS xA,
        p.expected_goal_involvements AS xGI,
        p.expected_goal_involvements_per_90 AS xGI_per_90,
        {hist_select}
        p.now_cost / 10.0 AS price_val
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    {hist_join}
    """
    df_xgi = pd.read_sql(query, _conn)

    current_season_numeric = [
        "Price", "Minutes", "Total_Points", "Goals", "Assists", "Clean_Sheets",
        "Saves", "xG", "xA", "xGI", "xGI_per_90", "element_type"
    ]
    for col_name in current_season_numeric:
        if col_name in df_xgi.columns:
            df_xgi[col_name] = pd.to_numeric(df_xgi[col_name], errors="coerce").fillna(0)

    career_numeric = ["Career_GI_90", "Career_Pts_90", "Career_Mins"]
    for col_name in career_numeric:
        if col_name in df_xgi.columns:
            df_xgi[col_name] = pd.to_numeric(df_xgi[col_name], errors="coerce")

    def calc_proj_xp_90(row):
        etype = int(row.get("element_type", 3))
        mins = float(row.get("Minutes", 0))
        if mins >= 45:
            xg90 = (float(row.get("xG", 0)) / mins) * 90.0
            xa90 = (float(row.get("xA", 0)) / mins) * 90.0
        else:
            xgi90 = float(row.get("xGI_per_90", 0))
            xg90 = xgi90 * 0.6
            xa90 = xgi90 * 0.4

        if etype == 4:
            return round((xg90 * 4.0) + (xa90 * 3.0), 2)
        elif etype == 3:
            return round((xg90 * 5.0) + (xa90 * 3.0), 2)
        elif etype == 2:
            return round((xg90 * 6.0) + (xa90 * 3.0), 2)
        else:
            return round((xg90 * 6.0) + (xa90 * 3.0), 2)

    if not df_xgi.empty:
        df_xgi["Proj_Attacking_xP_90"] = df_xgi.apply(calc_proj_xp_90, axis=1)
        df_xgi = df_xgi.dropna(subset=["Player"])
        df_xgi = df_xgi[df_xgi["Player"].astype(str).str.strip() != ""]

        df_xgi["_search_target"] = (
            df_xgi["Player"].fillna("")
            + " "
            + df_xgi["Full_Name"].fillna("")
            + " "
            + df_xgi["Team"].fillna("")
            + " "
            + df_xgi["Club_Name"].fillna("")
        ).str.strip()

    return df_xgi


@st.fragment
def render_expected_stats_tab(conn, current_gw):
    col_t1_hdr, col_t1_pop = st.columns([6, 1])
    with col_t1_hdr:
        section_header(
            "Expected Attacking Points & Efficiency",
            "Evaluate attacking performance via expected points per 90 and underlying goal involvements",
        )
    with col_t1_pop:
        st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
        with st.popover("📖 Guide"):
            st.markdown(
                """
                **Expected Attacking Points Guide**
                
                * **Proj xP/90:** Estimated attacking expected points per 90 minutes calculated from underlying expected goal involvements (`xGI/90 * position weight`).
                * **xG / xA / xGI:** Expected Goals, Assists, and Goal Involvements based on shot location and chance quality.
                * **Price Filter:** Use the range slider to isolate players within your specific budget constraints.
                * **Career GI / 90:** Multi-season historical actual performance baseline from prior Premier League campaigns.
                """
            )

    col_search, col1, col2, col3 = st.columns([1.5, 1, 1, 1])
    with col_search:
        search_query = st_keyup(
            "🔍 Search Player / Club",
            placeholder="e.g. Palmer, Haaland, Arsenal, MCI...",
            debounce=250,
            key="tab1_search_keyup",
        )
    with col1:
        min_minutes = st.slider(
            "Minimum Minutes Played", 0, 900, 0, step=45, key="tab1_min_mins"
        )
    with col2:
        position_filter = st.selectbox(
            "Filter Position", ["All", "GKP", "DEF", "MID", "FWD"], key="tab1_pos"
        )
    with col3:
        sort_by = st.selectbox(
            "Rank By",
            [
                "Projected Attacking xP / 90",
                "Expected Goal Involvements (xGI)",
                "xGI per 90",
                "Career GI / 90 (Past Seasons)",
                "Total Points",
                "Clean Sheets",
                "Goalkeeper Saves",
            ],
            key="tab1_sort",
        )

    col_price1, col_toggle1, col_toggle2 = st.columns([1.5, 1, 1])
    with col_price1:
        max_price_filter = st.slider(
            "Filter Max Price (£M)", 4.0, 15.5, 15.5, step=0.5, key="tab1_max_price"
        )
    with col_toggle1:
        only_my_squad_tab1 = st.toggle(
            "🎯 Only My Squad Players", key="tab1_only_squad"
        )
    with col_toggle2:
        show_career_baseline = st.toggle(
            "🏛️ Show Career Baselines (Past Seasons)", value=False, key="tab1_show_career"
        )

    df_raw = fetch_expected_stats_base_data(conn)
    if df_raw.empty:
        st.info("No player data available.")
        return

    filtered_df = df_raw.copy()

    if position_filter != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == position_filter]

    filtered_df = filtered_df[
        (filtered_df["Minutes"] >= min_minutes)
        & (filtered_df["Price"] <= max_price_filter)
    ]

    active_manager_id_tab1 = st.session_state.get("manager_id", "").strip()
    if only_my_squad_tab1 and not filtered_df.empty:
        if not active_manager_id_tab1:
            st.info("💡 Enter your FPL Team ID in the top bar to filter by your squad.")
            filtered_df = filtered_df.iloc[0:0]
        else:
            squad_ids_tab1 = get_manager_squad_ids(active_manager_id_tab1, current_gw)
            filtered_df = filtered_df[filtered_df["element_id"].isin(squad_ids_tab1)]

    has_search = bool(search_query and search_query.strip())

    if has_search and not filtered_df.empty:
        q = search_query.strip()
        search_targets = filtered_df["_search_target"].to_dict()

        matches = process.extract(
            query=q,
            choices=search_targets,
            scorer=fuzz.WRatio,
            score_cutoff=60,
            limit=40,
        )

        if matches:
            matched_indices = [m[2] for m in matches]
            filtered_df = filtered_df.loc[matched_indices]
        else:
            filtered_df = filtered_df.iloc[0:0]

    elif not filtered_df.empty:
        sort_map = {
            "Projected Attacking xP / 90": ("Proj_Attacking_xP_90", False),
            "Expected Goal Involvements (xGI)": ("xGI", False),
            "xGI per 90": ("xGI_per_90", False),
            "Career GI / 90 (Past Seasons)": ("Career_GI_90", False),
            "Total Points": ("Total_Points", False),
            "Clean Sheets": ("Clean_Sheets", False),
            "Goalkeeper Saves": ("Saves", False),
        }
        col, asc = sort_map[sort_by]
        filtered_df = filtered_df.sort_values(by=col, ascending=asc)

    if filtered_df.empty:
        st.info("No players found matching your filters.")
        return

    top_cards = filtered_df.head(min(4, len(filtered_df)))
    card_cols = st.columns(len(top_cards))
    for i, (_, row) in enumerate(top_cards.iterrows()):
        proj_xp = float(row["Proj_Attacking_xP_90"])
        xp_tag = (f"Proj {proj_xp:.2f} xP/90", "green")
        with card_cols[i]:
            c_gi = row.get("Career_GI_90")
            hist_note = (
                f" · <span>Career GI/90</span> {fmt_num(c_gi)}"
                if pd.notna(c_gi) and float(c_gi) > 0 and show_career_baseline
                else ""
            )
            card_img = get_player_img_url(row.get("photo"), row.get("code"))
            render_list_card(
                f"{row['Player']} ({row['Team']})",
                [(row["Pos"], "blue"), xp_tag],
                f'<span>Price</span> £{fmt_num(row["Price"], ".1f")} · <span>xGI</span>'
                f' {fmt_num(row["xGI"])} · <span>Pts</span>'
                f' {int(float(row["Total_Points"]))} · <span>xP/90</span>'
                f' {fmt_num(proj_xp, ".2f")}{hist_note}',
                img_url=card_img,
            )

    is_dark = st.session_state.get("theme_mode", "dark") == "dark"

    theme_styles = f"""
    <style>
    .unified-table-wrapper {{
        width: 100%;
        overflow-x: auto;
        border: 1px solid {"#222222" if is_dark else "#e2e8f0"};
        border-radius: 10px;
        background: {"#141414" if is_dark else "#ffffff"};
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-top: 1rem;
    }}
    .unified-table {{
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        color: {"#ffffff" if is_dark else "#0f172a"};
    }}
    .unified-table th {{
        background: {"#18181b" if is_dark else "#f8fafc"};
        color: {"#94a3b8" if is_dark else "#64748b"};
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        font-size: 0.78rem;
        letter-spacing: 0.02em;
        padding: 0.7rem 0.75rem;
        border-bottom: 1px solid {"#27272a" if is_dark else "#e2e8f0"};
        text-align: center;
        white-space: nowrap;
    }}
    .unified-table td {{
        padding: 0.5rem 0.75rem;
        border-bottom: 1px solid {"#1f1f23" if is_dark else "#f1f5f9"};
        vertical-align: middle;
        text-align: center;
        white-space: nowrap;
    }}
    .unified-table tr:last-child td {{
        border-bottom: none;
    }}
    .unified-table tr:hover td {{
        background: {"rgba(255, 255, 255, 0.02)" if is_dark else "rgba(0, 0, 0, 0.015)"};
    }}
    .player-unified-cell {{
        display: flex;
        align-items: center;
        gap: 10px;
        white-space: nowrap;
    }}
    .player-avatar-circle {{
        width: 28px;
        height: 28px;
        border-radius: 50%;
        object-fit: cover;
        object-position: top center;
        background-color: {"#1e293b" if is_dark else "#e2e8f0"};
        border: 1px solid {"#2a2a2a" if is_dark else "#cbd5e1"};
        flex-shrink: 0;
    }}
    .player-name-text {{
        font-weight: 600;
        color: {"#ffffff" if is_dark else "#0f172a"};
    }}
    .pos-pill {{
        display: inline-block;
        padding: 0.12rem 0.45rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
    }}
    .pos-GKP {{ background: rgba(245, 158, 11, 0.18); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3); }}
    .pos-DEF {{ background: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }}
    .pos-MID {{ background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .pos-FWD {{ background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}

    .xp-pill {{
        display: inline-block;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.8rem;
        background: rgba(34, 197, 94, 0.2);
        color: {"#4ade80" if is_dark else "#15803d"};
    }}
    </style>
    """

    display_df = filtered_df.head(35)
    html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
    html_out.append('<th style="text-align: left; padding-left: 1rem;">Player</th>')
    html_out.append('<th>Club</th><th>Pos</th><th>Price</th><th>Mins</th><th>Pts</th><th>Gls</th><th>Ast</th><th>CS</th><th>Saves</th>')
    html_out.append('<th>xG</th><th>xA</th><th>xGI</th><th>Proj xP/90</th><th>xGI/90</th>')

    if show_career_baseline:
        html_out.append('<th>Career GI/90</th><th>Career Pts/90</th><th>Career Mins</th>')

    html_out.append('</tr></thead><tbody>')

    for _, row in display_df.iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        proj_xp = float(row["Proj_Attacking_xP_90"])

        html_out.append("<tr>")
        html_out.append(
            f'<td style="text-align: left; padding-left: 1rem;">'
            f'<div class="player-unified-cell">'
            f'<img src="{p_img}" class="player-avatar-circle" onerror="this.src=\'{SILHOUETTE_BASE64}\'">'
            f'<span class="player-name-text">{row["Player"]}</span>'
            f'</div></td>'
        )
        html_out.append(f'<td>{row["Team"]}</td>')
        html_out.append(f'<td><span class="pos-pill pos-{row["Pos"]}">{row["Pos"]}</span></td>')
        html_out.append(f'<td>£{row["Price"]:.1f}</td>')
        html_out.append(f'<td>{int(row["Minutes"]):,}</td>')
        html_out.append(f'<td style="font-weight: 700;">{int(row["Total_Points"])}</td>')
        html_out.append(f'<td>{int(row["Goals"])}</td>')
        html_out.append(f'<td>{int(row["Assists"])}</td>')
        html_out.append(f'<td>{int(row["Clean_Sheets"])}</td>')
        html_out.append(f'<td>{int(row["Saves"])}</td>')
        html_out.append(f'<td>{row["xG"]:.2f}</td>')
        html_out.append(f'<td>{row["xA"]:.2f}</td>')
        html_out.append(f'<td style="font-weight: 700;">{row["xGI"]:.2f}</td>')
        html_out.append(f'<td><span class="xp-pill">{proj_xp:.2f}</span></td>')
        html_out.append(f'<td>{row["xGI_per_90"]:.2f}</td>')

        if show_career_baseline:
            c_gi = row.get("Career_GI_90")
            c_pts = row.get("Career_Pts_90")
            c_mins = row.get("Career_Mins")

            c_gi_str = fmt_num(c_gi) if pd.notna(c_gi) and float(c_gi) > 0 else "—"
            c_pts_str = fmt_num(c_pts) if pd.notna(c_pts) and float(c_pts) > 0 else "—"
            c_mins_str = f"{int(c_mins):,}" if pd.notna(c_mins) and float(c_mins) > 0 else "—"

            html_out.append(f'<td>{c_gi_str}</td>')
            html_out.append(f'<td>{c_pts_str}</td>')
            html_out.append(f'<td>{c_mins_str}</td>')

        html_out.append("</tr>")

    html_out.append("</tbody></table></div>")

    full_table_height = (len(display_df) * 45) + 60
    render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)