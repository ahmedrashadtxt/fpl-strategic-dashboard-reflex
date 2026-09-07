import math
import os
import pandas as pd
from rapidfuzz import fuzz, process
from st_keyup import st_keyup
import streamlit as st

from betting_engine import fetch_upcoming_betting_odds, get_fixture_market_xg_and_movement
from data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_manager_squad_ids,
)
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


def apply_target_market_projection(
    conn,
    base_proj_pts: float,
    pos: str,
    fdr: int,
    is_home: bool,
    team_short: str,
    opp_short: str,
    market_weight: float,
    factor_movement: bool,
    market_cache: dict,
) -> float:
    h_team = team_short if is_home else opp_short
    a_team = opp_short if is_home else team_short
    fdr_h = fdr if is_home else 3
    fdr_a = 3 if is_home else fdr

    mkt_h_xg, mkt_a_xg, mkt_h_cs, mkt_a_cs, mv = get_fixture_market_xg_and_movement(
        conn, h_team, a_team, fdr_h, fdr_a, market_cache
    )

    mkt_team_xg = mkt_h_xg if is_home else mkt_a_xg
    mkt_cs_prob = mkt_h_cs if is_home else mkt_a_cs
    team_mv = mv["home"] if is_home else mv["away"]

    fdr_base = max(0.6, 2.55 - (fdr * 0.35))
    blended_xg = ((1.0 - market_weight) * fdr_base) + (market_weight * mkt_team_xg)

    if factor_movement:
        blended_xg = max(0.4, blended_xg + (0.40 * team_mv["delta_xg"]))

    if pos in ("MID", "FWD"):
        xg_scale = blended_xg / max(fdr_base, 0.4)
        xg_scale = max(0.4, min(2.2, xg_scale))
        return round(base_proj_pts * xg_scale, 2)
    elif pos in ("GKP", "DEF"):
        base_cs_prob = max(0.05, min(0.65, math.exp(-max(0.6, fdr * 0.4))))
        blended_cs_prob = ((1.0 - market_weight) * base_cs_prob) + (market_weight * mkt_cs_prob)
        if factor_movement:
            blended_cs_prob = max(0.02, min(0.85, blended_cs_prob + (0.25 * team_mv["delta_win"])))
        cs_diff = (blended_cs_prob - base_cs_prob) * 4.0
        return round(max(0.5, base_proj_pts + cs_diff), 2)
    return round(base_proj_pts, 2)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_transfer_targets_base_data(_conn, current_gw: int, target_gw: int, enable_betting_target: bool, odds_api_key: str):
    """Caches base model evaluations and betting projections across all candidates."""
    query = """
    SELECT
        p.id,
        p.id AS element_id,
        p.code,
        p.photo,
        p.web_name AS Player,
        p.first_name || ' ' || p.second_name AS Full_Name,
        t.short_name AS Team,
        t.name AS Club_Name,
        p.team AS team_id,
        CASE p.element_type
            WHEN 1 THEN 'GKP'
            WHEN 2 THEN 'DEF'
            WHEN 3 THEN 'MID'
            WHEN 4 THEN 'FWD'
        END AS Pos,
        pos.singular_name AS Position,
        p.now_cost / 10.0 AS Cost,
        p.now_cost / 10.0 AS Price,
        p.minutes AS minutes,
        p.minutes AS Minutes,
        p.total_points AS Total_Points,
        p.total_points AS Season_Points,
        p.form AS Form,
        p.points_per_game AS PPG,
        p.expected_goals,
        p.expected_assists,
        p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE (p.status = 'a' OR p.chance_of_playing_next_round >= 75)
    """
    candidates_df = pd.read_sql(query, _conn)
    if candidates_df.empty:
        return pd.DataFrame()

    fixtures_df = pd.read_sql(
        """
        SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
               th.short_name AS Home_Team, ta.short_name AS Away_Team,
               f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
        FROM fixtures f
        INNER JOIN teams th ON f.team_h = th.id
        INNER JOIN teams ta ON f.team_a = ta.id
        WHERE f.event >= ? AND f.event <= ?
        """,
        _conn,
        params=[current_gw, current_gw + 4],
    )
    hist_baselines_df = get_historical_player_baselines(_conn)
    market_cache = fetch_upcoming_betting_odds(odds_api_key) if enable_betting_target else {}

    results = []
    for _, p_row in candidates_df.iterrows():
        fix_data = get_fixture_for_team(fixtures_df, p_row["team_id"], target_gw)
        base_xp = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)
        final_xp = base_xp

        if enable_betting_target and fix_data.get("opponent"):
            opp_short = fix_data["opponent"].replace(" (H)", "").replace(" (A)", "")
            final_xp = apply_target_market_projection(
                _conn,
                base_xp,
                p_row["Pos"],
                fix_data["fdr"],
                fix_data["is_home"],
                p_row["Team"],
                opp_short,
                market_weight=0.35,
                factor_movement=True,
                market_cache=market_cache,
            )

        price = float(p_row["Cost"])
        xp_per_mil = round(final_xp / max(price, 4.0), 2)

        row_dict = dict(p_row)
        row_dict.update({
            "Fixture": fix_data.get("opponent", "TBD"),
            "FDR": fix_data.get("fdr", 3),
            "Proj_xP": round(final_xp, 2),
            "xP_per_Mil": xp_per_mil,
        })
        results.append(row_dict)

    target_df = pd.DataFrame(results)
    if not target_df.empty:
        for col in ["Proj_xP", "xP_per_Mil", "Cost", "Price", "Form", "Total_Points", "Season_Points", "FDR"]:
            if col in target_df.columns:
                target_df[col] = pd.to_numeric(target_df[col], errors="coerce").fillna(0)

        target_df["_search_target"] = (
            target_df["Player"].fillna("")
            + " "
            + target_df["Full_Name"].fillna("")
            + " "
            + target_df["Team"].fillna("")
            + " "
            + target_df["Club_Name"].fillna("")
        ).str.strip()

    return target_df


@st.fragment
def render_transfer_market_tab(conn, current_gw):
    col_t5_hdr, col_t5_pop = st.columns([6, 1])
    with col_t5_hdr:
        section_header(
            "Transfer Target Finder",
            "Identify high-EV incoming transfer targets ranked by projected points and value efficiency",
        )
    with col_t5_pop:
        st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
        with st.popover("📖 Guide"):
            st.markdown(
                """
                **Target Finder & Value Metrics**
                
                * **Proj xP:** Projected points for the upcoming fixture using the Hybrid Model (Baseline Rate × Betting Implied Goals × Line Velocity).
                * **xP / £M:** Points efficiency per million pounds spent. High values highlight budget enablers with elite fixtures.
                * **Max Price Slider:** Set your exact budget limit to see the best available targets you can afford.
                * **Exclude My Squad:** Automatically hides players you currently own so you only browse genuine incoming replacements.
                """
            )

    next_gw_df = pd.read_sql(
        "SELECT id FROM events WHERE is_next = 1 LIMIT 1", conn
    )
    target_gw = int(next_gw_df["id"].values[0]) if not next_gw_df.empty else current_gw

    col_search5, col_pos5, col_sort5 = st.columns([1.5, 1, 1.2])
    with col_search5:
        search_query5 = st_keyup(
            "🔍 Search Player / Club",
            placeholder="e.g. Eze, Semenyo, Arsenal, LIV...",
            debounce=250,
            key="tab5_search_keyup",
        )
    with col_pos5:
        pos_filter5 = st.selectbox(
            "Filter Position", ["All", "GKP", "DEF", "MID", "FWD"], key="tab5_pos"
        )
    with col_sort5:
        sort_by5 = st.selectbox(
            "Rank Targets By",
            [
                "Projected Points (xP)",
                "Value Efficiency (xP / £M)",
                "Current Form",
                "Total Season Points",
                "Price (Low to High)",
            ],
            key="tab5_sort",
        )

    col_price5, col_excl5, col_mkt5 = st.columns([1.5, 1.1, 1.2])
    with col_price5:
        max_budget_filter = st.slider(
            "Target Max Price (£M)", 4.0, 15.5, 15.5, step=0.5, key="tab5_max_price"
        )
    with col_excl5:
        exclude_my_squad = st.toggle(
            "🚫 Exclude My Squad", value=True, key="tab5_exclude_squad"
        )
    with col_mkt5:
        enable_betting_target = st.toggle(
            "📊 Apply Betting Odds", value=True, key="tab5_betting_toggle"
        )

    odds_api_key = st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", ""))

    raw_targets_df = fetch_transfer_targets_base_data(
        conn, current_gw, target_gw, enable_betting_target, odds_api_key
    )

    if raw_targets_df.empty:
        st.info("No transfer targets available.")
        return

    filtered_df = raw_targets_df.copy()

    if pos_filter5 != "All":
        filtered_df = filtered_df[filtered_df["Pos"] == pos_filter5]

    filtered_df = filtered_df[filtered_df["Cost"] <= max_budget_filter]

    active_manager_id = st.session_state.get("manager_id", "").strip()
    if exclude_my_squad and active_manager_id and not filtered_df.empty:
        squad_ids = get_manager_squad_ids(active_manager_id, current_gw)
        filtered_df = filtered_df[~filtered_df["id"].isin(squad_ids)]

    has_search = bool(search_query5 and search_query5.strip())

    if has_search and not filtered_df.empty:
        q = search_query5.strip()
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
        sort_options = {
            "Projected Points (xP)": ("Proj_xP", False),
            "Value Efficiency (xP / £M)": ("xP_per_Mil", False),
            "Current Form": ("Form", False),
            "Total Season Points": ("Total_Points", False),
            "Price (Low to High)": ("Cost", True),
        }
        sort_col, sort_asc = sort_options[sort_by5]
        filtered_df = filtered_df.sort_values(by=sort_col, ascending=sort_asc)

    if filtered_df.empty:
        if search_query5.strip() and exclude_my_squad:
            st.info(
                f"No players found matching '{search_query5}'. "
                "If this player is already in your squad, turn off **Exclude My Squad** to view them."
            )
        else:
            st.info("No players found matching your criteria. Try adjusting your filters.")
        return

    top_targets = filtered_df.head(min(4, len(filtered_df)))
    card_cols = st.columns(len(top_targets))
    for i, (_, row) in enumerate(top_targets.iterrows()):
        card_img = get_player_img_url(row.get("photo"), row.get("code"))
        with card_cols[i]:
            render_list_card(
                f"{row['Player']} ({row['Team']})",
                [(row["Pos"], "blue"), (f"GW{target_gw} Target", "green")],
                f'<span>Price</span> £{fmt_num(row["Cost"], ".1f")} · <span>xP</span>'
                f' <strong>{fmt_num(row["Proj_xP"], ".1f")}</strong> · <span>Val</span>'
                f' {fmt_num(row["xP_per_Mil"], ".2f")}xP/£M · <span>Fix</span>'
                f' {row["Fixture"]}',
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
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.75rem;
    }}
    .fdr-easy {{ background: rgba(34, 197, 94, 0.2); color: {"#4ade80" if is_dark else "#15803d"}; }}
    .fdr-med {{ background: rgba(234, 179, 8, 0.2); color: {"#facc15" if is_dark else "#a16207"}; }}
    .fdr-hard {{ background: rgba(239, 68, 68, 0.2); color: {"#f87171" if is_dark else "#b91c1c"}; }}
    </style>
    """

    display_df = filtered_df.head(35)
    html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
    html_out.append('<th style="text-align: left; padding-left: 1rem;">Target Player</th>')
    html_out.append('<th>Club</th><th>Pos</th><th>Price</th><th>GW Fixture</th><th>FDR</th>')
    html_out.append('<th>Proj xP</th><th>xP / £M</th><th>Form</th><th>Season Pts</th>')
    html_out.append('</tr></thead><tbody>')

    for _, row in display_df.iterrows():
        p_img = get_player_img_url(row.get("photo"), row.get("code"))
        fdr = int(row["FDR"])
        fdr_cls = "fdr-easy" if fdr <= 2 else ("fdr-med" if fdr == 3 else "fdr-hard")

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
        html_out.append(f'<td>£{row["Cost"]:.1f}</td>')
        html_out.append(f'<td>{row["Fixture"]}</td>')
        html_out.append(f'<td><span class="fdr-pill {fdr_cls}">FDR {fdr}</span></td>')
        html_out.append(f'<td><span class="xp-pill">{row["Proj_xP"]:.1f}</span></td>')
        html_out.append(f'<td style="font-weight: 700;">{row["xP_per_Mil"]:.2f}</td>')
        html_out.append(f'<td>{row["Form"]}</td>')
        html_out.append(f'<td>{int(row["Total_Points"])}</td>')
        html_out.append("</tr>")

    html_out.append("</tbody></table></div>")

    full_table_height = (len(display_df) * 45) + 60
    render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)