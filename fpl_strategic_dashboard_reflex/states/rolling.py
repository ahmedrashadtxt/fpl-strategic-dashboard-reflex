"""Domain State for Rolling Form analysis."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.rolling import run_rolling_analysis


class RollingFormState(AppState):
    """Sub-state managing rolling multi-gameweek window performance and momentum."""

    is_loading: bool = False

    window_size: int = 5
    search_query: str = ""
    min_avg_mins: int = 45
    position_filter: str = "All"
    sort_by: str = "Form vs Price Ratio"
    only_my_squad: bool = False

    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        return [
            "Player", "Team", "Pos", "Price", "Roll_Mins_GW",
            "Roll_Points_GW", "Form_Price_Ratio", "Roll_xGI_90",
            "Roll_ICT_GW", "FDR_Next_5", "FDR_Difficulty", "BPS"
        ]

    def set_window(self, val: str):
        try:
            self.window_size = int(val)
        except Exception:
            self.window_size = 5
        return RollingFormState.load_data

    def set_search(self, val: str):
        self.search_query = val
        return RollingFormState.load_data

    def set_min_mins(self, val: list[int]):
        self.min_avg_mins = val[0]
        return RollingFormState.load_data

    def set_pos(self, val: str):
        self.position_filter = val
        return RollingFormState.load_data

    def set_sort(self, val: str):
        self.sort_by = val
        return RollingFormState.load_data

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return RollingFormState.load_data

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            manager_id = self.manager_id
            c_gw = self.current_gw
            ws = self.window_size
            sq = self.search_query
            mm = self.min_avg_mins
            pf = self.position_filter
            sb = self.sort_by
            oms = self.only_my_squad

        result = await asyncio.to_thread(
            run_rolling_analysis,
            c_gw, manager_id, ws, sq, mm, pf, sb, oms
        )

        async with self:
            if result:
                self.top_cards = result.get("cards", [])
                self.table_data = result.get("table", [])
            self.is_loading = False

