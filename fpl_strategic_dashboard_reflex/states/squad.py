"""Domain State for Squad Analyzer."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.squad import (
    analyze_manager_squad,
    fetch_live_gameweek_points,
    fetch_dream_team_data,
    fetch_motw_manager_data,
)


_squad_results_cache: Dict[str, Dict[str, Any]] = {}


class SquadAnalyzerState(AppState):
    """Sub-state managing squad analysis, pitch visualization, chips, and dream team comparison."""

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
    is_live_or_finished: bool = False
    last_loaded_manager_id: str = ""

    starters: List[Dict[str, Any]] = []
    bench: List[Dict[str, Any]] = []
    compare_starters: List[Dict[str, Any]] = []
    compare_bench: List[Dict[str, Any]] = []
    gw_options: List[str] = []
    gw_labels: List[str] = []
    gw_map: Dict[str, str] = {}
    selected_eval_label: str = ""
    used_chips_keys: List[str] = []

    market_disagreements: List[Dict[str, Any]] = []
    market_movements: List[Dict[str, Any]] = []

    base_pitch_html: str = ""
    comp_pitch_html: str = ""

    # Live Match Center Banner & Second Layer of KPI Cards
    banner_title: str = ""
    banner_subtext: str = ""
    banner_diff_text: str = ""
    banner_diff_color: str = "green"
    show_banner: bool = False

    kpi2_card1_label: str = "Net GW Points (Live)"
    kpi2_card1_val: str = "0 pts"
    kpi2_card1_delta: str = ""
    kpi2_card1_delta_color: str = "green"

    kpi2_card2_label: str = "Gameweek Rank"
    kpi2_card2_val: str = "Updating..."
    kpi2_card2_delta: str = ""
    kpi2_card2_delta_color: str = "green"

    kpi2_card3_label: str = "Players Played"
    kpi2_card3_val: str = "0 / 11"
    kpi2_card3_delta: str = ""
    kpi2_card3_delta_color: str = "green"

    kpi2_card4_label: str = "Captain (C)"
    kpi2_card4_val: str = "0 pts"
    kpi2_card4_delta: str = ""
    kpi2_card4_delta_color: str = "green"

    @rx.var
    def has_data(self) -> bool:
        return len(self.starters) > 0

    @rx.var
    def has_market_disagreements(self) -> bool:
        return len(self.market_disagreements) > 0

    @rx.var
    def has_market_movements(self) -> bool:
        return len(self.market_movements) > 0

    @rx.var
    def market_weight_pct(self) -> list[int]:
        return [int(round(self.market_weight * 100))]

    @rx.var
    def market_weight_display(self) -> str:
        return f"{self.market_weight:.2f}"

    @rx.var
    def show_betting_controls(self) -> bool:
        return not self.is_live_or_finished

    def _apply_squad_result(self, result: Dict[str, Any], manager_id: str):
        """Populates state attributes directly from a computed result dictionary."""
        if not result:
            return
        self.last_loaded_manager_id = manager_id
        self.has_manager_data = True
        self.mgr_name = result.get("mgr_name", "")
        self.overall_rank = result.get("overall_rank", 0)
        self.rank_delta = result.get("rank_delta", "")
        self.rank_delta_color = result.get("rank_delta_color", "green")
        self.total_points = result.get("total_points", 0)
        self.active_gw_pts = result.get("active_gw_pts", 0)
        self.active_gw_label = result.get("active_gw_label", "Active GW")
        self.gw_avg_pts = result.get("gw_avg_pts", 0)
        self.gw_avg_label = result.get("gw_avg_label", "GW Average")
        self.gw_avg_diff_str = result.get("gw_avg_diff_str", "")
        self.hero_perf_status = result.get("hero_perf_status", "green")
        self.squad_value = result.get("squad_value", 0.0)
        self.bank_balance = result.get("bank_balance", 0.0)
        self.starters = result.get("starters", [])
        self.bench = result.get("bench", [])
        self.compare_starters = result.get("compare_starters", [])
        self.gw_options = result.get("gw_options", [])
        self.gw_labels = result.get("gw_labels", [])
        self.gw_map = result.get("gw_map", {})
        self.selected_eval_gw = result.get("selected_eval_gw", self.selected_eval_gw)
        self.selected_eval_label = result.get("selected_eval_label", "")
        self.used_chips_keys = result.get("used_chips_keys", [])
        self.base_pitch_html = result.get("base_pitch_html", "")
        self.comp_pitch_html = result.get("comp_pitch_html", "")
        self.market_disagreements = result.get("market_disagreements", [])
        self.market_movements = result.get("market_movements", [])
        self.is_live_or_finished = result.get("is_live_or_finished", False)

        self.squad_header_text = result.get("squad_header_text", "Current Squad")
        self.comp_header_text = result.get("comp_header_text", "Dream 15")

        self.banner_title = result.get("banner_title", "")
        self.banner_subtext = result.get("banner_subtext", "")
        self.banner_diff_text = result.get("banner_diff_text", "")
        self.banner_diff_color = result.get("banner_diff_color", "green")
        self.show_banner = result.get("show_banner", False)

        self.kpi2_card1_label = result.get("kpi2_card1_label", "Net GW Points (Live)")
        self.kpi2_card1_val = result.get("kpi2_card1_val", "0 pts")
        self.kpi2_card1_delta = result.get("kpi2_card1_delta", "")
        self.kpi2_card1_delta_color = result.get("kpi2_card1_delta_color", "green")

        self.kpi2_card2_label = result.get("kpi2_card2_label", "Gameweek Rank")
        self.kpi2_card2_val = result.get("kpi2_card2_val", "Updating...")
        self.kpi2_card2_delta = result.get("kpi2_card2_delta", "")
        self.kpi2_card2_delta_color = result.get("kpi2_card2_delta_color", "green")

        self.kpi2_card3_label = result.get("kpi2_card3_label", "Players Played")
        self.kpi2_card3_val = result.get("kpi2_card3_val", "0 / 11")
        self.kpi2_card3_delta = result.get("kpi2_card3_delta", "")
        self.kpi2_card3_delta_color = result.get("kpi2_card3_delta_color", "green")

        self.kpi2_card4_label = result.get("kpi2_card4_label", "Captain (C)")
        self.kpi2_card4_val = result.get("kpi2_card4_val", "0 pts")
        self.kpi2_card4_delta = result.get("kpi2_card4_delta", "")
        self.kpi2_card4_delta_color = result.get("kpi2_card4_delta_color", "green")

    def toggle_chip(self, chip: str):
        if self.simulated_chip == chip:
            self.simulated_chip = "None"
        else:
            self.simulated_chip = chip
        return SquadAnalyzerState.load_squad(False)

    def set_simulated_chip(self, val: str):
        self.simulated_chip = val
        return SquadAnalyzerState.load_squad(False)

    def set_eval_label(self, label: str):
        self.selected_eval_label = label
        if label in self.gw_map:
            self.selected_eval_gw = self.gw_map[label]
        if "Finished" in label or "Live" in label:
            self.is_live_or_finished = True
        elif "Upcoming" in label:
            self.is_live_or_finished = False
        return SquadAnalyzerState.load_squad(False)

    def set_eval_gw(self, gw: str):
        self.selected_eval_gw = str(gw)
        for lbl, gid in self.gw_map.items():
            if gid == str(gw):
                self.selected_eval_label = lbl
                break
        if "Finished" in self.selected_eval_label or "Live" in self.selected_eval_label:
            self.is_live_or_finished = True
        elif "Upcoming" in self.selected_eval_label:
            self.is_live_or_finished = False
        return SquadAnalyzerState.load_squad(False)

    def set_pitch_view(self, val: bool):
        self.pitch_view = bool(val)

    def set_view_mode(self, val: str | list[str]):
        if isinstance(val, list):
            mode = val[0] if val else "pitch"
        else:
            mode = val
        self.pitch_view = (mode == "pitch")

    def set_enable_comparison(self, val: bool):
        self.enable_comparison = val
        if not val:
            self.super_team_mode = False
        return SquadAnalyzerState.load_squad(False)

    def set_super_team_mode(self, val: bool):
        self.super_team_mode = val
        return SquadAnalyzerState.load_squad(False)

    def set_enable_betting(self, val: bool):
        self.enable_betting = val
        return SquadAnalyzerState.load_squad(False)

    def set_market_weight_drag(self, val: list[float]):
        if val:
            self.market_weight = round(float(val[0]) / 100.0, 2)

    def set_market_weight(self, val: list[float]):
        if val:
            self.market_weight = round(float(val[0]) / 100.0, 2)
        return SquadAnalyzerState.load_squad(False)

    def set_factor_movement(self, val: bool):
        self.factor_movement = val
        return SquadAnalyzerState.load_squad(False)

    @rx.event
    def refresh_squad(self):
        """Explicitly re-fetches squad data, bypassing state and TTL caches."""
        return SquadAnalyzerState.load_squad(True)

    @rx.event(background=True)
    async def load_squad(self, force_refresh: bool = False):
        async with self:
            if not self.manager_id:
                return

            manager_id = self.manager_id
            current_gw = self.current_gw
            sel_gw = self.selected_eval_gw
            chip = self.simulated_chip
            comp = self.enable_comparison
            super_t = self.super_team_mode
            betting = self.enable_betting
            weight = self.market_weight
            movement = self.factor_movement

            cache_key = f"{manager_id}_{current_gw}_{sel_gw}_{chip}_{comp}_{super_t}_{betting}_{weight:.2f}_{movement}"

            # Fast cache hit: apply instantly without toggling is_loading = True
            if not force_refresh and cache_key in _squad_results_cache:
                self._apply_squad_result(_squad_results_cache[cache_key], manager_id)
                self.is_loading = False
                return

            self.is_loading = True
            self.status_message = "Syncing squad and match center..."

        if force_refresh:
            _squad_results_cache.clear()
            if hasattr(analyze_manager_squad, "clear_cache"):
                analyze_manager_squad.clear_cache()
            if hasattr(fetch_live_gameweek_points, "clear_cache"):
                fetch_live_gameweek_points.clear_cache()
            if hasattr(fetch_dream_team_data, "clear_cache"):
                fetch_dream_team_data.clear_cache()
            if hasattr(fetch_motw_manager_data, "clear_cache"):
                fetch_motw_manager_data.clear_cache()

        result = await asyncio.to_thread(
            analyze_manager_squad,
            manager_id, current_gw, sel_gw, chip, comp, super_t, betting, weight, movement
        )

        async with self:
            if result:
                _squad_results_cache[cache_key] = result
                self._apply_squad_result(result, manager_id)
            self.is_loading = False

