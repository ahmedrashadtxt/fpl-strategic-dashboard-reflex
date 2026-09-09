"""Domain State for Squad Analyzer."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.squad import analyze_manager_squad


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
            self.status_message = "Syncing squad and match center..."

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
            analyze_manager_squad,
            manager_id, current_gw, sel_gw, chip, comp, super_t, betting, weight, movement
        )

        async with self:
            if result:
                self.mgr_name = result.get("mgr_name", "")
                self.overall_rank = result.get("overall_rank", 0)
                self.total_points = result.get("total_points", 0)
                self.active_gw_pts = result.get("active_gw_pts", 0)
                self.active_gw_label = result.get("active_gw_label", "Active GW")
                self.squad_value = result.get("squad_value", 0.0)
                self.bank_balance = result.get("bank_balance", 0.0)
                self.starters = result.get("starters", [])
                self.bench = result.get("bench", [])
                self.compare_starters = result.get("compare_starters", [])
                self.compare_bench = result.get("compare_bench", [])
                self.gw_options = result.get("gw_options", [])
                self.used_chips_keys = result.get("used_chips_keys", [])
                self.base_pitch_html = result.get("base_pitch_html", "")
                self.comp_pitch_html = result.get("comp_pitch_html", "")

                if str(self.selected_eval_gw) not in self.gw_options and self.gw_options:
                    self.selected_eval_gw = str(result.get("default_gw", self.gw_options[0]))
                self.squad_header_text = result.get("squad_header_text", "Current Squad")
                self.comp_header_text = result.get("comp_header_text", "Dream 15")
            self.is_loading = False

