from data import get_manager_squad_ids
import pandas as pd
import plotly.express as px
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
def fetch_rolling_base_data(_conn, window_size: int):
    """Caches rolling window computations per window size."""
    rolling_query = f"""
    WITH ranked_matches AS (
        SELECT
            h.element_id,
            p.code,
            p.photo,
            p.web_name AS Player,
            p.first_name || ' ' || p.second_name AS Full_Name,
            t.short_name AS Team,
            t.name AS Club_Name,
            p.team AS Team_ID,
            CASE p.element_type
                WHEN 1 THEN 'GKP'
                WHEN 2 THEN 'DEF'
                WHEN 3 THEN 'MID'
                WHEN 4 THEN 'FWD'
            END AS Pos,
            p.element_type AS element_type,
            p.now_cost / 10.0 AS Price,
            h.round AS GW,
            h.total_points,
            h.minutes,
            CAST(h.expected_goal_involvements AS FLOAT) AS xgi,
            AVG(h.total_points) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Avg_Pts,
            SUM(CAST(h.expected_goal_involvements AS FLOAT)) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Sum_xGI,
            AVG(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Avg_Mins,
            SUM(h.minutes) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Total_Mins,
            SUM(CASE WHEN h.minutes > 0 THEN 1 ELSE 0 END) OVER (
                PARTITION BY h.element_id
                ORDER BY h.round
                ROWS BETWEEN {window_size - 1} PRECEDING AND CURRENT ROW
            ) AS Rolling_Matches_Played,
            ROW_NUMBER() OVER (
                PARTITION BY h.element_id
                ORDER BY h.round DESC
            ) AS rn
        FROM player_match_history h
        INNER JOIN players p ON h.element_id = p.id
        INNER JOIN teams t ON p.team = t.id
    )
    SELECT
        element_id,
        code,
        photo,
        Player,
        Full_Name,
        Team,
        Club_Name,
        Team_ID,
        Pos,
        element_type,
        Price,
        GW AS Latest_GW,
        ROUND(Rolling_Avg_Pts, 2) AS Rolling_Avg_Pts,
        ROUND(Rolling_Sum_xGI, 2) AS Rolling_Sum_xGI,
        ROUND(Rolling_Avg_Mins, 1) AS Rolling_Avg_Mins,
        Rolling_Matches_Played,
        ROUND(
            CASE 
                WHEN Rolling_Total_Mins > 0 
                THEN (Rolling_Sum_xGI / Rolling_Total_Mins) * 90.0 
                ELSE 0.0 
            END, 2
        ) AS Rolling_xGI_per_90
    FROM ranked_matches
    WHERE rn = 1
    """
    df = pd.read_sql(rolling_query, _conn)
    if not df.empty:
        for col in [
            "Price", "Rolling_Avg_Pts", "Rolling_Sum_xGI", "Rolling_Avg_Mins",
            "Rolling_xGI_per_90", "Rolling_Matches_Played", "element_type"
        ]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df = df.dropna(subset=["Player"])
        df = df[df["Player"].astype(str).str.strip() != ""]
        df["_search_target"] = (
            df["Player"].fillna("")
            + " "
            + df["Full_Name"].fillna("")
            + " "
            + df["Team"].fillna("")
            + " "
            + df["Club_Name"].fillna("")
        ).str.strip()
    return df


@st.fragment
def render_rolling_form_tab(conn, current_gw, teams_fdr_map):
    col_t2_hdr, col_t2_pop = st.columns([6, 1])
    with col_t2_hdr:
        section_header(
            "Rolling Form & Projected xP Trends",
            "Analyze rolling points output and expected points trajectory vs fixture schedule",
        )
    with col_t2_pop:
        st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
        with st.popover("📖 Guide"):
            st.markdown(
                """
                **Form vs. Fixtures Scatter Matrix**
                
                * **Proj Form xP:** Blended expected points per match combining underlying rolling $xGI/90$, actual rolling points form, appearance security, and upcoming 5-GW fixture difficulty.
                * **Upcoming 5-GW FDR:** Cumulative fixture rating over the next 5 games (lower score = greener schedule).
                * **Price Filter:** Isolate players within your budget constraints.
                * **Min Matches Filter:** Filters out rotation risks so you only evaluate regular starters.
                """
            )

    table_exists = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_match_history'",
        conn,
    )

    if table_exists.empty:
        st.warning("⚠️ Match history table `player_match_history` was not found in `fpl.db`.")
        return

    effective_gw = max(1, current_gw)
    col_search2, col_w, col_pos2, col_min_matches, col_min_mins2, col_sort2 = (
        st.columns([1.4, 0.9, 0.8, 0.9, 0.9, 1.2])
    )
    with col_search2:
        search_query2 = st_keyup(
            "🔍 Search Player / Club",
            placeholder="e.g. Cherki, Saka, Chelsea, ARS...",
            debounce=250,
            key="tab2_search_keyup",
        )

    with col_w:
        window_size = st.slider(
            "Match Window",
            min_value=1,
            max_value=10,
            value=min(10, max(effective_gw, 5)),
            step=1,
            key="tab2_window",
        )
    with col_pos2:
        pos_filter2 = st.selectbox(
            "Position", ["All", "GKP", "DEF", "MID", "FWD"], key="tab2_pos"
        )
    with col_min_matches:
        min_matches = st.slider(
            "Min Matches",
            min_value=1,
            max_value=max(1, window_size),
            value=1,
            step=1,
            key="tab2_matches",
        )
    with col_min_mins2:
        min_avg_mins = st.slider(
            "Min Avg Mins", 0, 90, 45, step=15, key="tab2_mins"
        )
    with col_sort2:
        rolling_sort = st.selectbox(
            "Rank By",
            [
                "Projected Form xP / Match",
                "Rolling Avg Points",
                "Rolling Sum xGI",
                "Rolling xGI / 90",
                "Upcoming Fixture Ease",
                "Rolling Avg Minutes",
                "Price",
            ],
            key="tab2_sort",
        )

    col_price3, col_toggle_squad = st.columns([1.5, 1])
    with col_price3:
        max_price_filter_roll = st.slider(
            "Filter Max Price (£M)", 4.0, 15.5, 15.5, step=0.5, key="roll_max_price"
        )
    with col_toggle_squad:
        only_my_squad = st.toggle("🎯 Only My Squad Players", key="tab2_only_squad")

    raw_rolling_df = fetch_rolling_base_data(conn, window_size)
    if raw_rolling_df.empty:
        st.info("No rolling match history found.")
        return

    filtered_df = raw_rolling_df.copy()

    if pos_filter2 != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == pos_filter2]

    filtered_df = filtered_df[
        (filtered_df["Price"] <= max_price_filter_roll)
        & (filtered_df["Rolling_Avg_Mins"] >= min_avg_mins)
        & (filtered_df["Rolling_Matches_Played"] >= min_matches)
    ]

    filtered_df["Upcoming_FDR"] = (
        filtered_df["Team_ID"].map(teams_fdr_map).fillna(15).astype(int)
    )

    def calc_rolling_proj_xp(row):
        etype = int(row.get("element_type", 3))
        xgi90 = float(row.get("Rolling_xGI_per_90", 0))
        avg_mins = float(row.get("Rolling_Avg_Mins", 60))
        avg_pts = float(row.get("Rolling_Avg_Pts", 3.0))
        fdr = int(row.get("Upcoming_FDR", 15))

        app_pts = 2.0 * min(1.0, max(0.2, avg_mins / 75.0))
        att_weight = 4.2 if etype == 4 else (4.6 if etype == 3 else 3.5)
        underlying_xp = (xgi90 * att_weight) * (avg_mins / 90.0)
        schedule_mult = max(0.75, min(1.25, 1.0 + ((15 - fdr) / 30.0)))
        blended_raw = (0.55 * (app_pts + underlying_xp)) + (0.45 * avg_pts)
        return round(blended_raw * schedule_mult, 2)

    filtered_df["Proj_Form_xP"] = filtered_df.apply(calc_rolling_proj_xp, axis=1)

    active_manager_id = st.session_state.get("manager_id", "").strip()
    if only_my_squad and not filtered_df.empty:
        if not active_manager_id:
            st.info("💡 Enter your FPL Team ID in the top bar to filter by your squad.")
            filtered_df = filtered_df.iloc[0:0]
        else:
            squad_ids = get_manager_squad_ids(active_manager_id, current_gw)
            filtered_df = filtered_df[filtered_df["element_id"].isin(squad_ids)]

    has_search = bool(search_query2 and search_query2.strip())
    if has_search and not filtered_df.empty:
        q = search_query2.strip()
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
        sort_rolling_map = {
            "Projected Form xP / Match": ("Proj_Form_xP", False),
            "Rolling Avg Points": ("Rolling_Avg_Pts", False),
            "Rolling Sum xGI": ("Rolling_Sum_xGI", False),
            "Rolling xGI / 90": ("Rolling_xGI_per_90", False),
            "Upcoming Fixture Ease": ("Upcoming_FDR", True),
            "Rolling Avg Minutes": ("Rolling_Avg_Mins", False),
            "Price": ("Price", False),
        }
        r_col, r_asc = sort_rolling_map[rolling_sort]
        filtered_df = filtered_df.sort_values(by=r_col, ascending=r_asc)

    if filtered_df.empty:
        st.info("No players found matching the current rolling filter criteria.")
        return

    if len(filtered_df) >= 2:
        x_mid = float(filtered_df["Upcoming_FDR"].median())
        y_mid = float(filtered_df["Proj_Form_xP"].median())

        fig = px.scatter(
            filtered_df,
            x="Upcoming_FDR",
            y="Proj_Form_xP",
            color="Pos",
            size="Price",
            hover_name="Player",
            hover_data={
                "Team": True,
                "Price": ":.1f",
                "Proj_Form_xP": ":.2f",
                "Rolling_Avg_Pts": ":.2f",
                "Rolling_Sum_xGI": ":.2f",
                "Upcoming_FDR": True,
                "Rolling_Avg_Mins": ":.0f",
                "Rolling_Matches_Played": True,
                "Pos": False,
            },
            labels={
                "Upcoming_FDR": "Upcoming 5-GW Fixture Difficulty Rating (Lower = Easier)",
                "Proj_Form_xP": "Projected Form xP / Match",
                "Pos": "Position",
            },
            title="Projected Form vs Fixture Run (Proj Form xP vs Next 5 FDR)",
            color_discrete_map={
                "GKP": "#f59e0b",
                "DEF": "#3b82f6",
                "MID": "#10b981",
                "FWD": "#ef4444",
            },
        )

        fig.add_vline(x=x_mid, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)")
        fig.add_hline(y=y_mid, line_dash="dash", line_color="rgba(255, 255, 255, 0.25)")

        fig.update_layout(
            template="plotly_dark",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            paper_bgcolor="rgba(15, 23, 42, 0.0)",
            margin=dict(l=20, r=20, t=50, b=20),
            height=450,
        )
        st.plotly_chart(fig, use_container_width=True)

    top_rolling = filtered_df.head(min(5, len(filtered_df)))
    cols_r = st.columns(len(top_rolling))
    for i, (_, row) in enumerate(top_rolling.iterrows()):
        card_img = get_player_img_url(row.get("photo"), row.get("code"))
        proj_xp = float(row["Proj_Form_xP"])
        with cols_r[i]:
            render_list_card(
                f"{row['Player']} ({row['Team']})",
                [(row["Pos"], "blue"), (f"Proj {proj_xp:.1f} xP", "green")],
                f'<span>Price</span> £{fmt_num(row["Price"], ".1f")} · <span>Form xP</span>'
                f' <strong>{fmt_num(proj_xp, ".2f")}</strong> · <span>Avg Pts</span>'
                f' {fmt_num(row["Rolling_Avg_Pts"], ".1f")} · <span>Next 5 FDR</span>'
                f' {int(row["Upcoming_FDR"])}',
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
    .fdr-pill {{
        display: inline-block;
        padding: 0.15rem 0.55rem;
        border-radius: 4px;
        font-weight: 800;
        font-size: 0.82rem;
    }}
    .fdr-green {{ background: rgba(34, 197, 94, 0.2); color: {"#4ade80" if is_dark else "#15803d"}; }}
    .fdr-yellow {{ background: rgba(234, 179, 8, 0.2); color: {"#facc15" if is_dark else "#a16207"}; }}
    .fdr-red {{ background: rgba(239, 68, 68, 0.2); color: {"#f87171" if is_dark else "#b91c1c"}; }}
    </style>
    """

    display_df = filtered_df.head(35)
    html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
    html_out.append('<th style="text-align: left; padding-left: 1rem;">Player</th>')
    html_out.append('<th>Club</th><th>Pos</th><th>Price</th><th>GW</th>')
    html_out.append('<th>Proj Form xP</th>')
    html_out.append(f'<th>Avg Pts (L{window_size})</th><th>xGI (L{window_size})</th><th>xGI/90 (L{window_size})</th>')
    html_out.append(f'<th>Next 5 FDR</th><th>Mins (L{window_size})</th><th>Apps</th>')
    html_out.append('</tr></thead><tbody>')

    for _, row in display_df.iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        fdr_val = int(row["Upcoming_FDR"])
        fdr_cls = "fdr-green" if fdr_val <= 11 else ("fdr-yellow" if fdr_val <= 14 else "fdr-red")
        proj_xp = float(row["Proj_Form_xP"])

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
        html_out.append(f'<td>{int(row["Latest_GW"])}</td>')
        html_out.append(f'<td><span class="xp-pill">{proj_xp:.2f}</span></td>')
        html_out.append(f'<td style="font-weight: 700;">{row["Rolling_Avg_Pts"]:.2f}</td>')
        html_out.append(f'<td>{row["Rolling_Sum_xGI"]:.2f}</td>')
        html_out.append(f'<td>{row["Rolling_xGI_per_90"]:.2f}</td>')
        html_out.append(f'<td><span class="fdr-pill {fdr_cls}">{fdr_val}</span></td>')
        html_out.append(f'<td>{row["Rolling_Avg_Mins"]:.1f}</td>')
        html_out.append(f'<td>{int(row["Rolling_Matches_Played"])}</td>')
        html_out.append("</tr>")

    html_out.append("</tbody></table></div>")

    full_table_height = (len(display_df) * 45) + 60
    render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)