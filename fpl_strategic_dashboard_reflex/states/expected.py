"""Domain State for Expected Stats (xG, xA, xGI)."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.expected import run_expected_analysis


class ExpectedStatsState(AppState):
    """Sub-state managing attacking expected metrics (xG, xA, xGI) and baseline filters."""

    is_loading: bool = False

    search_query: str = ""
    min_avg_mins: int = 0
    position_filter: str = "All"
    sort_by: str = "Projected Attacking xP"
    max_price: float = 15.5
    only_my_squad: bool = False
    show_career_baseline: bool = False

    # Cache tracking fields
    last_loaded_gw: int = 0
    last_loaded_mgr: str = ""
    last_sq: str = ""
    last_mm: int = 0
    last_pf: str = ""
    last_sb: str = ""
    last_mp: float = 0.0
    last_oms: bool = False
    last_scb: bool = False

    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        base_cols = [
            "Player", "Club", "Pos", "Price", "Mins", "Avg M/GW",
            "Pts", "Gls", "Ast", "CS", "Saves", "xG", "xA", "xGI", "Proj xP", "xGI/90"
        ]
        if self.show_career_baseline:
            return base_cols + ["Career GI/90", "Career Pts/90", "Career Mins"]
        return base_cols

    def set_search(self, val: str):
        self.search_query = val
        return ExpectedStatsState.load_data(True)

    def set_min_mins(self, val: list[float]):
        try:
            self.min_avg_mins = int(val[0])
        except Exception:
            pass
        return ExpectedStatsState.load_data(True)

    def set_pos(self, val: str):
        self.position_filter = val
        return ExpectedStatsState.load_data(True)

    def set_sort(self, val: str):
        self.sort_by = val
        return ExpectedStatsState.load_data(True)

    def set_price(self, val: list[float] | list[int]):
        try:
            self.max_price = float(val[0])
        except Exception:
            pass
        return ExpectedStatsState.load_data(True)

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return ExpectedStatsState.load_data(True)

    def set_career(self, val: bool):
        self.show_career_baseline = val
        return ExpectedStatsState.load_data(True)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches expected stats data bypassing caches."""
        return ExpectedStatsState.load_data(True)

    @rx.event(background=True)
    async def load_data(self, force_refresh: bool = False):
        async with self:
            manager_id = self.manager_id
            c_gw = self.current_gw
            sq = self.search_query
            mm = self.min_avg_mins
            pf = self.position_filter
            sb = self.sort_by
            mp = self.max_price
            oms = self.only_my_squad
            scb = self.show_career_baseline

            if self.has_data and not force_refresh and (
                c_gw == self.last_loaded_gw
                and manager_id == self.last_loaded_mgr
                and sq == self.last_sq
                and mm == self.last_mm
                and pf == self.last_pf
                and sb == self.last_sb
                and mp == self.last_mp
                and oms == self.last_oms
                and scb == self.last_scb
            ):
                return

            self.is_loading = True

        result = await asyncio.to_thread(
            run_expected_analysis,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb
        )

        async with self:
            if result:
                self.top_cards = result.get("cards", [])
                self.table_data = result.get("table", [])
            self.last_loaded_gw = c_gw
            self.last_loaded_mgr = manager_id
            self.last_sq = sq
            self.last_mm = mm
            self.last_pf = pf
            self.last_sb = sb
            self.last_mp = mp
            self.last_oms = oms
            self.last_scb = scb
            self.is_loading = False
