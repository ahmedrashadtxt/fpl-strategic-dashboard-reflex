import asyncio
import reflex as rx
import pandas as pd
from typing import List, Dict, Any

from backend.data import get_connection, get_global_gameweek_info
from backend.squad_logic import (
    fetch_manager_entry, fetch_manager_history, fetch_manager_picks,
    fetch_live_gameweek_points, get_rolling_player_metrics, get_teams_fdr_map,
    build_player_tooltip, get_cached_league_dream_15, get_cached_league_super_15,
    find_best_chip_gw, build_pitch_html
)
from fpl_strategic_dashboard_reflex.state import AppState

class SquadAnalyzerState(AppState):
    is_loading: bool = False
    status_message: str = "Loading squad..."
    
    selected_eval_gw: str = "0"
    simulated_chip: str = "None"
    pitch_view: bool = True
    enable_comparison: bool = False
    squad_header_text: str = "Current Squad"
    comp_header_text: str = "Dream 15"
    super_team_mode: bool = False
    enable_betting: bool = True
    market_weight: float = 0.35
    factor_movement: bool = True
    
    mgr_name: str = "My Team"
    overall_rank: int = 0
    total_points: int = 0
    active_gw_pts: int = 0
    active_gw_label: str = "Active GW"
    squad_value: float = 0.0
    bank_balance: float = 0.0
    
    starters: List[Dict[str, Any]] = []
    bench: List[Dict[str, Any]] = []
    compare_starters: List[Dict[str, Any]] = []
    compare_bench: List[Dict[str, Any]] = []
    gw_options: List[str] = []
    used_chips_keys: List[str] = []
    
    base_pitch_html: str = ""
    comp_pitch_html: str = ""
    
    @rx.var
    def has_data(self) -> bool:
        return len(self.starters) > 0
        
    def toggle_chip(self, chip: str):
        if self.simulated_chip == chip:
            self.simulated_chip = "None"
        else:
            self.simulated_chip = chip
        return SquadAnalyzerState.load_squad
        
    def set_simulated_chip(self, val: str):
        self.simulated_chip = val
        return SquadAnalyzerState.load_squad
    def set_eval_gw(self, gw: str):
        self.selected_eval_gw = str(gw)
        return SquadAnalyzerState.load_squad
        
    def set_pitch_view(self, val: bool):
        self.pitch_view = val
    def set_enable_comparison(self, val: bool):
        self.enable_comparison = val
        return SquadAnalyzerState.load_squad
    def set_super_team_mode(self, val: bool):
        self.super_team_mode = val
        return SquadAnalyzerState.load_squad
    def set_enable_betting(self, val: bool):
        self.enable_betting = val
        return SquadAnalyzerState.load_squad
    def set_market_weight(self, val: list[int]):
        self.market_weight = val[0] / 100.0
        return SquadAnalyzerState.load_squad
    def set_factor_movement(self, val: bool):
        self.factor_movement = val
        return SquadAnalyzerState.load_squad
        
    @rx.event(background=True)
    async def load_squad(self):
        async with self:
            if not self.manager_id:
                return
            self.is_loading = True
            self.status_message = "Syncing Live Match Center..."
            
        # Offload logic
        
        async with self:
            manager_id = self.manager_id
            current_gw = self.current_gw
            sel_gw = self.selected_eval_gw
            chip = self.simulated_chip
            comp = self.enable_comparison
            super_t = self.super_team_mode
            betting = self.enable_betting
            weight = self.market_weight
            movement = self.factor_movement
            
        result = await asyncio.to_thread(
            _run_squad_analysis, 
            manager_id, current_gw, sel_gw, chip, comp, super_t, betting, weight, movement
        )
        
        async with self:
            if result:
                self.mgr_name = result.get('mgr_name', '')
                self.overall_rank = result.get('overall_rank', 0)
                self.total_points = result.get('total_points', 0)
                self.active_gw_pts = result.get('active_gw_pts', 0)
                self.active_gw_label = result.get('active_gw_label', 'Active GW')
                self.squad_value = result.get('squad_value', 0.0)
                self.bank_balance = result.get('bank_balance', 0.0)
                self.starters = result.get('starters', [])
                self.bench = result.get('bench', [])
                self.compare_starters = result.get('compare_starters', [])
                self.compare_bench = result.get('compare_bench', [])
                self.gw_options = result.get('gw_options', [])
                self.used_chips_keys = result.get('used_chips_keys', [])
                self.base_pitch_html = result.get('base_pitch_html', '')
                self.comp_pitch_html = result.get('comp_pitch_html', '')
                
                if str(self.selected_eval_gw) not in self.gw_options and self.gw_options:
                    self.selected_eval_gw = str(result.get('default_gw', self.gw_options[0]))
                self.squad_header_text = result.get('squad_header_text', 'Current Squad')
                self.comp_header_text = result.get('comp_header_text', 'Dream 15')
            self.is_loading = False
            
def _run_squad_analysis(manager_id, current_gw, selected_eval_gw, chip, comp, super_t, betting, weight, movement):
    try:
        selected_eval_gw = int(selected_eval_gw)
        conn = get_connection()
        events_df, next_gw_id, _ = get_global_gameweek_info(conn)
        
        mgr_data = fetch_manager_entry(manager_id)
        if not mgr_data:
            return None
            
        rolling_metrics_df = get_rolling_player_metrics(conn)
        teams_fdr_map = get_teams_fdr_map(conn, current_gw)
        mgr_history = fetch_manager_history(manager_id)
        
        finished_gw_ids = [int(r["id"]) for _, r in events_df[events_df["finished"] == 1].iterrows()] if "finished" in events_df.columns else []
        ongoing_gw_ids = [int(r["id"]) for _, r in events_df.iterrows() if int(r["id"]) not in finished_gw_ids and int(r["id"]) < next_gw_id]
        ongoing_gw = ongoing_gw_ids[0] if ongoing_gw_ids else None
        last_finished_gw = max(finished_gw_ids) if finished_gw_ids else None
        
        active_calc_gw = ongoing_gw if ongoing_gw else (last_finished_gw or next_gw_id)
        
        picks_data = fetch_manager_picks(manager_id, active_calc_gw, next_gw_id)
        entry_history = picks_data.get("entry_history", {})
        transfers_cost = entry_history.get("event_transfers_cost", 0)
        bank_balance = entry_history.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
        
        picks_list = picks_data.get("picks", [])
        pick_ids = [p["element"] for p in picks_list]
        
        if not pick_ids:
            return None
            
        placeholders = ",".join(["?"] * len(pick_ids))
        squad_query = f"""
        SELECT
            p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
            t.short_name AS Team,
            CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
            pos.singular_name AS Position, p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
            p.total_points AS Season_Points, p.expected_goals, p.expected_assists,
            p.form AS Form, p.points_per_game AS PPG, p.expected_goal_involvements_per_90 AS xGI_per_90,
            p.news AS News, p.status AS Status, p.chance_of_playing_next_round AS Chance
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        INNER JOIN positions pos ON p.element_type = pos.id
        WHERE p.id IN ({placeholders})
        """
        squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
        
        meta_dict = {p["element"]: {"multiplier": p["multiplier"], "is_captain": p["is_captain"], "is_vice": p["is_vice_captain"], "order": p["position"]} for p in picks_list}
        squad_df["order"] = squad_df["id"].map(lambda x: meta_dict[x]["order"])
        squad_df["Multiplier"] = squad_df["id"].map(lambda x: meta_dict[x]["multiplier"])
        squad_df["is_cap"] = squad_df["id"].map(lambda x: meta_dict[x]["is_captain"])
        squad_df["is_vc"] = squad_df["id"].map(lambda x: meta_dict[x]["is_vice"])
        
        live_points_map = fetch_live_gameweek_points(active_calc_gw)
        squad_df["Raw_GW_Pts"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}).get("points", 0) if isinstance(live_points_map.get(x), dict) else live_points_map.get(x, 0))
        squad_df["GW_Points"] = squad_df["Raw_GW_Pts"] * squad_df["Multiplier"]
        squad_df["live_stats"] = squad_df["id"].map(lambda x: live_points_map.get(x, {}) if isinstance(live_points_map.get(x), dict) else {})
        
        # Determine options for gws
        target_chip_gw = None
        if chip != "None":
            target_chip_gw = find_best_chip_gw(chip, squad_df, conn, next_gw_id)
            
        standard_upcoming = [g for g in range(next_gw_id, min(20, next_gw_id + 3))]
        upcoming_gws = list(standard_upcoming)
        if target_chip_gw and target_chip_gw not in standard_upcoming:
            upcoming_gws.append(target_chip_gw)
        else:
            fourth_gw = next_gw_id + 3
            if fourth_gw <= 19:
                upcoming_gws.append(fourth_gw)
                
        all_gw_options = []
        if last_finished_gw is not None: all_gw_options.append(last_finished_gw)
        if ongoing_gw is not None: all_gw_options.append(ongoing_gw)
        all_gw_options.extend(upcoming_gws)
        all_gw_options = sorted(list(dict.fromkeys(all_gw_options)))
        
        default_gw = target_chip_gw if (target_chip_gw and target_chip_gw in all_gw_options) else (ongoing_gw if ongoing_gw else next_gw_id)
        if selected_eval_gw not in all_gw_options:
            selected_eval_gw = default_gw
            
        # Add rolling logic and fdr
        if not squad_df.empty:
            if not rolling_metrics_df.empty:
                squad_df["roll_pts"] = squad_df["id"].map(rolling_metrics_df["roll_pts"]).fillna(0.0)
                squad_df["roll_xgi90"] = squad_df["id"].map(rolling_metrics_df["roll_xgi90"]).fillna(0.0)
                squad_df["roll_mins"] = squad_df["id"].map(rolling_metrics_df["roll_mins"]).fillna(0).astype(int)
            else:
                squad_df["roll_pts"] = 0.0
                squad_df["roll_xgi90"] = 0.0
                squad_df["roll_mins"] = 0
            if teams_fdr_map:
                squad_df["fdr5"] = squad_df["team_id"].map(teams_fdr_map).fillna(15).astype(int)
            else:
                squad_df["fdr5"] = 15
                
        # Re-fetch points if eval gw is different from active
        if selected_eval_gw != active_calc_gw and (selected_eval_gw in finished_gw_ids or selected_eval_gw == ongoing_gw):
            eval_live_map = fetch_live_gameweek_points(selected_eval_gw)
            squad_df["Raw_GW_Pts"] = squad_df["id"].map(lambda x: eval_live_map.get(x, {}).get("points", 0) if isinstance(eval_live_map.get(x), dict) else eval_live_map.get(x, 0))
            squad_df["live_stats"] = squad_df["id"].map(lambda x: eval_live_map.get(x, {}) if isinstance(eval_live_map.get(x), dict) else {})
            
        squad_df["tooltip_html"] = squad_df.apply(lambda r: build_player_tooltip(r, is_live=(selected_eval_gw in finished_gw_ids or selected_eval_gw == ongoing_gw)), axis=1)
        
        # Sort into starters and bench
        starters_df = squad_df[squad_df["order"] <= 11].sort_values("order")
        bench_df = squad_df[squad_df["order"] > 11].sort_values("order")
        
        # Comparison logic
        comp_starters = []
        comp_bench = []
        if comp:
            total_val = float(squad_df["Cost"].sum()) + bank_balance
            if super_t:
                comp_xi, comp_sub, _ = get_cached_league_super_15(conn, current_gw, selected_eval_gw, betting, weight, movement)
            else:
                comp_xi, comp_sub, _ = get_cached_league_dream_15(conn, current_gw, selected_eval_gw, total_val, betting, weight, movement)
                
            if not comp_xi.empty:
                comp_xi["is_cap"] = (comp_xi["id"] == comp_xi.iloc[0]["id"])
                comp_xi["is_vc"] = (comp_xi["id"] == comp_xi.iloc[1]["id"]) if len(comp_xi) > 1 else False
                comp_xi["Multiplier"] = comp_xi["is_cap"].map(lambda x: 2 if x else 1)
                comp_xi["tooltip_html"] = comp_xi.apply(lambda r: build_player_tooltip(r, is_live=False), axis=1)
                comp_starters = comp_xi.fillna("").to_dict("records")
            if not comp_sub.empty:
                comp_sub["tooltip_html"] = comp_sub.apply(lambda r: build_player_tooltip(r, is_live=False), axis=1)
                comp_bench = comp_sub.fillna("").to_dict("records")
        
        used_chips_keys = [c["name"] for c in mgr_history.get("chips", [])]
        
        is_live = (selected_eval_gw in finished_gw_ids or selected_eval_gw == ongoing_gw)
        base_pitch_html = build_pitch_html(starters_df, bench_df, is_live=is_live)
        comp_pitch_html = ""
        if comp and not comp_xi.empty:
            comp_pitch_html = build_pitch_html(comp_xi, comp_sub, is_live=False)
        

        squad_pts = int(starters_df["GW_Points"].sum() - transfers_cost) if not starters_df.empty else 0
        squad_xp = float(starters_df["Proj_Pts"].sum()) if not starters_df.empty else 0.0
        squad_header = f"Your Squad - GW{selected_eval_gw} ({squad_pts} pts)" if is_live else f"Your Squad - GW{selected_eval_gw} ({squad_xp:.1f} xP)"
        
        comp_header = ""
        if comp and not comp_xi.empty:
            comp_xp = float(comp_xi["Proj_Pts"].sum())
            comp_header = f"Super Team - GW{selected_eval_gw} ({comp_xp:.1f} xP)" if super_t else f"Dream 15 - GW{selected_eval_gw} ({comp_xp:.1f} xP)"

        return {
            'squad_header_text': squad_header,
            'comp_header_text': comp_header,
            'gw_options': [str(gw) for gw in all_gw_options],
            'mgr_name': mgr_data.get("name", "My Team"),
            'overall_rank': int(mgr_data.get("summary_overall_rank", 0)),
            'total_points': int(mgr_data.get("summary_overall_points", 0)),
            'active_gw_pts': int(starters_df["GW_Points"].sum() - transfers_cost) if not starters_df.empty else 0,
            'active_gw_label': f"GW{ongoing_gw} Live" if ongoing_gw else f"GW{last_finished_gw} Pts",
            'squad_value': float(squad_df["Cost"].sum()) if not squad_df.empty else 100.0,
            'bank_balance': bank_balance,
            'starters': starters_df.fillna("").to_dict("records"),
            'bench': bench_df.fillna("").to_dict("records"),
            'compare_starters': comp_starters,
            'compare_bench': comp_bench,
            
            'default_gw': default_gw,
            'used_chips_keys': used_chips_keys,
            'base_pitch_html': base_pitch_html,
            'comp_pitch_html': comp_pitch_html
        }
    except Exception as e:
        print(f"Squad analyzer backend error: {e}")
        return None

def squad_list_view(starters: list, bench: list):
    return rx.vstack(
        rx.foreach(
            starters,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="10px",
                border="1px solid rgba(255,255,255,0.1)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.6)",
                margin_bottom="2px"
            )
        ),
        rx.text("Bench", font_weight="bold", margin_top="4"),
        rx.foreach(
            bench,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="10px",
                border="1px solid rgba(255,255,255,0.1)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.4)",
                margin_bottom="2px"
            )
        ),
        width="100%",
        spacing="2"
    )

def squad_analyzer_page():
    return rx.box(
        rx.cond(
            SquadAnalyzerState.is_loading,
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.icon("activity", size=40, color="var(--accent-9)"),
                        rx.heading("Analyzing Squad...", size="4"),
                        rx.text(SquadAnalyzerState.status_message, color="gray", size="2"),
                        rx.progress(value=None, width="100%", color_scheme="blue"),
                        align_items="center",
                        spacing="4"
                    ),
                    padding="6",
                    width="350px",
                    box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
                ),
                padding="12",
                width="100%",
                min_height="300px"
            )
        ),
        rx.cond(
            (SquadAnalyzerState.manager_id == ""),
            rx.center(
                rx.callout(
                    "👆 Click 'Enter FPL ID' in the top-right header to load your squad analysis.",
                    icon="info",
                ),
                padding="8"
            )
        ),
        rx.cond(
            (SquadAnalyzerState.manager_id != "") & ~SquadAnalyzerState.is_loading & SquadAnalyzerState.has_data,
            rx.vstack(
                # Metrics Row
                rx.grid(
                    rx.box(rx.text("Manager", size="1", color="gray"), rx.text(SquadAnalyzerState.mgr_name, weight="bold")),
                    rx.box(rx.text("Overall Rank", size="1", color="gray"), rx.text(SquadAnalyzerState.overall_rank, weight="bold")),
                    rx.box(rx.text("Total Points", size="1", color="gray"), rx.text(SquadAnalyzerState.total_points, weight="bold")),
                    rx.box(rx.text(SquadAnalyzerState.active_gw_label, size="1", color="gray"), rx.text(SquadAnalyzerState.active_gw_pts, weight="bold")),
                    rx.box(rx.text("Squad Value", size="1", color="gray"), rx.text(SquadAnalyzerState.squad_value, weight="bold")),
                    rx.box(rx.text("In The Bank", size="1", color="gray"), rx.text(SquadAnalyzerState.bank_balance, weight="bold")),
                    columns="6",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Chips Row
                rx.vstack(
                    rx.text("HALF 1 CHIPS (GW1-19)", size="1", color="gray", weight="bold"),
                    rx.radio(
                        items=["None", "Wildcard", "Free Hit", "Bench Boost", "Triple Captain"],
                        value=SquadAnalyzerState.simulated_chip,
                        on_change=SquadAnalyzerState.set_simulated_chip,
                        direction="row",
                        spacing="4"
                    ),
                    spacing="1",
                    margin_bottom="4"
                ),
                # Controls
                rx.vstack(
                    rx.hstack(
                        rx.icon("calendar"),
                        rx.text("Select Gameweek:", weight="bold"),
                        align_items="center"
                    ),
                    rx.radio(
                        items=SquadAnalyzerState.gw_options,
                        value=SquadAnalyzerState.selected_eval_gw,
                        on_change=SquadAnalyzerState.set_eval_gw,
                        direction="row",
                        spacing="4"
                    ),
                    spacing="2",
                    margin_bottom="4"
                ),
                rx.hstack(
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.pitch_view, on_change=SquadAnalyzerState.set_pitch_view),
                        rx.text("Pitch View"),
                        align_items="center"
                    ),
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.enable_comparison, on_change=SquadAnalyzerState.set_enable_comparison),
                        rx.text("Comparison"),
                        align_items="center"
                    ),
                    rx.cond(
                        SquadAnalyzerState.enable_comparison,
                        rx.hstack(
                            rx.switch(checked=SquadAnalyzerState.super_team_mode, on_change=SquadAnalyzerState.set_super_team_mode),
                            rx.text("Super Team"),
                            align_items="center"
                        ),
                        rx.box()
                    ),
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.enable_betting, on_change=SquadAnalyzerState.set_enable_betting),
                        rx.text("Betting Market xG"),
                        align_items="center"
                    ),
                    spacing="6",
                    width="100%",
                    align_items="center",
                    margin_bottom="4"
                ),
                # Market Weight Slider
                rx.cond(
                    SquadAnalyzerState.enable_betting,
                    rx.vstack(
                        rx.text("Market Implied Weight: " + SquadAnalyzerState.market_weight.to_string(), size="2"),
                        rx.slider(
                            default_value=[35],
                            min=0,
                            max=100,
                            on_value_commit=SquadAnalyzerState.set_market_weight,
                            width="100%"
                        ),
                        rx.hstack(
                            rx.switch(checked=SquadAnalyzerState.factor_movement, on_change=SquadAnalyzerState.set_factor_movement),
                            rx.text("Line Movement"),
                            align_items="center"
                        ),
                        spacing="2",
                        width="300px",
                        margin_bottom="4"
                    ),
                    rx.box()
                ),
                
                # Views
                rx.cond(
                    SquadAnalyzerState.enable_comparison,
                    rx.grid(
                        rx.box(
                            rx.text("Current Squad", weight="bold", margin_bottom="2"),
                            rx.cond(
                                SquadAnalyzerState.pitch_view,
                                rx.html(SquadAnalyzerState.base_pitch_html),
                                squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench)
                            ),
                            width="100%"
                        ),
                        rx.box(
                            rx.text(rx.cond(SquadAnalyzerState.super_team_mode, "Super Team", "Dream 15"), weight="bold", margin_bottom="2"),
                            rx.cond(
                                SquadAnalyzerState.pitch_view,
                                rx.html(SquadAnalyzerState.comp_pitch_html),
                                squad_list_view(SquadAnalyzerState.compare_starters, SquadAnalyzerState.compare_bench)
                            ),
                            width="100%"
                        ),
                        columns="2",
                        spacing="4",
                        width="100%"
                    ),
                    rx.box(
                        rx.text("Current Squad", weight="bold", margin_bottom="2"),
                        rx.cond(
                            SquadAnalyzerState.pitch_view,
                            rx.html(SquadAnalyzerState.base_pitch_html),
                            squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench)
                        ),
                        width="100%"
                    )
                ),
                width="100%",
                spacing="4"
            )
        ),
        width="100%",
        on_mount=SquadAnalyzerState.load_squad
    )
