import streamlit as st
import pandas as pd
import numpy as np
from rapidfuzz import fuzz
from st_keyup import st_keyup
from data import get_manager_squad_ids, solve_optimal_xi, calculate_projected_points
from simulation_engine import build_odds_map, run_gameweek_simulation, run_head_to_head_simulation
from theme import render_guide_popover, section_header
from tabs.squad_analyzer import get_cached_league_eval_df, get_cached_league_dream_15

def render_simulator_tab(conn, events_df, current_gw):
    col_hdr, col_pop = st.columns([6.2, 0.8], vertical_alignment="center")
    with col_hdr:
        section_header(
            "Monte Carlo Gameweek Simulator",
            "Stress-test your squad across thousands of probabilistic match outcomes.",
        )
    with col_pop:
        render_guide_popover(
            title="Monte Carlo Gameweek Simulator",
            subtitle="Stress-test your squad across thousands of probabilistic match outcomes",
            items=[
                {"badge": "Target GW", "title": "Fixture Simulation Target", "desc": "Select any future gameweek to simulate based on bookmaker clean sheet and anytime goalscorer odds.", "color": "#38bdf8"},
                {"badge": "Squad Source", "title": "Flexible Squad Selection", "desc": "Test your active FPL squad, locked transfer plan, Budget Dream 15, or build a custom 15-player team.", "color": "#10b981"},
                {"badge": "Iterations", "title": "Monte Carlo Precision", "desc": "Simulate 1,000 to 10,000 probabilistic iterations to model player goal distributions and variance tails.", "color": "#818cf8"},
                {"badge": "Sandbox", "title": "Custom 15-Player Sandbox", "desc": "Build hypothetical wildcard teams with fuzzy search, live budget tracking, and club limit enforcement.", "color": "#f59e0b"},
                {"badge": "Benchmark", "title": "Head-to-Head Comparison", "desc": "Directly compare point distributions between your current team and your planned transfer squad.", "color": "#38bdf8"},
                {"badge": "Risk Metrics", "title": "Percentile Ranges & Win %", "desc": "Assess 10th percentile floor safety, median expectation, and 90th percentile ceiling boom potential.", "color": "#10b981"},
            ],
            tip="Focus on 10th percentile floor projections when defending a mini-league lead, and 90th percentile ceiling when chasing aggressive rank swings.",
            key="guide_pop_simulator",
        )
            
    st.markdown("#### Target Gameweek")
    all_gws = events_df[events_df["id"] >= current_gw]["id"].tolist()
    if not all_gws:
        all_gws = [current_gw]
        
    selected_gw = st.selectbox("Simulate Gameweek:", all_gws, label_visibility="collapsed")
    
    st.markdown("#### Squad Source")
    if "sim_squad_mode" not in st.session_state:
        st.session_state["sim_squad_mode"] = ":material/person:  My Active Squad"
        
    b1, b2, b3, b4 = st.columns(4)
    def set_squad(mode):
        st.session_state["sim_squad_mode"] = mode
        
    with b1:
        if st.button(":material/person:  My Active Squad", key="chip_btn_sim_1", type="primary" if st.session_state["sim_squad_mode"] == ":material/person:  My Active Squad" else "secondary", use_container_width=True):
            set_squad(":material/person:  My Active Squad")
            st.rerun()
    with b2:
        if st.button(":material/sync:  Post-Transfer Plan", key="chip_btn_sim_2", type="primary" if st.session_state["sim_squad_mode"] == ":material/sync:  Post-Transfer Plan" else "secondary", use_container_width=True):
            set_squad(":material/sync:  Post-Transfer Plan")
            st.rerun()
    with b3:
        if st.button(":material/star:  Budget Dream 15", key="chip_btn_sim_3", type="primary" if st.session_state["sim_squad_mode"] == ":material/star:  Budget Dream 15" else "secondary", use_container_width=True):
            set_squad(":material/star:  Budget Dream 15")
            st.rerun()
    with b4:
        if st.button(":material/build:  Custom 15-Player Sandbox", key="chip_btn_sim_4", type="primary" if st.session_state["sim_squad_mode"] == ":material/build:  Custom 15-Player Sandbox" else "secondary", use_container_width=True):
            set_squad(":material/build:  Custom 15-Player Sandbox")
            st.rerun()
            
    squad_mode = st.session_state["sim_squad_mode"]
                          
    manager_id = st.session_state.get("manager_id", "")
    
    # Load Squad based on mode
    squad_df = None
    
    if squad_mode == ":material/person:  My Active Squad":
        if st.session_state.get("active_squad_sim_df") is not None:
            squad_df = st.session_state["active_squad_sim_df"].copy()
            st.success(":material/check_circle:  Simulating your **Saved Optimal Squad** from Squad Analyzer.")
        else:
            if not manager_id:
                st.info("Please enter your FPL ID in the top header to load your active squad.")
                return
            
            squad_ids = get_manager_squad_ids(manager_id, selected_gw)
            if not squad_ids:
                st.warning("Could not fetch active squad. Try a different GW or check ID.")
                return
                
            players_query = f"SELECT * FROM players WHERE id IN ({','.join(map(str, squad_ids))})"
            squad_df = pd.read_sql_query(players_query, conn)
        
    elif squad_mode == ":material/sync:  Post-Transfer Plan":
        transfer_result = st.session_state.get("transfer_result", {})
        if "transferred_squad_df" not in transfer_result:
            st.info("No active transfer plan found in session state. Please visit the Transfer Analyzer to solve transfers first.")
            return
        squad_df = transfer_result["transferred_squad_df"]
        
    elif squad_mode == ":material/star:  Budget Dream 15":
        if "budget_dream_15_df" not in st.session_state:
            st.info("No Budget Dream 15 found. Please visit Squad Analyzer to generate and save it.")
            return
        squad_df = st.session_state["budget_dream_15_df"]
        
    elif squad_mode == ":material/build:  Custom 15-Player Sandbox":
        full_pool_df = get_cached_league_eval_df(conn, current_gw, selected_gw)
        # Create image URLs for the data editor
        full_pool_df["Photo"] = full_pool_df["photo"].apply(
            lambda x: f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(x).replace('.jpg', '.png')}" if pd.notna(x) and str(x).strip() != "" and "Photo-Missing" not in str(x) else "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"
        )

        if "sandbox_selected_ids" not in st.session_state:
            st.session_state["sandbox_selected_ids"] = []

        col_table, col_tracker = st.columns([2, 1], gap="large")

        with col_table:
            st.markdown("##### :material/search:  Player Pool & Selection")
            f_col1, f_col2 = st.columns([1.6, 1])
            with f_col1:
                search_query = st_keyup(
                    "Search player or club:",
                    placeholder="e.g. Palmer, Haaland, ARS, LIV...",
                    key="sandbox_search_input",
                    debounce=250,
                )
            with f_col2:
                pos_filter = st.multiselect(
                    "Position:",
                    options=["GKP", "DEF", "MID", "FWD"],
                    default=[],
                    key="sandbox_pos_filter",
                )

            filtered_pool = full_pool_df.copy()
            if pos_filter:
                filtered_pool = filtered_pool[filtered_pool["Pos"].isin(pos_filter)]
            if search_query and search_query.strip():
                query_clean = search_query.strip().lower()
                def match_score(row):
                    p_score = fuzz.partial_ratio(query_clean, str(row['Player']).lower())
                    t_score = fuzz.partial_ratio(query_clean, str(row['Team']).lower())
                    return max(p_score, t_score)

                filtered_pool["score"] = filtered_pool.apply(match_score, axis=1)
                filtered_pool = filtered_pool[filtered_pool["score"] >= 65].sort_values("score", ascending=False)

            # Build display columns
            display_cols = ["id", "Photo", "Player", "Team", "Pos", "Cost", "Proj_Pts", "Opponent", "FDR"]
            avail_cols = [c for c in display_cols if c in filtered_pool.columns]
            display_df = filtered_pool[avail_cols].copy()
            display_df.insert(0, "Select", display_df["id"].isin(st.session_state["sandbox_selected_ids"]))

            # Sort: selected players at top, then highest match score if searching, else highest projected points
            if search_query and search_query.strip() and "score" in filtered_pool.columns:
                display_df["score"] = filtered_pool["score"]
                display_df = display_df.sort_values(by=["Select", "score", "Proj_Pts"], ascending=[False, False, False]).drop(columns=["score"])
            else:
                display_df = display_df.sort_values(by=["Select", "Proj_Pts"], ascending=[False, False])

            # Unique key taking search, pos, and session state version counter
            editor_ver = st.session_state.get("sandbox_ver", 0)
            editor_key = f"sandbox_editor_{hash((str(search_query or ''), tuple(sorted(pos_filter))))}_{editor_ver}"

            edited_df = st.data_editor(
                display_df,
                hide_index=True,
                disabled=[c for c in display_df.columns if c != "Select"],
                column_config={
                    "Select": st.column_config.CheckboxColumn("Select", default=False),
                    "Photo": st.column_config.ImageColumn("Image"),
                    "Player": st.column_config.TextColumn("Player"),
                    "Team": st.column_config.TextColumn("Club"),
                    "Pos": st.column_config.TextColumn("Pos"),
                    "Cost": st.column_config.NumberColumn("Cost", format="£%.1f"),
                    "Proj_Pts": st.column_config.NumberColumn("Proj xP", format="%.1f"),
                    "Opponent": st.column_config.TextColumn("Fixture"),
                    "FDR": st.column_config.NumberColumn("FDR"),
                    "id": None,
                },
                use_container_width=True,
                height=480,
                key=editor_key,
            )

            # Sync checkbox selections with session state
            if edited_df is not None and not edited_df.empty:
                newly_selected = set(edited_df[edited_df["Select"] == True]["id"]) - set(st.session_state["sandbox_selected_ids"])
                newly_deselected = (set(edited_df[edited_df["Select"] == False]["id"]) & set(st.session_state["sandbox_selected_ids"])) & set(display_df["id"])

                if newly_selected or newly_deselected:
                    cur_set = set(st.session_state["sandbox_selected_ids"])
                    rejected = False

                    # Check constraints for newly selected players
                    for pid in newly_selected:
                        temp_set = cur_set.copy()
                        temp_set.add(pid)
                        temp_df = full_pool_df[full_pool_df["id"].isin(temp_set)]

                        if len(temp_set) > 15:
                            st.toast("Cannot select more than 15 players.", icon="⚠️")
                            rejected = True
                            break
                        if round(float(temp_df["Cost"].sum()), 2) > 100.0:
                            st.toast("Budget exceeded (£100.0m max).", icon="⚠️")
                            rejected = True
                            break
                        if temp_df["Team"].value_counts().max() > 3:
                            st.toast("Max 3 players per club allowed.", icon="⚠️")
                            rejected = True
                            break

                        pos_counts = temp_df["Pos"].value_counts().to_dict()
                        if pos_counts.get("GKP", 0) > 2 or pos_counts.get("DEF", 0) > 5 or pos_counts.get("MID", 0) > 5 or pos_counts.get("FWD", 0) > 3:
                            st.toast("Position limits exceeded (Max 2 GKP, 5 DEF, 5 MID, 3 FWD).", icon="⚠️")
                            rejected = True
                            break

                        cur_set.add(pid) # Valid, add them

                    cur_set.difference_update(newly_deselected)
                    st.session_state["sandbox_selected_ids"] = list(cur_set)

                    if rejected:
                        # Force editor to re-render to uncheck the rejected box
                        st.session_state["sandbox_ver"] = st.session_state.get("sandbox_ver", 0) + 1

                    st.rerun()

        with col_tracker:
            selected_ids = st.session_state["sandbox_selected_ids"]
            selected_df = full_pool_df[full_pool_df["id"].isin(selected_ids)].copy()

            n_selected = len(selected_df)
            total_cost = float(selected_df["Cost"].sum()) if not selected_df.empty else 0.0
            budget_remaining = 100.0 - total_cost

            # Position counts
            pos_counts = selected_df["Pos"].value_counts().to_dict() if not selected_df.empty else {}
            gk_cnt = pos_counts.get("GKP", 0)
            def_cnt = pos_counts.get("DEF", 0)
            mid_cnt = pos_counts.get("MID", 0)
            fwd_cnt = pos_counts.get("FWD", 0)

            # Team limits
            team_counts = selected_df["Team"].value_counts().to_dict() if not selected_df.empty else {}
            max_team = max(team_counts.values()) if team_counts else 0
            teams_exceeded = [t for t, c in team_counts.items() if c > 3]

            st.markdown("##### :material/checklist:  Constraints Tracker")

            # Quick Actions: Random 15 and Load Budget 15
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button(":material/casino:  Random 15", use_container_width=True, key="sandbox_btn_random"):
                    p_df = full_pool_df.copy()
                    p_df["weight"] = p_df["Proj_Pts"].clip(lower=1.0) + (p_df["Cost"] * 0.5)
                    valid_sq = None
                    for _ in range(1000):
                        sq = pd.concat([
                            p_df[p_df["Pos"] == "GKP"].sample(n=2, weights="weight"),
                            p_df[p_df["Pos"] == "DEF"].sample(n=5, weights="weight"),
                            p_df[p_df["Pos"] == "MID"].sample(n=5, weights="weight"),
                            p_df[p_df["Pos"] == "FWD"].sample(n=3, weights="weight"),
                        ])
                        if sq["Cost"].sum() <= 100.0 and sq["Team"].value_counts().max() <= 3:
                            valid_sq = sq
                            break
                    if valid_sq is not None:
                        st.session_state["sandbox_selected_ids"] = valid_sq["id"].tolist()
                        st.session_state["sandbox_ver"] = st.session_state.get("sandbox_ver", 0) + 1
                        st.rerun()
                    else:
                        st.warning("Could not generate valid random squad under £100m. Please try again.")

            with btn_col2:
                if st.button(":material/star:  Load Budget 15", use_container_width=True, key="sandbox_btn_budget"):
                    if "budget_dream_15_df" in st.session_state and st.session_state["budget_dream_15_df"] is not None:
                        b_ids = st.session_state["budget_dream_15_df"]["id"].tolist()
                        st.session_state["sandbox_selected_ids"] = b_ids
                        st.session_state["sandbox_ver"] = st.session_state.get("sandbox_ver", 0) + 1
                        st.rerun()
                    else:
                        with st.spinner("Generating Budget Dream 15..."):
                            d_xi, d_bench, _ = get_cached_league_dream_15(conn, current_gw, selected_gw, total_budget=100.0)
                            if not d_xi.empty:
                                b_ids = pd.concat([d_xi, d_bench], ignore_index=True)["id"].tolist()
                                st.session_state["sandbox_selected_ids"] = b_ids
                                st.session_state["sandbox_ver"] = st.session_state.get("sandbox_ver", 0) + 1
                                st.rerun()
                            else:
                                st.error("Could not solve Budget Dream 15.")

            if selected_ids:
                if st.button(":material/delete:  Clear All", use_container_width=True, key="sandbox_btn_clear"):
                    st.session_state["sandbox_selected_ids"] = []
                    st.session_state["sandbox_ver"] = st.session_state.get("sandbox_ver", 0) + 1
                    st.rerun()

            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            
            # Constraint Visual Display
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                p_color = "normal" if n_selected == 15 else ("inverse" if n_selected > 15 else "off")
                p_label = "Complete" if n_selected == 15 else (f"Need {15 - n_selected}" if n_selected < 15 else f"+{n_selected - 15} Over")
                st.metric("Players", f"{n_selected} / 15", delta=p_label, delta_color=p_color)
            with m_c2:
                b_color = "normal" if budget_remaining >= 0 else "inverse"
                st.metric("Total Budget", f"£{total_cost:.1f}m", delta=f"£{budget_remaining:+.1f}m ITB", delta_color=b_color)

            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            st.markdown("**Positions:**")
            p_c1, p_c2, p_c3, p_c4 = st.columns(4)
            p_c1.metric("GKP", f"{gk_cnt}/2", delta="OK" if gk_cnt == 2 else f"{gk_cnt - 2}", delta_color="normal" if gk_cnt == 2 else "inverse")
            p_c2.metric("DEF", f"{def_cnt}/5", delta="OK" if def_cnt == 5 else f"{def_cnt - 5}", delta_color="normal" if def_cnt == 5 else "inverse")
            p_c3.metric("MID", f"{mid_cnt}/5", delta="OK" if mid_cnt == 5 else f"{mid_cnt - 5}", delta_color="normal" if mid_cnt == 5 else "inverse")
            p_c4.metric("FWD", f"{fwd_cnt}/3", delta="OK" if fwd_cnt == 3 else f"{fwd_cnt - 3}", delta_color="normal" if fwd_cnt == 3 else "inverse")

            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            if teams_exceeded:
                st.error(f":material/error: **Team limit exceeded (>3)**: {', '.join([f'{t} ({team_counts[t]})' for t in teams_exceeded])}")
            else:
                st.caption(f":material/check_circle: Club Limits: Max {max_team}/3 per club")

        # 5. Validation
        violations = []
        if n_selected != 15:
            violations.append(f"Select exactly 15 players (currently {n_selected}).")
        if total_cost > 100.05:
            violations.append(f"Squad cost (£{total_cost:.1f}m) exceeds £100.0m budget.")
        if gk_cnt != 2:
            violations.append(f"Requires exactly 2 Goalkeepers (currently {gk_cnt}).")
        if def_cnt != 5:
            violations.append(f"Requires exactly 5 Defenders (currently {def_cnt}).")
        if mid_cnt != 5:
            violations.append(f"Requires exactly 5 Midfielders (currently {mid_cnt}).")
        if fwd_cnt != 3:
            violations.append(f"Requires exactly 3 Forwards (currently {fwd_cnt}).")
        if teams_exceeded:
            violations.append(f"Max 3 players per club exceeded: {', '.join([f'{t} ({team_counts[t]})' for t in teams_exceeded])}.")

        if violations:
            st.warning("⚠️ **Sandbox Squad Constraints Incomplete:**\n\n* " + "\n* ".join(violations))
            return

        squad_df = full_pool_df[full_pool_df["id"].isin(selected_ids)].copy()
        st.success(f":material/check_circle:  Valid 15-player custom squad ready (£{total_cost:.1f}m, {squad_df['Proj_Pts'].sum():.1f} total Proj xP).")
        
    if squad_df is None or len(squad_df) == 0:
        st.error("Squad is empty.")
        return
        
    # Ensure we have projected points for the squad to solve XI
    adv_fixtures_query = """
    SELECT
        f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
        th.short_name AS Home_Team, ta.short_name AS Away_Team,
        f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
    FROM fixtures f
    INNER JOIN teams th ON f.team_h = th.id
    INNER JOIN teams ta ON f.team_a = ta.id
    WHERE f.event = ?
    """
    fixtures_df = pd.read_sql_query(adv_fixtures_query, conn, params=[selected_gw])
    from data import get_teams_fdr_map, get_fixture_for_team, get_historical_player_baselines
    from simulation_engine import build_odds_map
    fdr_map = get_teams_fdr_map(conn, selected_gw)
    hist_df = get_historical_player_baselines(conn)
    teams_df = pd.read_sql_query("SELECT id, short_name FROM teams", conn)
    team_id_to_name = dict(zip(teams_df["id"], teams_df["short_name"]))
    team_name_to_id = dict(zip(teams_df["short_name"], teams_df["id"]))
    
    odds_map = build_odds_map(conn, selected_gw, fixtures_df, fdr_map)
    
    squad_evaluated = []
    is_saved_active = (squad_mode == ":material/person:  My Active Squad" and st.session_state.get("active_squad_sim_df") is not None)
    for _, p_row in squad_df.iterrows():
        p_dict = p_row.to_dict()
        team_val = p_dict.get("team_id", p_dict.get("team", p_dict.get("Team")))
        if isinstance(team_val, str) and not str(team_val).isdigit():
            team_val = team_name_to_id.get(team_val, 1)
        p_dict["team"] = int(team_val) if team_val is not None else 1
        
        et = p_dict.get("element_type", 3)
        if "Pos" in p_dict and isinstance(p_dict["Pos"], str):
            pass
        elif et == 1: p_dict["Pos"] = "GKP"
        elif et == 2: p_dict["Pos"] = "DEF"
        elif et == 4: p_dict["Pos"] = "FWD"
        else: p_dict["Pos"] = "MID"
        
        # For accurate solver xP, rely entirely on the pre-computed Proj_Pts if we loaded the Dream 15, saved optimal squad, or custom sandbox
        # Otherwise calculate natively using the odds_map injection to match the analyzer tab
        if (squad_mode in [":material/star:  Budget Dream 15", ":material/build:  Custom 15-Player Sandbox"] or is_saved_active) and "Proj_Pts" in p_dict and pd.notna(p_dict["Proj_Pts"]):
            pts = float(p_dict["Proj_Pts"])
        else:
            fix_info = get_fixture_for_team(fixtures_df, int(p_dict["team"]), selected_gw)
            team_odds = odds_map.get(int(p_dict["team"]), [])
            if team_odds:
                fix_info["team_xg"] = team_odds[0]["team_xg"]
                fix_info["opp_xg"] = team_odds[0]["opp_xg"]
                fix_info["cs_prob"] = team_odds[0]["cs_prob"]
            pts = calculate_projected_points(p_dict, fix_info, selected_gw, hist_df)
        
        squad_evaluated.append({
            "id": p_dict.get("id", p_dict.get("element_id")),
            "photo": p_dict.get("photo"),
            "code": p_dict.get("code"),
            "Player": p_dict.get("web_name", p_dict.get("Player")),
            "Club": team_id_to_name.get(p_dict["team"], str(p_dict["team"])),
            "Pos": p_dict["Pos"],
            "Proj_Pts": pts,
            "Cost": float(p_dict.get("now_cost", p_dict.get("Cost", 50.0))) / 10.0 if p_dict.get("now_cost") else p_dict.get("Cost", 5.0),
            "team": p_dict["team"],
            "minutes": p_dict.get("minutes", 0),
            "xGI_per_90": float(p_dict.get("expected_goal_involvements_per_90", p_dict.get("xGI_per_90", p_dict.get("roll_xgi90"))) or 0.0),
            "chance_of_playing_this_round": p_dict.get("chance_of_playing_this_round", p_dict.get("Chance", 100.0)),
        })
        
    squad_eval_df = pd.DataFrame(squad_evaluated)
    
    try:
        opt_xi, opt_bench, opt_formation = solve_optimal_xi(squad_eval_df)
    except Exception as e:
        st.error(f"Error solving optimal XI: {e}")
        opt_xi = squad_eval_df.head(11)
        opt_bench = squad_eval_df.tail(len(squad_eval_df)-11)
        
    col_ctrl, col_viz = st.columns([1, 2], gap="large")
    with col_ctrl:
        st.markdown(f"**Optimal Starting XI ({len(opt_xi)} players)**")
        is_dark = st.session_state.get("theme_mode", "dark") == "dark"
        from theme import render_sortable_table, SILHOUETTE_BASE64
        
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
        .cap-pill {{
            display: inline-block;
            margin-left: 6px;
            padding: 0.1rem 0.38rem;
            border-radius: 4px;
            font-size: 0.68rem;
            font-weight: 700;
            line-height: 1.2;
            vertical-align: middle;
        }}
        .cap-c {{
            background: rgba(234, 179, 8, 0.2);
            color: #facc15;
            border: 1px solid rgba(234, 179, 8, 0.45);
        }}
        .cap-vc {{
            background: rgba(148, 163, 184, 0.2);
            color: {"#cbd5e1" if is_dark else "#475569"};
            border: 1px solid {"rgba(148, 163, 184, 0.4)" if is_dark else "#cbd5e1"};
        }}
        </style>
        """
        
        html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
        html_out.append('<th style="text-align: left; padding-left: 1rem;">Player</th>')
        html_out.append('<th>Pos</th><th>Club</th><th>Proj xP</th></tr></thead><tbody>')
        for _, row in opt_xi.iterrows():
            photo_val = row.get("photo")
            if pd.notna(photo_val) and str(photo_val).strip() != "":
                photo_str = str(photo_val).replace(".jpg", ".png")
                p_img = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{photo_str}"
            else:
                p_img = SILHOUETTE_BASE64
                
            html_out.append("<tr>")
            html_out.append(f'<td style="text-align: left; padding-left: 1rem;">'
                            f'<div class="player-unified-cell">'
                            f'<img src="{p_img}" class="player-avatar-circle" onerror="this.src=\'{SILHOUETTE_BASE64}\'">'
                            f'<span class="player-name-text">{row["Player"]}</span>'
                            f'</div></td>')
            html_out.append(f'<td><span class="pos-pill pos-{row["Pos"]}">{row["Pos"]}</span></td>')
            html_out.append(f'<td>{row["Club"]}</td>')
            html_out.append(f'<td><span class="xp-pill">{float(row["Proj_Pts"]):.2f}</span></td>')
            html_out.append("</tr>")
        html_out.append("</tbody></table></div>")
        
        full_table_height = (len(opt_xi) * 45) + 60
        render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)
        
        captain_id = None
        vc_id = None
        if len(opt_xi) > 0:
            top_players = opt_xi.sort_values("Proj_Pts", ascending=False)
            captain_id = top_players.iloc[0]["id"]
            if len(top_players) > 1:
                vc_id = top_players.iloc[1]["id"]
                
        # Sim Controls
        st.markdown("#### Simulation Settings")
        n_sims = st.select_slider("Iterations:", options=[1000, 5000, 10000, 20000], value=10000)
        compare_rival = st.checkbox(":material/swords:  Compare Against Benchmark")
        compare_mode = None
        if compare_rival:
            compare_mode = "My Current Squad vs Transfer Plan"
            st.caption("Benchmark: My Active Squad vs Post-Transfer Plan")
            
        if st.button(":material/casino:  Run Monte Carlo Simulation", type="primary", width='stretch'):
            with st.spinner(f"Simulating {n_sims} scenarios..."):
                odds_map = build_odds_map(conn, selected_gw, fixtures_df, fdr_map)
                totals, p_dists, stats = run_gameweek_simulation(opt_xi, odds_map, n_sims, captain_id, vc_id)
                
                h2h_stats = None
                if compare_rival:
                    squad_b_eval_df = None
                    if compare_mode == "My Squad vs Dream 15":
                        query = "SELECT * FROM players WHERE status='a' AND chance_of_playing_this_round=100 ORDER BY selected_by_percent DESC LIMIT 15"
                        squad_b = pd.read_sql_query(query, conn)
                        squad_b_eval = []
                        for _, p_row in squad_b.iterrows():
                            p_dict = p_row.to_dict()
                            team_val = p_dict.get("team", p_dict.get("team_id", p_dict.get("Team")))
                            p_dict["team"] = team_val
                            
                            et = p_dict.get("element_type", 3)
                            if "Pos" in p_dict and isinstance(p_dict["Pos"], str):
                                pass
                            elif et == 1: p_dict["Pos"] = "GKP"
                            elif et == 2: p_dict["Pos"] = "DEF"
                            elif et == 4: p_dict["Pos"] = "FWD"
                            else: p_dict["Pos"] = "MID"
                            if compare_mode == "Budget Dream 15" and "Proj_Pts" in p_dict and pd.notna(p_dict["Proj_Pts"]):
                                pts = float(p_dict["Proj_Pts"])
                            else:
                                fix_info = get_fixture_for_team(fixtures_df, int(p_dict["team"]), selected_gw)
                                team_odds = odds_map.get(int(p_dict["team"]), [])
                                if team_odds:
                                    fix_info["team_xg"] = team_odds[0]["team_xg"]
                                    fix_info["opp_xg"] = team_odds[0]["opp_xg"]
                                    fix_info["cs_prob"] = team_odds[0]["cs_prob"]
                                pts = calculate_projected_points(p_dict, fix_info, selected_gw, hist_df)
                            squad_b_eval.append({"id": p_dict.get("id", p_dict.get("element_id")), "photo": p_dict.get("photo"), "code": p_dict.get("code"), "Player": p_dict.get("web_name", p_dict.get("Player")), "team": p_dict["team"], "Pos": p_dict["Pos"], "Proj_Pts": pts, "minutes": p_dict.get("minutes", 0), "xGI_per_90": float(p_dict.get("expected_goal_involvements_per_90", p_dict.get("xGI_per_90", p_dict.get("roll_xgi90"))) or 0.0), "chance_of_playing_this_round": p_dict.get("chance_of_playing_this_round", 100.0)})
                        squad_b_eval_df = pd.DataFrame(squad_b_eval)
                    elif compare_mode == "My Current Squad vs Transfer Plan":
                        transfer_result = st.session_state.get("transfer_result", {})
                        if "transferred_squad_df" in transfer_result:
                            squad_b = transfer_result["transferred_squad_df"]
                            squad_b_eval = []
                            for _, p_row in squad_b.iterrows():
                                p_dict = p_row.to_dict()
                                team_val = p_dict.get("team", p_dict.get("team_id", p_dict.get("Team")))
                                p_dict["team"] = team_val
                                
                                et = p_dict.get("element_type", 3)
                                if "Pos" in p_dict and isinstance(p_dict["Pos"], str):
                                    pass
                                elif et == 1: p_dict["Pos"] = "GKP"
                                elif et == 2: p_dict["Pos"] = "DEF"
                                elif et == 4: p_dict["Pos"] = "FWD"
                                else: p_dict["Pos"] = "MID"
                                fix_info = get_fixture_for_team(fixtures_df, int(p_dict["team"]), selected_gw)
                                team_odds = odds_map.get(int(p_dict["team"]), [])
                                if team_odds:
                                    fix_info["team_xg"] = team_odds[0]["team_xg"]
                                    fix_info["opp_xg"] = team_odds[0]["opp_xg"]
                                    fix_info["cs_prob"] = team_odds[0]["cs_prob"]
                                pts = calculate_projected_points(p_dict, fix_info, selected_gw, hist_df)
                                squad_b_eval.append({"id": p_dict.get("id", p_dict.get("element_id")), "photo": p_dict.get("photo"), "code": p_dict.get("code"), "Player": p_dict.get("web_name", p_dict.get("Player")), "team": p_dict["team"], "Pos": p_dict["Pos"], "Proj_Pts": pts, "minutes": p_dict.get("minutes", 0), "xGI_per_90": float(p_dict.get("expected_goal_involvements_per_90", p_dict.get("xGI_per_90", p_dict.get("roll_xgi90"))) or 0.0), "chance_of_playing_this_round": p_dict.get("chance_of_playing_this_round", 100.0)})
                            squad_b_eval_df = pd.DataFrame(squad_b_eval)
                            
                    if squad_b_eval_df is not None and not squad_b_eval_df.empty:
                        try:
                            opt_xi_b, _, _ = solve_optimal_xi(squad_b_eval_df)
                        except:
                            opt_xi_b = squad_b_eval_df.head(11)
                            
                        top_b = opt_xi_b.sort_values("Proj_Pts", ascending=False)
                        cap_b = top_b.iloc[0]["id"] if len(top_b) > 0 else None
                        vc_b = top_b.iloc[1]["id"] if len(top_b) > 1 else None
                        h2h_stats = run_head_to_head_simulation(opt_xi, opt_xi_b, odds_map, n_sims, captain_id, vc_id, cap_b, vc_b)

                st.session_state["sim_results"] = {
                    "totals": totals,
                    "stats": stats,
                    "gw": selected_gw,
                    "mode": squad_mode,
                    "h2h_stats": h2h_stats
                }
                
    with col_viz:
        sim_res = st.session_state.get("sim_results")
        if sim_res:
            stats = sim_res["stats"]
            
            st.markdown(f"### Simulation Results <span style='font-size:0.8rem; color:#94a3b8;'>(Executed in {stats['exec_time_ms']:.0f}ms)</span>", unsafe_allow_html=True)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Median Score", f"{stats['median']:.1f} pts")
            m2.metric("Safe Floor (p10)", f"{stats['p10_floor']:.1f} pts")
            m3.metric("Haul Ceiling (p90)", f"{stats['p90_ceiling']:.1f} pts")
            m4.metric("Volatility (±σ)", f"{stats['std_dev']:.1f}")
            
            # Draw Distribution Chart with Altair
            import altair as alt
            
            # Bucket the totals for the histogram
            totals = sim_res["totals"]
            df_hist = pd.DataFrame({"Points": totals})
            
            hist_chart = alt.Chart(df_hist).mark_bar(opacity=0.8, color="#3b82f6").encode(
                x=alt.X("Points:Q", bin=alt.Bin(maxbins=40), title="Total Points"),
                y=alt.Y("count()", title="Simulations"),
                tooltip=["count()"]
            ).properties(
                height=300
            )
            
            # Vertical lines for percentiles
            lines_data = pd.DataFrame({
                "x": [stats['p10_floor'], stats['median'], stats['p90_ceiling']],
                "label": ["10th Percentile", "Median", "90th Percentile"],
                "color": ["#ef4444", "#22c55e", "#eab308"]
            })
            
            rules = alt.Chart(lines_data).mark_rule(strokeWidth=2, strokeDash=[4, 4]).encode(
                x="x:Q",
                color=alt.Color("color:N", scale=None)
            )
            
            st.altair_chart((hist_chart + rules).interactive(), width='stretch')
            
            if sim_res.get("h2h_stats"):
                h2h = sim_res["h2h_stats"]
                st.markdown("#### Head-to-Head Comparison")
                st.info(f"**Primary Squad Win %**: {h2h['win_pct_a']:.1f}% &nbsp; | &nbsp; **Benchmark Win %**: {h2h['win_pct_b']:.1f}% &nbsp; | &nbsp; **Draw %**: {h2h['draw_pct']:.1f}%")
            
            st.markdown("#### Player Contribution Breakdown")
            df_player_stats = pd.DataFrame(stats["player_stats"])
            # Format
            df_player_stats["Median Pts"] = df_player_stats["median"].apply(lambda x: f"{x:.1f}")
            df_player_stats["Haul Prob"] = df_player_stats["haul_prob"].apply(lambda x: f"{x*100:.1f}%")
            df_player_stats["CS Prob"] = df_player_stats["cs_prob"].apply(lambda x: f"{x*100:.1f}%")
            
            def add_c(row):
                tag = ""
                if row["id"] == captain_id:
                    tag = ' <span class="cap-pill cap-c">(C)</span>'
                elif row["id"] == vc_id:
                    tag = ' <span class="cap-pill cap-vc">(VC)</span>'
                return f"{row['web_name']}{tag}"
                
            df_player_stats["Player"] = df_player_stats.apply(add_c, axis=1)
            
            # Merge photo back in
            if "id" in df_player_stats.columns and "id" in squad_eval_df.columns:
                df_player_stats = df_player_stats.merge(squad_eval_df[["id", "photo"]], on="id", how="left")
            
            html_out = [theme_styles, '<div class="unified-table-wrapper"><table class="unified-table"><thead><tr>']
            html_out.append('<th style="text-align: left; padding-left: 1rem;">Player</th>')
            html_out.append('<th>Pos</th><th>Team</th><th>Median Pts</th><th>Haul Prob</th><th>CS Prob</th></tr></thead><tbody>')
            for _, row in df_player_stats.iterrows():
                photo_val = row.get("photo")
                if pd.notna(photo_val) and str(photo_val).strip() != "":
                    photo_str = str(photo_val).replace(".jpg", ".png")
                    p_img = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{photo_str}"
                else:
                    p_img = SILHOUETTE_BASE64
                    
                html_out.append("<tr>")
                html_out.append(f'<td style="text-align: left; padding-left: 1rem;">'
                                f'<div class="player-unified-cell">'
                                f'<img src="{p_img}" class="player-avatar-circle" onerror="this.src=\'{SILHOUETTE_BASE64}\'">'
                                f'<span class="player-name-text">{row["Player"]}</span>'
                                f'</div></td>')
                html_out.append(f'<td><span class="pos-pill pos-{row["pos"]}">{row["pos"]}</span></td>')
                html_out.append(f'<td>{row["team"]}</td>')
                html_out.append(f'<td style="font-weight: 700;">{row["Median Pts"]}</td>')
                html_out.append(f'<td>{row["Haul Prob"]}</td>')
                html_out.append(f'<td>{row["CS Prob"]}</td>')
                html_out.append("</tr>")
            html_out.append("</tbody></table></div>")
            
            full_table_height = (len(df_player_stats) * 45) + 60
            render_sortable_table("".join(html_out), is_dark=is_dark, height=full_table_height)
        else:
            st.info("Configure your squad and run the simulation to see distributions.")
