import asyncio
import reflex as rx
import pandas as pd
from typing import List, Dict, Any

from backend.data import get_connection, get_global_gameweek_info, solve_optimal_xi
from backend.transfer_logic import (
    fetch_transfer_manager_entry as fetch_manager_entry, fetch_transfer_manager_history as fetch_manager_history, fetch_transfer_manager_picks as fetch_manager_picks,
    calculate_available_fts, get_rolling_player_metrics, get_teams_fdr_map,
    evaluate_league_multi_gw, solve_multi_gw_transfers, build_player_tooltip,
    prepare_xi_display, render_transfer_pitch_component
)
from fpl_strategic_dashboard_reflex.state import AppState

class TransferAnalyzerState(AppState):
    is_loading: bool = False
    status_message: str = "Loading market..."
    
    horizon_len: str = "1"
    ft_count: str = "1"
    max_hits: str = "0"
    pitch_view: bool = True
    enable_betting: bool = True
    market_weight: float = 0.35
    min_mins: int = 45
    
    pos_options: List[str] = []
    neg_options: List[str] = []
    # Using parallel arrays or a dictionary mapping for labels isn't supported directly in rx.select/multiselect easily if we want custom labels.
    # We will use "ID: Player Name" format for options directly.
    
    selected_positive: List[str] = []
    selected_negative: List[str] = []
    
    bank_balance: float = 0.0
    swaps: List[Dict[str, str]] = []
    
    base_starters: List[Dict[str, Any]] = []
    base_bench: List[Dict[str, Any]] = []
    trans_starters: List[Dict[str, Any]] = []
    trans_bench: List[Dict[str, Any]] = []
    
    base_pitch_html: str = ""
    comp_pitch_html: str = ""
    
    metrics: Dict[str, Any] = {
        "bank_after": 0.0,
        "team_value": 0.0,
        "old_xp": 0.0,
        "new_xp": 0.0,
        "xp_diff": 0.0
    }
    
    ledger_data: List[Dict[str, Any]] = []

    @rx.var
    def ledger_columns(self) -> list[str]:
        return ["Role", "Player", "Team", "Pos", "Cost", "Horizon_xP", "Avg_xP"]

    @rx.var
    def has_data(self) -> bool:
        return len(self.base_starters) > 0
        
    @rx.var
    def total_allowed_transfers(self) -> int:
        return int(self.ft_count) + int(self.max_hits)
        
    def set_horizon(self, val: str):
        self.horizon_len = int(val)
        return TransferAnalyzerState.analyze
    def set_fts(self, val: str):
        self.ft_count = int(val)
        return TransferAnalyzerState.analyze
    def set_max_hits(self, val: str):
        self.max_hits = int(val)
        return TransferAnalyzerState.analyze
    def set_pitch_view(self, val: bool):
        self.pitch_view = val
    def set_enable_betting(self, val: bool):
        self.enable_betting = val
        return TransferAnalyzerState.analyze
    def set_market_weight(self, val: list[int]):
        self.market_weight = val[0] / 100.0
        return TransferAnalyzerState.analyze
    def set_min_mins(self, val: list[int]):
        self.min_mins = val[0]
        return TransferAnalyzerState.analyze
        
    def set_selected_positive(self, val: List[str]):
        self.selected_positive = val
        return TransferAnalyzerState.analyze
    def set_selected_negative(self, val: List[str]):
        self.selected_negative = val
        return TransferAnalyzerState.analyze
        
    @rx.event(background=True)
    async def analyze(self):
        async with self:
            if not self.manager_id:
                return
            self.is_loading = True
            self.status_message = "Solving optimal transfer path..."
        
        async with self:
            manager_id = self.manager_id
            current_gw = self.current_gw
            horizon = int(self.horizon_len)
            ft = int(self.ft_count)
            hits = int(self.max_hits)
            betting = self.enable_betting
            weight = self.market_weight
            mins = self.min_mins
            pos_sel = self.selected_positive
            neg_sel = self.selected_negative
            
        result = await asyncio.to_thread(
            _run_transfer_analysis, 
            manager_id, current_gw, horizon, ft, hits, betting, weight, mins, pos_sel, neg_sel
        )
        
        async with self:
            if result:
                self.pos_options = result['pos_options']
                self.neg_options = result['neg_options']
                self.bank_balance = result['bank_balance']
                self.swaps = result['swaps']
                self.base_starters = result['base_starters']
                self.base_bench = result['base_bench']
                self.trans_starters = result['trans_starters']
                self.trans_bench = result['trans_bench']
                self.base_pitch_html = result['base_pitch_html']
                self.comp_pitch_html = result['comp_pitch_html']
                self.metrics = result['metrics']
                self.ledger_data = result.get('ledger_data', [])
                # Reset free transfers on first load if default is set
                if result.get("init_ft"):
                    self.ft_count = str(result["init_ft"])
            self.is_loading = False
            
def _run_transfer_analysis(manager_id, current_gw, horizon, ft, hits, betting, weight, mins, pos_sel, neg_sel):
    try:
        conn = get_connection()
        events_df, next_gw, _ = get_global_gameweek_info(conn)
        
        mgr_data = fetch_manager_entry(manager_id)
        if not mgr_data: return None
        mgr_history = fetch_manager_history(manager_id)
        
        # Calculate initial FTs if not already overridden by UI
        calc_ft = calculate_available_fts(mgr_history)
        
        # Determine picks
        finished_gw_ids = [int(r["id"]) for _, r in events_df[events_df["finished"] == 1].iterrows()] if "finished" in events_df.columns else []
        ongoing_gw_ids = [int(r["id"]) for _, r in events_df.iterrows() if int(r["id"]) not in finished_gw_ids and int(r["id"]) < next_gw]
        ongoing_gw = ongoing_gw_ids[0] if ongoing_gw_ids else None
        last_finished_gw = max(finished_gw_ids) if finished_gw_ids else None
        
        active_calc_gw = ongoing_gw if ongoing_gw else (last_finished_gw or next_gw)
        picks_data = fetch_manager_picks(manager_id, active_calc_gw)
        
        entry_history = picks_data.get("entry_history", {})
        bank_balance = entry_history.get("bank", mgr_data.get("last_deadline_bank", 0)) / 10.0
        picks_list = picks_data.get("picks", [])
        pick_ids = [p["element"] for p in picks_list]
        
        if not pick_ids: return None
        
        placeholders = ",".join(["?"] * len(pick_ids))
        squad_query = f"""
        SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
               t.short_name AS Team,
               CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
               p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
               p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
               p.status AS Status, p.chance_of_playing_next_round AS Chance, p.news AS News
        FROM players p
        INNER JOIN teams t ON p.team = t.id
        WHERE p.id IN ({placeholders})
        """
        squad_df = pd.read_sql(squad_query, conn, params=pick_ids)
        
        league_eval_df = evaluate_league_multi_gw(
            conn, next_gw, horizon,
            enable_betting=betting, market_weight=weight, factor_movement=True
        )
        
        available_market_df = league_eval_df[
            (~league_eval_df["id"].isin(pick_ids)) &
            (league_eval_df["avg_mins"] >= mins)
        ].sort_values(by="Horizon_xP", ascending=False)
        
        # Build Options
        pos_options = []
        for _, r in squad_df.iterrows():
            pos_options.append(f"lock_{r['id']}::🔒 Keep: {r['Player']} ({r['Team']} · {r['Pos']})")
        for _, r in available_market_df.iterrows():
            pos_options.append(f"target_{r['id']}::🎯 Target: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m · {r['Horizon_xP']:.1f} xP)")
            
        neg_options = []
        for _, r in squad_df.iterrows():
            neg_options.append(f"sell_{r['id']}::🔴 Sell: {r['Player']} ({r['Team']} · {r['Pos']})")
        for _, r in available_market_df.iterrows():
            neg_options.append(f"block_{r['id']}::⛔ Block: {r['Player']} ({r['Team']} · {r['Pos']} · £{r['Cost']:.1f}m)")
            
        # Parse selected
        locked_players = [int(k.split("::")[0].replace("lock_", "")) for k in pos_sel if k.startswith("lock_")]
        targeted_in_players = [int(k.split("::")[0].replace("target_", "")) for k in pos_sel if k.startswith("target_")]
        force_out_players = [int(k.split("::")[0].replace("sell_", "")) for k in neg_sel if k.startswith("sell_")]
        blocked_in_players = [int(k.split("::")[0].replace("block_", "")) for k in neg_sel if k.startswith("block_")]
        
        total_allowed_transfers = int(ft + hits)
        curr_squad_horizon = league_eval_df[league_eval_df["id"].isin(pick_ids)].copy()
        
        transferred_squad_df, swaps = solve_multi_gw_transfers(
            current_squad_df=curr_squad_horizon,
            candidate_league_df=league_eval_df,
            bank=bank_balance,
            num_transfers=total_allowed_transfers,
            locked_player_ids=locked_players,
            target_in_player_ids=targeted_in_players,
            force_out_player_ids=force_out_players,
            blocked_in_player_ids=blocked_in_players,
            min_avg_minutes=mins,
        )
        
        out_ids = {s["out"]["id"] for s in swaps}
        in_ids = {s["in"]["id"] for s in swaps}
        forced_out_ids = {s["out"]["id"] for s in swaps if s.get("forced_out")}

        curr_squad_horizon["is_transfer_out"] = curr_squad_horizon["id"].isin(out_ids)
        curr_squad_horizon["is_forced_out"] = curr_squad_horizon["id"].isin(forced_out_ids)
        curr_squad_horizon["is_transfer_in"] = False
        curr_squad_horizon["is_target_in"] = False

        transferred_squad_df["is_transfer_out"] = False
        transferred_squad_df["is_forced_out"] = False
        transferred_squad_df["is_transfer_in"] = transferred_squad_df["id"].isin(in_ids)
        transferred_squad_df["is_target_in"] = transferred_squad_df["id"].isin(targeted_in_players)

        raw_base_xi, raw_base_bench, _ = solve_optimal_xi(curr_squad_horizon)
        raw_trans_xi, raw_trans_bench, _ = solve_optimal_xi(transferred_squad_df)

        base_xi, base_bench = prepare_xi_display(raw_base_xi, raw_base_bench)
        trans_xi, trans_bench = prepare_xi_display(raw_trans_xi, raw_trans_bench)
        
        base_xi["tooltip_html"] = base_xi.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        base_bench["tooltip_html"] = base_bench.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        trans_xi["tooltip_html"] = trans_xi.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        trans_bench["tooltip_html"] = trans_bench.apply(lambda r: build_player_tooltip(r, horizon_len=horizon), axis=1)
        
        base_pitch_html = render_transfer_pitch_component(base_xi, base_bench)
        comp_pitch_html = render_transfer_pitch_component(trans_xi, trans_bench)
        
        base_xp = float(base_xi["Proj_Pts"].sum())
        trans_xp = float(trans_xi["Proj_Pts"].sum())
        
        safe_swaps = []
        for s in swaps:
            safe_swaps.append({
                "out_name": str(s["out"]["Player"]),
                "in_name": str(s["in"]["Player"]),
                "out_team": str(s["out"].get("Team", "")),
                "in_team": str(s["in"].get("Team", "")),
                "gain": float(s.get("gain", 0.0)),
                "cost_diff": float(s.get("cost_diff", 0.0)),
                "forced_out": bool(s.get("forced_out", False)),
                "target": bool(s.get("target", False))
            })
            
        ledger_df = transferred_squad_df.copy()
        if not ledger_df.empty:
            ledger_df["Role"] = ledger_df["id"].map(
                lambda x: (
                    "Target Signing 🎯" if x in in_ids and x in targeted_in_players
                    else ("New Signing 🟢" if x in in_ids else ("Locked 🔒" if x in locked_players else "Retained"))
                )
            )
            cols = ["Role", "Player", "Team", "Pos", "Cost", "Horizon_xP", "Avg_xP"]
            cols = [c for c in cols if c in ledger_df.columns]
            ledger_data = ledger_df[cols].sort_values(by="Horizon_xP", ascending=False).fillna("").to_dict("records")
        else:
            ledger_data = []

        return {
            'ledger_data': ledger_data,
            'pos_options': pos_options,
            'neg_options': neg_options,
            'bank_balance': bank_balance,
            'swaps': safe_swaps,
            'base_starters': base_xi.fillna("").to_dict("records"),
            'base_bench': base_bench.fillna("").to_dict("records"),
            'trans_starters': trans_xi.fillna("").to_dict("records"),
            'trans_bench': trans_bench.fillna("").to_dict("records"),
            'base_pitch_html': base_pitch_html,
            'comp_pitch_html': comp_pitch_html,
            'init_ft': calc_ft if ft == 1 else None,  # only pass calc_ft if default 1 was not customized
            'metrics': {
                'bank_after': bank_balance + sum(float(s["out"]["Cost"]) for s in swaps) - sum(float(s["in"]["Cost"]) for s in swaps),
                'team_value': float(curr_squad_horizon["Cost"].sum()),
                'old_xp': base_xp,
                'new_xp': trans_xp,
                'xp_diff': trans_xp - base_xp
            }
        }
    except Exception as e:
        print(f"Transfer analyzer backend error: {e}")
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

def transfer_analyzer_page():
    return rx.box(
        rx.cond(
            TransferAnalyzerState.is_loading,
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.icon("bot", size=40, color="var(--accent-9)"),
                        rx.heading("Synthesizing Path...", size="4"),
                        rx.text(TransferAnalyzerState.status_message, color="gray", size="2"),
                        rx.progress(value=None, width="100%", color_scheme="green"),
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
            (TransferAnalyzerState.manager_id == ""),
            rx.center(
                rx.callout(
                    "👆 Click 'Enter FPL ID' in the top-right header to load your transfer analysis.",
                    icon="info",
                ),
                padding="8"
            )
        ),
        rx.cond(
            (TransferAnalyzerState.manager_id != "") & ~TransferAnalyzerState.is_loading & TransferAnalyzerState.has_data,
            rx.vstack(
                # Controls
                rx.grid(
                    rx.box(
                        rx.text("Horizon (GWs)"),
                        rx.select(["1", "2", "3", "5"], value=TransferAnalyzerState.horizon_len, on_change=TransferAnalyzerState.set_horizon)
                    ),
                    rx.box(
                        rx.text("Free Transfers"),
                        rx.select(["0", "1", "2", "3", "4", "5"], value=TransferAnalyzerState.ft_count, on_change=TransferAnalyzerState.set_fts)
                    ),
                    rx.box(
                        rx.text("Max Hits"),
                        rx.select(["0", "1", "2", "3", "4"], value=TransferAnalyzerState.max_hits, on_change=TransferAnalyzerState.set_max_hits)
                    ),
                    rx.box(
                        rx.text("Pitch View"),
                        rx.checkbox("", checked=TransferAnalyzerState.pitch_view, on_change=TransferAnalyzerState.set_pitch_view)
                    ),
                    rx.box(
                        rx.text("Betting xG"),
                        rx.checkbox("", checked=TransferAnalyzerState.enable_betting, on_change=TransferAnalyzerState.set_enable_betting)
                    ),
                    columns="5",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Multi Selects
                rx.grid(
                    rx.box(
                        rx.text("🔒 Keep / 🎯 Target", weight="bold"),
                        rx.select(TransferAnalyzerState.pos_options, value=rx.cond(TransferAnalyzerState.selected_positive.length() > 0, TransferAnalyzerState.selected_positive[0], ""), on_change=lambda x: TransferAnalyzerState.set_selected_positive([x]))
                        # Note: Reflex select only supports single selection easily out of the box in this form, so we adapt it.
                    ),
                    rx.box(
                        rx.text("🔴 Sell / ⛔ Block", weight="bold"),
                        rx.select(TransferAnalyzerState.neg_options, value=rx.cond(TransferAnalyzerState.selected_negative.length() > 0, TransferAnalyzerState.selected_negative[0], ""), on_change=lambda x: TransferAnalyzerState.set_selected_negative([x]))
                    ),
                    columns="2",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                rx.divider(),
                
                # Results Metrics
                rx.grid(
                    rx.box(rx.text("Current Bank", size="1", color="gray"), rx.text(TransferAnalyzerState.bank_balance, weight="bold")),
                    rx.box(rx.text("Bank After", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["bank_after"], weight="bold")),
                    rx.box(rx.text("Old xP", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["old_xp"], weight="bold")),
                    rx.box(rx.text("New xP", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["new_xp"], weight="bold")),
                    rx.box(rx.text("Diff", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["xp_diff"], weight="bold", color="green")),
                    columns="5",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Recommended Transfers
                rx.box(
                    rx.text("🔄 Recommended Transfer Moves", font_weight="bold", font_size="lg", margin_bottom="3"),
                    rx.cond(
                        TransferAnalyzerState.swaps.length() == 0,
                        rx.callout("✅ Your current squad is optimal for this horizon. No transfer yields higher starting points within your budget.", icon="check_check", color_scheme="green"),
                        rx.vstack(
                            rx.foreach(
                                TransferAnalyzerState.swaps,
                                lambda s: rx.card(
                                    rx.hstack(
                                        rx.box(
                                            rx.badge("TRANSFER OUT", color_scheme="red", radius="full", margin_bottom="1"),
                                            rx.text(s["out_name"], weight="bold"),
                                            rx.text(s["out_team"], size="1", color="gray"),
                                        ),
                                        rx.icon("arrow_right", size=24, color="gray"),
                                        rx.box(
                                            rx.badge(rx.cond(s["target"], "TARGET IN 🎯", "TRANSFER IN 🟢"), color_scheme=rx.cond(s["target"], "blue", "green"), radius="full", margin_bottom="1"),
                                            rx.text(s["in_name"], weight="bold"),
                                            rx.text(s["in_team"], size="1", color="gray"),
                                        ),
                                        rx.spacer(),
                                        rx.box(
                                            rx.text("Expected Gain", size="1", color="gray"),
                                            rx.text(f"+{s['gain']:.1f} xP", weight="bold", color="green"),
                                            rx.text(f"Cost Δ: £{s['cost_diff']:.1f}m", size="1", color="gray"),
                                            align_items="end"
                                        ),
                                        width="100%",
                                        align_items="center"
                                    ),
                                    width="100%",
                                    margin_bottom="2"
                                )
                            )
                        )
                    ),
                    margin_bottom="6"
                ),
                
                # Views
                rx.grid(
                    rx.box(
                        rx.text("Current Squad", weight="bold", margin_bottom="2"),
                        rx.cond(
                            TransferAnalyzerState.pitch_view,
                            rx.html(TransferAnalyzerState.base_pitch_html),
                            squad_list_view(TransferAnalyzerState.base_starters, TransferAnalyzerState.base_bench)
                        ),
                        width="100%"
                    ),
                    rx.box(
                        rx.text("Optimal Path", weight="bold", margin_bottom="2"),
                        rx.cond(
                            TransferAnalyzerState.pitch_view,
                            rx.html(TransferAnalyzerState.comp_pitch_html),
                            squad_list_view(TransferAnalyzerState.trans_starters, TransferAnalyzerState.trans_bench)
                        ),
                        width="100%"
                    ),
                    columns="2",
                    spacing="4",
                    width="100%"
                ),

                # Multi-Gameweek Performance Ledger
                rx.box(
                    rx.text("📋 Multi-Gameweek Performance Ledger", weight="bold", font_size="lg", margin_bottom="3"),
                    rx.data_table(
                        data=TransferAnalyzerState.ledger_data,
                        columns=TransferAnalyzerState.ledger_columns,
                        pagination=True,
                        search=True,
                        sort=True,
                        width="100%"
                    ),
                    width="100%",
                    margin_top="6"
                ),
                width="100%",
                spacing="4"
            )
        ),
        width="100%",
        on_mount=TransferAnalyzerState.analyze
    )
