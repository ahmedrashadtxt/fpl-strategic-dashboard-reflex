"""Domain State for Rolling Form analysis."""

import asyncio
from typing import Any, Dict, List
import plotly.graph_objects as go
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.rolling import run_rolling_analysis


class RollingFormState(AppState):
    """Sub-state managing rolling multi-gameweek window performance and momentum."""

    is_loading: bool = False

    window_size: int = 5
    search_query: str = ""
    min_avg_mins: int = 45
    min_matches: int = 1
    position_filter: str = "All"
    sort_by: str = "Projected Form xP / Match"
    max_price: float = 15.5
    only_my_squad: bool = False

    # Cache tracking fields
    last_loaded_gw: int = 0
    last_loaded_mgr: str = ""
    last_ws: int = 0
    last_sq: str = ""
    last_mm: int = 0
    last_pf: str = ""
    last_sb: str = ""
    last_oms: bool = False
    last_mp: float = 0.0
    last_mmat: int = 0

    plot_fig: go.Figure = go.Figure()
    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        return [
            "Player", "Club", "Pos", "Price", "GW", "Proj Form xP",
            "Avg Pts", "xGI", "xGI/90", "Next 5 FDR", "Mins", "Apps"
        ]

    def set_window(self, val: list[float]):
        try:
            self.window_size = int(val[0])
        except Exception:
            self.window_size = 5
        return RollingFormState.load_data(True)

    def set_search(self, val: str):
        self.search_query = val
        return RollingFormState.load_data(True)

    def set_min_mins(self, val: list[float]):
        try:
            self.min_avg_mins = int(val[0])
        except Exception:
            pass
        return RollingFormState.load_data(True)

    def set_min_matches(self, val: list[float]):
        try:
            self.min_matches = int(val[0])
        except Exception:
            pass
        return RollingFormState.load_data(True)

    def set_pos(self, val: str):
        self.position_filter = val
        return RollingFormState.load_data(True)

    def set_sort(self, val: str):
        self.sort_by = val
        return RollingFormState.load_data(True)

    def set_price(self, val: list[float]):
        try:
            self.max_price = float(val[0])
        except Exception:
            pass
        return RollingFormState.load_data(True)

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return RollingFormState.load_data(True)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches rolling form data bypassing caches."""
        return RollingFormState.load_data(True)

    @rx.event(background=True)
    async def load_data(self, force_refresh: bool = False):
        async with self:
            manager_id = self.manager_id
            c_gw = self.current_gw
            ws = self.window_size
            sq = self.search_query
            mm = self.min_avg_mins
            pf = self.position_filter
            sb = self.sort_by
            oms = self.only_my_squad
            mp = self.max_price
            mmat = self.min_matches

            if self.has_data and not force_refresh and (
                c_gw == self.last_loaded_gw
                and manager_id == self.last_loaded_mgr
                and ws == self.last_ws
                and sq == self.last_sq
                and mm == self.last_mm
                and pf == self.last_pf
                and sb == self.last_sb
                and oms == self.last_oms
                and mp == self.last_mp
                and mmat == self.last_mmat
            ):
                return

            self.is_loading = True

        result = await asyncio.to_thread(
            run_rolling_analysis,
            c_gw, manager_id, ws, sq, mm, pf, sb, oms, mp, mmat
        )

        async with self:
            if result:
                self.top_cards = result.get("top_cards", result.get("cards", []))
                self.table_data = result.get("table", [])
                self.plot_fig = result.get("fig", go.Figure())
            self.last_loaded_gw = c_gw
            self.last_loaded_mgr = manager_id
            self.last_ws = ws
            self.last_sq = sq
            self.last_mm = mm
            self.last_pf = pf
            self.last_sb = sb
            self.last_oms = oms
            self.last_mp = mp
            self.last_mmat = mmat
            self.is_loading = False
