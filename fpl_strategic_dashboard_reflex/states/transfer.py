"""Domain State for Transfer Analyzer / Solver."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.transfer import analyze_transfers


class TransferAnalyzerState(AppState):
    """Sub-state managing multi-gameweek transfer optimization, budget, and swaps."""

    is_loading: bool = False
    status_message: str = "Loading transfer market..."

    horizon_len: str = "1"
    ft_count: str = "1"
    max_hits: str = "0"
    pitch_view: bool = True
    enable_betting: bool = True
    market_weight: float = 0.35
    min_mins: int = 45

    pos_options: List[str] = []
    neg_options: List[str] = []
    selected_positive: List[str] = []
    selected_negative: List[str] = []

    bank_balance: float = 0.0
    swaps: List[Dict[str, Any]] = []

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
        "xp_diff": 0.0,
    }

    @rx.var
    def has_data(self) -> bool:
        return len(self.base_starters) > 0

    @rx.var
    def total_allowed_transfers(self) -> int:
        try:
            return int(self.ft_count) + int(self.max_hits)
        except (ValueError, TypeError):
            return 1

    def set_horizon(self, val: str):
        self.horizon_len = str(val)
        return TransferAnalyzerState.analyze

    def set_fts(self, val: str):
        self.ft_count = str(val)
        return TransferAnalyzerState.analyze

    def set_max_hits(self, val: str):
        self.max_hits = str(val)
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

            manager_id = self.manager_id
            current_gw = self.current_gw
            try:
                horizon = int(self.horizon_len)
                ft = int(self.ft_count)
                hits = int(self.max_hits)
            except Exception:
                horizon, ft, hits = 1, 1, 0

            betting = self.enable_betting
            weight = self.market_weight
            mins = self.min_mins
            pos_sel = self.selected_positive
            neg_sel = self.selected_negative

        result = await asyncio.to_thread(
            analyze_transfers,
            manager_id, current_gw, horizon, ft, hits, betting, weight, mins, pos_sel, neg_sel
        )

        async with self:
            if result:
                self.pos_options = result.get("pos_options", [])
                self.neg_options = result.get("neg_options", [])
                self.bank_balance = result.get("bank_balance", 0.0)
                self.swaps = result.get("swaps", [])
                self.base_starters = result.get("base_starters", [])
                self.base_bench = result.get("base_bench", [])
                self.trans_starters = result.get("trans_starters", [])
                self.trans_bench = result.get("trans_bench", [])
                self.base_pitch_html = result.get("base_pitch_html", "")
                self.comp_pitch_html = result.get("comp_pitch_html", "")
                self.metrics = result.get("metrics", self.metrics)

                if result.get("init_ft"):
                    self.ft_count = str(result["init_ft"])
            self.is_loading = False

