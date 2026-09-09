from data import get_manager_squad_ids
import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process
from st_keyup import st_keyup
import streamlit as st
from theme import (
    SILHOUETTE_BASE64,
    fmt_num,
    render_guide_popover,
    render_list_card,
    render_sortable_table,
    section_header,
)

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
def fetch_defensive_base_data(_conn, current_gw: int = 1):
    """Fetches player defensive records and precomputes absolute gameweek projected defensive xP."""
    player_cols = [
        c.lower()
        for c in pd.read_sql("PRAGMA table_info(players)", _conn)["name"].tolist()
    ]

    t_expr = (
        "p.tackles AS T"
        if "tackles" in player_cols
        else ("p.t AS T" if "t" in player_cols else "0 AS T")
    )

    if "clearances_blocks_interceptions" in player_cols:
        cbi_expr = "p.clearances_blocks_interceptions AS CBI"
    elif "cbi" in player_cols:
        cbi_expr = "p.cbi AS CBI"
    elif all(c in player_cols for c in ["clearances", "blocks", "interceptions"]):
        cbi_expr = "(p.clearances + p.blocks + p.interceptions) AS CBI"
    else:
        cbi_expr = "0 AS CBI"

    r_expr = (
        "p.recoveries AS R"
        if "recoveries" in player_cols
        else ("p.r AS R" if "r" in player_cols else "0 AS R")
    )

    if "defensive_contribution" in player_cols:
        dc_expr = "p.defensive_contribution AS DC"
    elif "defensive_contributions" in player_cols:
        dc_expr = "p.defensive_contributions AS DC"
    elif "dc" in player_cols:
        dc_expr = "p.dc AS DC"
    else:
        cbi_col = (
            "p.clearances_blocks_interceptions"
            if "clearances_blocks_interceptions" in player_cols
            else ("p.cbi" if "cbi" in player_cols else "0")
        )
        t_col = "p.tackles" if "tackles" in player_cols else "0"
        r_col = "p.recoveries" if "recoveries" in player_cols else "0"
        dc_expr = f"""
            CASE 
                WHEN p.element_type = 2 THEN (COALESCE({cbi_col}, 0) + COALESCE({t_col}, 0))
                ELSE (COALESCE({cbi_col}, 0) + COALESCE({t_col}, 0) + COALESCE({r_col}, 0))
            END AS DC
        """

    xgc_expr = (
        "p.expected_goals_conceded AS xGC"
        if "expected_goals_conceded" in player_cols
        else "0.0 AS xGC"
    )
    xgc_90_expr = (
        "p.expected_goals_conceded_per_90 AS xGC_per_90"
        if "expected_goals_conceded_per_90" in player_cols
        else "0.0 AS xGC_per_90"
    )

    table_check = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_past_seasons'",
        _conn,
    )
    has_history = not table_check.empty

    past_cols = (
        [
            c.lower()
            for c in pd.read_sql(
                "PRAGMA table_info(player_past_seasons)", _conn
            )["name"].tolist()
        ]
        if has_history
        else []
    )

    gc_hist_col = "SUM(goals_conceded)" if "goals_conceded" in past_cols else "0"
    cs_hist_col = "SUM(clean_sheets)" if "clean_sheets" in past_cols else "0"

    hist_join = (
        f"""
        LEFT JOIN (
            SELECT 
                element_id,
                ROUND(({gc_hist_col} * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_GC_90,
                ROUND(({cs_hist_col} * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_CS_90,
                ROUND((SUM(total_points) * 1.0 / NULLIF(SUM(minutes), 0)) * 90.0, 2) AS Career_Pts_90,
                SUM(minutes) AS Career_Mins
            FROM player_past_seasons
            GROUP BY element_id
        ) hist ON p.id = hist.element_id
    """
        if has_history
        else ""
    )

    hist_select = (
        """
        hist.Career_GC_90,
        hist.Career_CS_90,
        hist.Career_Pts_90,
        hist.Career_Mins,
    """
        if has_history
        else """
        NULL AS Career_GC_90,
        NULL AS Career_CS_90,
        NULL AS Career_Pts_90,
        NULL AS Career_Mins,
    """
    )

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
        p.clean_sheets AS Clean_Sheets,
        p.goals_conceded AS Goals_Conceded,
        p.saves AS Saves,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance,
        {xgc_expr},
        {xgc_90_expr},
        {t_expr},
        {cbi_expr},
        {r_expr},
        {dc_expr},
        {hist_select}
        p.now_cost / 10.0 AS price_val
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    {hist_join}
    """
    df_def = pd.read_sql(query, _conn)

    current_season_numeric = [
        "Price", "Minutes", "Total_Points", "Clean_Sheets", "Goals_Conceded",
        "Saves", "xGC", "xGC_per_90", "T", "CBI", "R", "DC", "element_type"
    ]
    for col_name in current_season_numeric:
        if col_name in df_def.columns:
            df_def[col_name] = pd.to_numeric(df_def[col_name], errors="coerce").fillna(0)

    career_numeric = ["Career_GC_90", "Career_CS_90", "Career_Pts_90", "Career_Mins"]
    for col_name in career_numeric:
        if col_name in df_def.columns:
            df_def[col_name] = pd.to_numeric(df_def[col_name], errors="coerce")

    df_def["DC_per_90"] = (
        (df_def["DC"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
    ).fillna(0.0).round(2)
    df_def["Saves_per_90"] = (
        (df_def["Saves"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
    ).fillna(0.0).round(2)

    if (df_def["xGC_per_90"] == 0).all():
        df_def["xGC_per_90"] = (
            (df_def["xGC"] / df_def["Minutes"].replace(0, pd.NA)) * 90.0
        ).fillna(0.0).round(2)

    completed_gws = max(1, current_gw - 1)
    df_def["Avg_Mins_GW"] = (df_def["Minutes"] / completed_gws).round(1)

    def calc_def_xp(row):
        etype = int(row.get("element_type", 2))
        mins = float(row.get("Minutes", 0))
        career_gc = row.get("Career_GC_90")
        avg_mins = float(row.get("Avg_Mins_GW", 0))

        raw_xgc90 = float(row.get("xGC_per_90", 0))
        if raw_xgc90 <= 0:
            raw_xgc90 = 1.35

        if mins < 90:
            baseline_gc = (
                float(career_gc)
                if pd.notna(career_gc) and float(career_gc) > 0
                else 1.35
            )
            weight = mins / 90.0
            xgc90 = (raw_xgc90 * weight) + (baseline_gc * (1.0 - weight))
        else:
            xgc90 = raw_xgc90

        cs_prob = np.exp(-xgc90)
        saves90 = float(row.get("Saves_per_90", 0))

        # Expected match playing time and clean sheet 60-minute eligibility
        if current_gw > 1:
            if avg_mins >= 60:
                mins_factor = min(1.0, avg_mins / 90.0)
                cs_eligible = 1.0
            elif avg_mins >= 30:
                mins_factor = (avg_mins / 90.0) * 0.85
                cs_eligible = 0.40
            elif mins > 0:
                mins_factor = max(0.05, mins / (completed_gws * 90.0))
                cs_eligible = 0.05
            else:
                mins_factor = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.35
                cs_eligible = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.35
        else:
            mins_factor = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.60
            cs_eligible = 0.85 if float(row.get("Price", 0)) >= 5.0 else 0.60

        status = str(row.get("Status", "a"))
        chance = row.get("Chance")
        if status in ("i", "u", "s"):
            avail = 0.0
        elif pd.notna(chance) and str(chance).strip() not in ("", "None"):
            avail = float(chance) / 100.0
        else:
            avail = 1.0

        if etype == 1:
            cs_pts = cs_prob * 4.0 * cs_eligible
            gc_deduction = (xgc90 * mins_factor) * 0.50
            save_pts = (saves90 * mins_factor) / 3.0
            net_def_xp = cs_pts - gc_deduction + save_pts
        elif etype == 2:
            cs_pts = cs_prob * 4.0 * cs_eligible
            gc_deduction = (xgc90 * mins_factor) * 0.50
            net_def_xp = cs_pts - gc_deduction
        elif etype == 3:
            net_def_xp = cs_prob * 1.0 * cs_eligible
        else:
            net_def_xp = 0.0

        dc90 = float(row.get("DC_per_90", 0))
        dc_boost = (0.40 if dc90 >= 10.0 else (0.20 if dc90 >= 7.0 else 0.0)) * mins_factor
        return round(max(0.0, (net_def_xp + dc_boost) * avail), 2)

    def calc_def_xp_90(row):
        etype = int(row.get("element_type", 2))
        mins = float(row.get("Minutes", 0))
        career_gc = row.get("Career_GC_90")

        raw_xgc90 = float(row.get("xGC_per_90", 0))
        if raw_xgc90 <= 0:
            raw_xgc90 = 1.35

        if mins < 90:
            baseline_gc = (
                float(career_gc)
                if pd.notna(career_gc) and float(career_gc) > 0
                else 1.35
            )
            weight = mins / 90.0
            xgc90 = (raw_xgc90 * weight) + (baseline_gc * (1.0 - weight))
        else:
            xgc90 = raw_xgc90

        cs_prob = np.exp(-xgc90)
        saves90 = float(row.get("Saves_per_90", 0))

        if etype == 1:
            cs_pts = cs_prob * 4.0
            gc_deduction = xgc90 * 0.50
            save_pts = saves90 / 3.0
            net_def_xp = cs_pts - gc_deduction + save_pts
        elif etype == 2:
            cs_pts = cs_prob * 4.0
            gc_deduction = xgc90 * 0.50
            net_def_xp = cs_pts - gc_deduction
        elif etype == 3:
            net_def_xp = cs_prob * 1.0
        else:
            net_def_xp = 0.0

        dc90 = float(row.get("DC_per_90", 0))
        dc_boost = 0.40 if dc90 >= 10.0 else (0.20 if dc90 >= 7.0 else 0.0)
        return round(max(0.1, net_def_xp + dc_boost), 2)

    if not df_def.empty:
        df_def["Proj_Defensive_xP"] = df_def.apply(calc_def_xp, axis=1)
        df_def["Proj_Defensive_xP_90"] = df_def.apply(calc_def_xp_90, axis=1)
        df_def = df_def.dropna(subset=["Player"])
        df_def = df_def[df_def["Player"].astype(str).str.strip() != ""]

        df_def["_search_target"] = (
            df_def["Player"].fillna("")
            + " "
            + df_def["Full_Name"].fillna("")
            + " "
            + df_def["Team"].fillna("")
            + " "
            + df_def["Club_Name"].fillna("")
        ).str.strip()

    return df_def


@st.fragment
def render_defensive_stats_tab(conn, current_gw):
    col_def_hdr, col_def_pop = st.columns([6.2, 0.8], vertical_alignment="center")
    with col_def_hdr:
        section_header(
            "Defensive Resilience & Projected Defensive xP",
            "Evaluate clean sheet probability, defensive actions, and goalkeeper save points",
        )
    with col_def_pop:
        render_guide_popover(
            title="Defensive Resilience & Projected Defensive xP",
            subtitle="Evaluate clean sheet probability, defensive actions, and goalkeeper save points",
            items=[
                {"badge": "Def xP", "title": "Projected Defensive Points", "desc": "Defensive expected points derived from clean sheet odds (P(CS) × 4 for DEF/GKP, × 1 for MID), goals conceded deductions (-0.5 × xGC), saves (+1 per 3 saves), and playing time.", "color": "#38bdf8"},
                {"badge": "DC Actions", "title": "Defensive Contributions (DC)", "desc": "Tracks Clearances, Blocks, Interceptions, and Tackles (CBIT) targeting the official FPL +2 DC bonus point threshold.", "color": "#10b981"},
                {"badge": "Saves", "title": "Goalkeeper Save Projections", "desc": "Expected shot volume and save bonus points projected against opposing team shot rates per 90.", "color": "#818cf8"},
                {"badge": "Regression", "title": "Sample Size Shrinkage", "desc": "Small early-season minute samples (<90 mins) are automatically regressed toward career baselines to remove sample noise.", "color": "#f59e0b"},
                {"badge": "Minutes", "title": "Starter Regularity Filter", "desc": "Filters out substitute cameos and rotation liabilities to focus strictly on nailed-on starters.", "color": "#38bdf8"},
            ],
            tip="Target budget defenders whose teams concede low-quality shots from distance—they rack up baseline DC actions while preserving high clean sheet odds.",
            key="guide_pop_defensive_stats",
        )

    col_search, col1, col2, col3 = st.columns([1.4, 1.2, 1, 1.2])
    with col_search:
        search_query = st_keyup(
            "Search Player / Club",
            placeholder="e.g. Gabriel, Raya, Saliba, ARS...",
            debounce=250,
            key="def_search_keyup",
        )
    with col1:
        min_avg_mins = st.slider(
            ":material/timer:  Min Avg Mins / GW", 0, 90, 0, step=5, key="def_min_avg_mins",
            help="Filter players by average minutes played per gameweek",
        )
    with col2:
        position_filter = st.selectbox(
            "Filter Position", ["DEF", "GKP", "MID", "All"], index=0, key="def_pos"
        )
    with col3:
        sort_by = st.selectbox(
            "Rank By",
            [
                "Projected Defensive xP",
                "DC per 90",
                "Total DC",
                "Projected Defensive xP / 90",
                "CBI (Clearances, Blocks, Int)",
                "Tackles (T)",
                "Recoveries (R)",
                "Expected Goals Conceded (Lowest xGC)",
                "Clean Sheets",
                "Total Points",
                "Goalkeeper Saves",
            ],
            key="def_sort",
        )

    col_price2, col_toggle1, col_toggle2 = st.columns([1.5, 1, 1])
    with col_price2:
        max_price_filter_def = st.slider(
            "Filter Max Price (£M)", 4.0, 9.0, 9.0, step=0.5, key="def_max_price"
        )
    with col_toggle1:
        only_my_squad_tab = st.toggle(
            ":material/my_location:  Only My Squad Players", key="def_only_squad"
        )
    with col_toggle2:
        show_career_baseline = st.toggle(
            ":material/account_balance:  Show Career Baselines (Past Seasons)", value=False, key="def_show_career"
        )

    df_raw = fetch_defensive_base_data(conn, current_gw)
    if df_raw.empty:
        st.info("No player data available.")
        return

    filtered_df = df_raw.copy()

    if position_filter != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == position_filter]

    filtered_df = filtered_df[
        (filtered_df["Avg_Mins_GW"] >= min_avg_mins)
        & (filtered_df["Price"] <= max_price_filter_def)
    ]

    active_manager_id = st.session_state.get("manager_id", "").strip()
    if only_my_squad_tab and not filtered_df.empty:
        if not active_manager_id:
            st.info(":material/lightbulb: Enter your FPL Team ID in the top bar to filter by your squad.")
            filtered_df = filtered_df.iloc[0:0]
        else:
            squad_ids = get_manager_squad_ids(active_manager_id, current_gw)
            filtered_df = filtered_df[filtered_df["element_id"].isin(squad_ids)]

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
            "Projected Defensive xP": ("Proj_Defensive_xP", False),
            "DC per 90": ("DC_per_90", False),
            "Total DC": ("DC", False),
            "Projected Defensive xP / 90": ("Proj_Defensive_xP_90", False),
            "CBI (Clearances, Blocks, Int)": ("CBI", False),
            "Tackles (T)": ("T", False),
            "Recoveries (R)": ("R", False),
            "Expected Goals Conceded (Lowest xGC)": ("xGC", True),
            "Clean Sheets": ("Clean_Sheets", False),
            "Total Points": ("Total_Points", False),
            "Goalkeeper Saves": ("Saves", False),
        }
        sort_col, sort_asc = sort_map[sort_by]
        filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)

    if filtered_df.empty:
        st.info("No players found matching your filters.")
        return

    top_cards = filtered_df.head(min(4, len(filtered_df)))
    card_cols = st.columns(len(top_cards))
    for i, (_, row) in enumerate(top_cards.iterrows()):
        proj_def_xp = float(row["Proj_Defensive_xP"])
        def_xp_tag = (f"Proj {proj_def_xp:.2f} def xP", "blue")

        with card_cols[i]:
            c_cs = row.get("Career_CS_90")
            hist_note = (
                f" · <span>Career CS/90</span> {fmt_num(c_cs)}"
                if pd.notna(c_cs) and float(c_cs) > 0 and show_career_baseline
                else ""
            )
            card_img = get_player_img_url(row.get("photo"), row.get("code"))
            render_list_card(
                f"{row['Player']} ({row['Team']})",
                [(row["Pos"], "blue"), def_xp_tag],
                f'<span>Price</span> £{fmt_num(row["Price"], ".1f")} · <span>Avg M/GW</span>'
                f' {int(row["Avg_Mins_GW"])}m · <span>xGC</span>'
                f' {fmt_num(row["xGC"])} · <span>DC/90</span>'
                f' {fmt_num(row["DC_per_90"])} · <span>Pts</span>'
                f' {int(float(row["Total_Points"]))} · <span>Def xP</span>'
                f' {fmt_num(proj_def_xp, ".2f")}{hist_note}',
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

    .def-xp-pill {{
        display: inline-block;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.8rem;
        background: rgba(59, 130, 246, 0.2);
        color: {"#60a5fa" if is_dark else "#1d4ed8"};
    }}
    </style>
    """

    display_df = filtered_df.head(35)
    html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
    html_out.append('<th style="text-align: left; padding-left: 1rem;">Player</th>')
    html_out.append('<th>Club</th><th>Pos</th><th>Price</th><th>Mins</th><th>Avg M/GW</th><th>Pts</th><th>CS</th><th>GC</th>')
    html_out.append('<th>xGC</th><th>Proj Def xP</th><th>xGC/90</th><th>DC</th><th>DC/90</th><th>CBI</th><th>R</th><th>T</th><th>Saves</th><th>Saves/90</th>')

    if show_career_baseline:
        html_out.append('<th>Career GC/90</th><th>Career CS/90</th><th>Career Pts/90</th><th>Career Mins</th>')

    html_out.append('</tr></thead><tbody>')

    for _, row in display_df.iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        proj_def_xp = float(row["Proj_Defensive_xP"])

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
        html_out.append(f'<td>{int(row["Avg_Mins_GW"])}m</td>')
        html_out.append(f'<td style="font-weight: 700;">{int(row["Total_Points"])}</td>')
        html_out.append(f'<td>{int(row["Clean_Sheets"])}</td>')
        html_out.append(f'<td>{int(row["Goals_Conceded"])}</td>')
        html_out.append(f'<td>{row["xGC"]:.2f}</td>')
        html_out.append(f'<td><span class="def-xp-pill">{proj_def_xp:.2f}</span></td>')
        html_out.append(f'<td>{row["xGC_per_90"]:.2f}</td>')
        html_out.append(f'<td style="font-weight: 700;">{int(row["DC"])}</td>')
        html_out.append(f'<td>{row["DC_per_90"]:.2f}</td>')
        html_out.append(f'<td>{int(row["CBI"])}</td>')
        html_out.append(f'<td>{int(row["R"])}</td>')
        html_out.append(f'<td>{int(row["T"])}</td>')
        html_out.append(f'<td>{int(row["Saves"])}</td>')
        html_out.append(f'<td>{row["Saves_per_90"]:.2f}</td>')

        if show_career_baseline:
            c_gc = row.get("Career_GC_90")
            c_cs = row.get("Career_CS_90")
            c_pts = row.get("Career_Pts_90")
            c_mins = row.get("Career_Mins")

            c_gc_str = fmt_num(c_gc) if pd.notna(c_gc) and float(c_gc) > 0 else "—"
            c_cs_str = fmt_num(c_cs) if pd.notna(c_cs) and float(c_cs) > 0 else "—"
            c_pts_str = fmt_num(c_pts) if pd.notna(c_pts) and float(c_pts) > 0 else "—"
            c_mins_str = f"{int(c_mins):,}" if pd.notna(c_mins) and float(c_mins) > 0 else "—"

            html_out.append(f'<td>{c_gc_str}</td>')
            html_out.append(f'<td>{c_cs_str}</td>')
            html_out.append(f'<td>{c_pts_str}</td>')
            html_out.append(f'<td>{c_mins_str}</td>')

        html_out.append("</tr>")

    html_out.append("</tbody></table></div>")

    full_table_height = (len(display_df) * 45) + 60
    render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)