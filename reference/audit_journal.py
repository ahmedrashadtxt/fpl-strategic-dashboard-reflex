import sqlite3
import pandas as pd
import streamlit as st
import json
from theme import render_guide_popover, section_header
from datetime import datetime

# ── Local Imports ─────────────────────────────────────────────────────────────
from data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_teams_fdr_map,
    solve_optimal_xi,
)
from .squad_analyzer import (
    fetch_manager_entry,
    fetch_manager_picks,
    fetch_live_gameweek_points,
    render_pitch_component,
    get_rolling_player_metrics,
)

try:
    from audit_db import (
        init_audit_tables,
        save_pre_gw_snapshot,
        settle_post_gw_snapshot,
        get_snapshot,
        get_all_gw_versions,
        is_owner_manager,
    )
except (ImportError, Exception):
    import sys
    if "audit_db" in sys.modules:
        try:
            import importlib
            import audit_db
            importlib.reload(audit_db)
            from audit_db import (
                init_audit_tables,
                save_pre_gw_snapshot,
                settle_post_gw_snapshot,
                get_snapshot,
                get_all_gw_versions,
                is_owner_manager,
            )
        except Exception:
            def init_audit_tables(conn): pass
            def save_pre_gw_snapshot(*args, **kwargs): return 1
            def settle_post_gw_snapshot(*args, **kwargs): return False
            def get_snapshot(*args, **kwargs): return None
            def get_all_gw_versions(*args, **kwargs): return []
            def is_owner_manager(manager_id=None): return False
    else:
        def init_audit_tables(conn): pass
        def save_pre_gw_snapshot(*args, **kwargs): return 1
        def settle_post_gw_snapshot(*args, **kwargs): return False
        def get_snapshot(*args, **kwargs): return None
        def get_all_gw_versions(*args, **kwargs): return []
        def is_owner_manager(manager_id=None): return False


POS_MAP = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


# ── Solver Helper ─────────────────────────────────────────────────────────────
def compute_active_solver_squad(conn, manager_id: str, target_gw: int, current_gw: int):
    picks_data = fetch_manager_picks(manager_id, target_gw, current_gw)
    picks_list = picks_data.get("picks", [])
    if not picks_list:
        return None, "No squad picks found for this FPL ID."

    pick_ids = [p["element"] for p in picks_list]
    placeholders = ",".join(["?"] * len(pick_ids))

    squad_query = f"""
    SELECT
        p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
        t.short_name AS Team,
        CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
        p.element_type, pos.singular_name AS Position, p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
        p.total_points AS Season_Points, p.expected_goals, p.expected_assists,
        p.form AS Form, p.points_per_game AS PPG, p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.news AS News, p.status AS Status, p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE p.id IN ({placeholders})
    """
    squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
    if squad_df.empty:
        return None, "Failed to load player data from database."

    adv_fixtures_query = """
    SELECT
        f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
        th.short_name AS Home_Team, ta.short_name AS Away_Team,
        f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
    FROM fixtures f
    INNER JOIN teams th ON f.team_h = th.id
    INNER JOIN teams ta ON f.team_a = ta.id
    WHERE f.event >= ? AND f.event <= ?
    """
    adv_fix_df = pd.read_sql(adv_fixtures_query, conn, params=[current_gw, max(19, target_gw)])
    hist_baselines_df = get_historical_player_baselines(conn)

    squad_eval_list = []
    for _, p_row in squad_df.iterrows():
        fix_data = get_fixture_for_team(adv_fix_df, p_row["team_id"], target_gw)
        proj_pts = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)

        p_eval = dict(p_row)
        p_eval.update({
            "Opponent": fix_data.get("opponent", "—"),
            "FDR": fix_data.get("fdr", 3),
            "Proj_Pts": round(proj_pts, 2),
            "predicted_xp": round(proj_pts, 2),
            "web_name": p_row["Player"],
            "Player": p_row["Player"],
            "Pos": p_row["Pos"],
        })
        squad_eval_list.append(p_eval)

    eval_df = pd.DataFrame(squad_eval_list)
    optimal_xi, optimal_bench, formation = solve_optimal_xi(eval_df)

    optimal_xi = optimal_xi.sort_values("Proj_Pts", ascending=False).reset_index(drop=True)
    optimal_xi["is_starter"] = True
    optimal_xi["is_cap"] = False
    optimal_xi["is_vc"] = False
    optimal_xi["Multiplier"] = 1

    if len(optimal_xi) > 0:
        optimal_xi.loc[0, "is_cap"] = True
        optimal_xi.loc[0, "Multiplier"] = 2
    if len(optimal_xi) > 1:
        optimal_xi.loc[1, "is_vc"] = True

    optimal_bench["is_starter"] = False
    optimal_bench["is_cap"] = False
    optimal_bench["is_vc"] = False
    optimal_bench["Multiplier"] = 1

    full_lineup_df = pd.concat([optimal_xi, optimal_bench], ignore_index=True)
    full_lineup_records = full_lineup_df.to_dict(orient="records")

    for r in full_lineup_records:
        r["is_captain"] = bool(r.get("is_cap", False))
        r["is_vice"] = bool(r.get("is_vc", False))

    return full_lineup_records, None


# ── Tab Renderer ─────────────────────────────────────────────────────────────
def render_audit_journal_tab(conn, events_df, current_gw, player_pool_df=None):
    mgr_to_use = st.session_state.get("manager_id", "").strip()
    if not is_owner_manager(mgr_to_use):
        return

    init_audit_tables(conn)
    is_dark = st.session_state.get("theme_mode", "dark") == "dark"

    col_hdr, col_pop = st.columns([6.2, 0.8], vertical_alignment="center")
    with col_hdr:
        section_header(
            "Model Audit & Performance Journal",
            "Inspect locked solver versions, track pre-match line shifts, and audit prediction variance against final outcomes.",
        )
    with col_pop:
        render_guide_popover(
            title="Model Audit & Performance Journal",
            subtitle="Inspect locked solver versions, track pre-match line shifts, and audit prediction variance against final outcomes",
            items=[
                {"badge": "Snapshots", "title": "Pre-Deadline Snapshots", "desc": "Inspect immutable lineup versions locked before each gameweek deadline to evaluate model projections against actual points.", "color": "#38bdf8"},
                {"badge": "Versions", "title": "Iteration History", "desc": "Audit each transfer plan revision, formation change, and captain switch made throughout the gameweek window.", "color": "#10b981"},
                {"badge": "Settlement", "title": "Official Match Settlement", "desc": "Fetch official live/settled FPL points and calculate total squad variance against baseline predictions.", "color": "#818cf8"},
                {"badge": "Residuals", "title": "Over/Underperformance Analysis", "desc": "Pinpoint individual player residuals to separate bad variance (unlucky finishing) from model blind spots.", "color": "#f59e0b"},
                {"badge": "Multi-Manager", "title": "Manager Account Isolation", "desc": "All snapshot versions, locks, and settlement states are strictly scoped to your active FPL Team ID.", "color": "#38bdf8"},
            ],
            tip="Regularly audit your captain prediction residuals post-gameweek to assess whether your vice-captain was statistically favored by underlying metrics.",
            key="guide_pop_audit_journal",
        )

    # ── Controls Bar ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1.5, 2.0, 1.3, 1.3], vertical_alignment="bottom")

    with c1:
        selected_gw = st.selectbox(
            "Gameweek:",
            options=list(range(1, 39)),
            index=max(0, min(current_gw - 1, 37)),
            key="audit_gw_selector",
        )

    all_versions = get_all_gw_versions(conn, mgr_to_use, selected_gw)
    has_snapshots = len(all_versions) > 0

    with c2:
        if has_snapshots:
            version_options = [v["version"] for v in all_versions]
            selected_version = st.selectbox(
                "Snapshot Version:",
                options=version_options,
                format_func=lambda ver: (
                    f"Version {ver} (Latest / Final)" if ver == version_options[0] 
                    else f"Version {ver} (Locked {next((v.get('created_at') or '')[:16].replace('T', ' ') for v in all_versions if v['version'] == ver)} UTC)"
                ),
                key=f"audit_ver_select_gw_{selected_gw}",
            )
        else:
            selected_version = None
            st.selectbox("Snapshot Version:", options=["No locks recorded"], disabled=True)

    snapshot = get_snapshot(conn, mgr_to_use, selected_gw, version=selected_version) if has_snapshots else None

    with c3:
        if st.button(":material/lock:  Lock New Version", key=f"lock_btn_gw_{selected_gw}", width='stretch'):
            with st.spinner(f"Computing new version for GW{selected_gw}..."):
                lineup_records, err = compute_active_solver_squad(conn, mgr_to_use, selected_gw, current_gw)
                if err:
                    st.error(err)
                else:
                    new_ver = save_pre_gw_snapshot(conn, mgr_to_use, selected_gw, lineup_records, transfers_data=[], source="Audit Journal")
                    st.toast(f"GW{selected_gw} locked as Version {new_ver}!", icon=":material/check_circle: ")
                    st.rerun()

    with c4:
        if st.button(":material/sync:  Settle Outcomes", key=f"settle_btn_gw_{selected_gw}", width='stretch'):
            if not snapshot:
                st.warning("Lock a solver version before settling match outcomes.")
            else:
                with st.spinner(f"Fetching official points for GW{selected_gw}..."):
                    raw_live_map = fetch_live_gameweek_points(selected_gw)
                    if not raw_live_map:
                        st.error(f"Live data for GW{selected_gw} is not available yet.")
                    else:
                        clean_points_map = {
                            pid: data.get("total_points", data.get("points", 0)) if isinstance(data, dict) else data 
                            for pid, data in raw_live_map.items()
                        }
                        settle_post_gw_snapshot(conn, mgr_to_use, selected_gw, clean_points_map, target_version=selected_version)
                        st.toast(f"GW{selected_gw} Version {selected_version} settled!", icon=":material/check_circle: ")
                        st.rerun()

    if not snapshot:
        st.info(f"No snapshot logged for **GW {selected_gw}**. Click **:material/lock:  Lock New Version** or lock your team in the **Squad Analyzer** tab.")
        return

    # ── Summary Metrics ───────────────────────────────────────────────────────
    st.divider()
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    
    is_settled = (snapshot.get("status") == "SETTLED")
    var = snapshot.get("variance_pts")
    pred_total_val = float(snapshot.get("predicted_total") or 0.0)

    m1.metric("Status", "Settled :material/check_circle: " if is_settled else "Pre-Lock :material/lock: ")
    m2.metric("Viewing Version", f"v{snapshot.get('version', 1)} of {len(all_versions)}")
    m3.metric("Projected Total", f"{pred_total_val:.1f} xP")
    m4.metric("Actual Score", f"{snapshot['actual_total']} pts" if is_settled else "Pending :material/hourglass_bottom: ")
    m5.metric("Model Variance", f"{var:+.1f} pts" if var is not None else "-", delta=var if var is not None else None)
    m6.metric("Bench Left", f"{snapshot['bench_points']} pts" if snapshot.get("bench_points") is not None else "-")

    # ── Multi-Version Evolution Table (Only Rendered if >= 2 Versions Exist) ───
    if len(all_versions) > 1:
        st.markdown("#### :material/receipt_long:  Version Iteration History")
        hist_rows = []
        for v in all_versions:
            is_cur = (v.get("version") == selected_version)
            created_str = v.get("created_at")
            lock_time = created_str[:16].replace("T", " ") if created_str else "-"
            mkt_weight = v.get("market_weight")
            mkt_weight_val = float(mkt_weight) if mkt_weight is not None else 0.35
            pred_tot = float(v.get("predicted_total") or 0.0)

            hist_rows.append({
                "Version": f"v{v.get('version', 1)}" + (" (Viewing)" if is_cur else ""),
                "Source": v.get("source", "Squad Analyzer"),
                "Locked At (UTC)": lock_time,
                "Formation": v.get("formation") or "4-4-2",
                "Market Weight": f"{mkt_weight_val:.2f}",
                "Projected Total": f"{pred_tot:.1f} xP",
                "Captain": v.get("captain_name") or "-",
                "Actual Score": f"{v['actual_total']} pts" if v.get("actual_total") is not None else "Pending",
                "Variance": f"{v['variance_pts']:+.1f} pts" if v.get("variance_pts") is not None else "-",
            })
        st.dataframe(pd.DataFrame(hist_rows), hide_index=True, use_container_width=True)

    # ── Reconstruct Lineup Data ───────────────────────────────────────────────
    lineup = snapshot.get("lineup", [])
    for p in lineup:
        if "Pos" not in p or not p["Pos"]:
            p["Pos"] = POS_MAP.get(p.get("element_type", 0), "MID")
        if "Player" not in p or not p["Player"]:
            p["Player"] = p.get("web_name", "Unknown")
        if "web_name" not in p:
            p["web_name"] = p["Player"]
        if "Cost" not in p:
            p["Cost"] = p.get("now_cost", 50) / 10.0 if "now_cost" in p else 5.0
        if "photo" not in p:
            p["photo"] = ""
        if "code" not in p:
            p["code"] = None
        if "Team" not in p:
            p["Team"] = ""
        if "Opponent" not in p:
            p["Opponent"] = "—"
        if "Proj_Pts" not in p:
            p["Proj_Pts"] = float(p.get("predicted_xp", 0.0) or 0.0)

        p["GW_Points"] = (p.get("actual_pts", 0) or 0) * int(p.get("Multiplier", 1) or 1)
        p["Raw_GW_Pts"] = int(p.get("actual_pts", 0) or 0)
        p["is_cap"] = bool(p.get("is_captain", False) or p.get("is_cap", False))
        p["is_vc"] = bool(p.get("is_vice", False) or p.get("is_vc", False))
        p["Multiplier"] = 2 if p["is_cap"] else 1

    df_all = pd.DataFrame(lineup)
    if "is_starter" not in df_all.columns:
        df_all["is_starter"] = [i < 11 for i in range(len(df_all))]

    starters_df = df_all[df_all["is_starter"] == True].copy()
    bench_df = df_all[df_all["is_starter"] == False].copy()

    # ── Display Header & View Mode ────────────────────────────────────────────
    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    c_view_title, c_view_toggle = st.columns([3, 1], vertical_alignment="center")
    with c_view_title:
        st.markdown(f"### :material/shield:  Locked Lineup: GW{selected_gw} (Version {selected_version})")
    with c_view_toggle:
        view_mode = st.radio("View Mode:", ["Pitch", "Table"], horizontal=True, key=f"view_mode_gw_{selected_gw}")

    if view_mode == "Pitch":
        rolling_metrics_df = get_rolling_player_metrics(conn)
        teams_fdr_map = get_teams_fdr_map(conn, current_gw)
        render_pitch_component(
            starters_df,
            bench_df,
            is_live=is_settled,
            rolling_df=rolling_metrics_df,
            fdr_map=teams_fdr_map,
        )
    else:
        st.markdown("#### Starting XI")
        table_starters = pd.DataFrame([{
            "Role": "Captain" if p.get("is_cap") else ("Vice" if p.get("is_vc") else "Starter"),
            "Player": p["web_name"],
            "Team": p.get("Team", "-"),
            "Pos": p.get("Pos", "-"),
            "Projected xP": f"{p.get('Proj_Pts', 0.0):.1f}",
            "Actual Score": f"{p.get('actual_pts', 0)} pts" if is_settled else "Pending",
            "Variance (Δ)": f"{p.get('actual_pts', 0) - p.get('Proj_Pts', 0.0):+.1f} pts" if is_settled else "-",
        } for _, p in starters_df.iterrows()])
        st.dataframe(table_starters, hide_index=True, use_container_width=True)

        if not bench_df.empty:
            st.markdown("#### Bench Dugout")
            table_bench = pd.DataFrame([{
                "Role": f"Sub {idx}",
                "Player": p["web_name"],
                "Team": p.get("Team", "-"),
                "Pos": p.get("Pos", "-"),
                "Projected xP": f"{p.get('Proj_Pts', 0.0):.1f}",
                "Actual Score": f"{p.get('actual_pts', 0)} pts" if is_settled else "Pending",
            } for idx, (_, p) in enumerate(bench_df.iterrows())])
            st.dataframe(table_bench, hide_index=True, use_container_width=True)

    # ── Post-Gameweek Error Decomposition (Settled Only) ──────────────────────
    if is_settled:
        st.markdown("### :material/search:  Post-Match Residual Analysis")
        st.caption("Decomposes model accuracy to separate tactical execution from match variance.")

        r1, r2 = st.columns(2)
        starters_analysis = starters_df.copy()
        starters_analysis["delta"] = starters_analysis["Raw_GW_Pts"] - starters_analysis["Proj_Pts"]

        with r1:
            st.markdown("##### :material/circle:  Top Positive Differentials (Beat Projection)")
            top_over = starters_analysis.sort_values("delta", ascending=False).head(3)
            over_table = pd.DataFrame([{
                "Player": r["web_name"],
                "Projected": f"{r['Proj_Pts']:.1f} xP",
                "Actual": f"{r['Raw_GW_Pts']} pts",
                "Gain": f"{r['delta']:+.1f} pts"
            } for _, r in top_over.iterrows()])
            st.dataframe(over_table, hide_index=True, use_container_width=True)

        with r2:
            st.markdown("##### :material/circle:  Top Variance Leaks (Underperformed Projection)")
            top_under = starters_analysis.sort_values("delta", ascending=True).head(3)
            under_table = pd.DataFrame([{
                "Player": r["web_name"],
                "Projected": f"{r['Proj_Pts']:.1f} xP",
                "Actual": f"{r['Raw_GW_Pts']} pts",
                "Loss": f"{r['delta']:+.1f} pts"
            } for _, r in top_under.iterrows()])
            st.dataframe(under_table, hide_index=True, use_container_width=True)