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
    sort_by: str = "Projected Gameweek xP (Total)"
    max_price: float = 15.0
    only_my_squad: bool = False
    show_career_baseline: bool = False

    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        return [
            "Player", "Team", "Pos", "Price", "Avg_Mins_GW",
            "Total_Points", "xG", "xA", "xGI", "gw_xp", "Form", "Att_Ret_Prob", "BPS"
        ]

    def set_search(self, val: str):
        self.search_query = val
        return ExpectedStatsState.load_data

    def set_min_mins(self, val: list[int]):
        self.min_avg_mins = val[0]
        return ExpectedStatsState.load_data

    def set_pos(self, val: str):
        self.position_filter = val
        return ExpectedStatsState.load_data

    def set_sort(self, val: str):
        self.sort_by = val
        return ExpectedStatsState.load_data

    def set_price(self, val: list[int]):
        self.max_price = val[0] / 10.0
        return ExpectedStatsState.load_data

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return ExpectedStatsState.load_data

    def set_career(self, val: bool):
        self.show_career_baseline = val
        return ExpectedStatsState.load_data

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            manager_id = self.manager_id
            c_gw = self.current_gw
            sq = self.search_query
            mm = self.min_avg_mins
            pf = self.position_filter
            sb = self.sort_by
            mp = self.max_price
            oms = self.only_my_squad
            scb = self.show_career_baseline

        result = await asyncio.to_thread(
            run_expected_analysis,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb
        )

        async with self:
            if result:
                self.top_cards = result.get("cards", [])
                self.table_data = result.get("table", [])
            self.is_loading = False

