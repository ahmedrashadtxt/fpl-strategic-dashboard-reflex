"""Domain State for Rolling Form analysis."""

import asyncio
from typing import Any, Dict, List
import plotly.graph_objects as go
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.rolling import run_rolling_analysis
from fpl_strategic_dashboard_reflex.services.table_sort import ROLLING_FORM_KEY_MAP, sort_table_rows

_rolling_form_cache: Dict[str, Dict[str, Any]] = {}


class RollingFormState(AppState):
    """Sub-state managing rolling multi-gameweek window performance and momentum."""

    is_loading: bool = False

    window_size: int = 5
    search_query: str = ""
    min_avg_mins: int = 45
    min_matches: int = 1
    position_filter: str = "All"
    sort_by: str = "Projected Form xP / Match"
    max_price: float = 17.0
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
    sort_column: str = "Proj Form xP"
    sort_direction: str = "desc"

    def handle_sort(self, col: str):
        if self.sort_column == col:
            self.sort_direction = "asc" if self.sort_direction == "desc" else "desc"
        else:
            self.sort_column = col
            self.sort_direction = "asc" if col in ("Player", "Club", "Pos", "Next 5 FDR") else "desc"
        self._apply_sort()

    def _apply_sort(self):
        if self.sort_column and self.table_data:
            self.table_data = sort_table_rows(
                self.table_data,
                self.sort_column,
                reverse=(self.sort_direction == "desc"),
                key_map=ROLLING_FORM_KEY_MAP,
            )

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        return [
            "Player", "Club", "Pos", "Price", "GW", "Proj Form xP",
            "Avg Pts", "xGI", "xGI/90", "Next 5 FDR", "Mins", "Apps"
        ]

    @rx.var
    def window_size_list(self) -> list[int]:
        return [self.window_size]

    @rx.var
    def min_matches_list(self) -> list[int]:
        return [self.min_matches]

    @rx.var
    def min_avg_mins_list(self) -> list[int]:
        return [self.min_avg_mins]

    @rx.var
    def max_price_list(self) -> list[float]:
        return [self.max_price]

    def set_window_drag(self, val: list[float]):
        if val:
            try:
                self.window_size = int(val[0])
            except Exception:
                pass

    def set_window(self, val: list[float]):
        if val:
            try:
                self.window_size = int(val[0])
            except Exception:
                self.window_size = 5
        return RollingFormState.load_data(False)

    def set_search(self, val: str):
        self.search_query = val
        return RollingFormState.load_data(False)

    def set_min_mins_drag(self, val: list[float]):
        if val:
            try:
                self.min_avg_mins = int(val[0])
            except Exception:
                pass

    def set_min_mins(self, val: list[float]):
        if val:
            try:
                self.min_avg_mins = int(val[0])
            except Exception:
                pass
        return RollingFormState.load_data(False)

    def set_min_matches_drag(self, val: list[float]):
        if val:
            try:
                self.min_matches = int(val[0])
            except Exception:
                pass

    def set_min_matches(self, val: list[float]):
        if val:
            try:
                self.min_matches = int(val[0])
            except Exception:
                pass
        return RollingFormState.load_data(False)

    def set_pos(self, val: str):
        self.position_filter = val
        return RollingFormState.load_data(False)

    def set_sort(self, val: str):
        self.sort_by = val
        sort_by_col_map = {
            "Projected Form xP / Match": ("Proj Form xP", "desc"),
            "Rolling Avg Points": ("Avg Pts", "desc"),
            "Rolling Sum xGI": ("xGI", "desc"),
            "Rolling xGI / 90": ("xGI/90", "desc"),
            "Upcoming Fixture Ease": ("Next 5 FDR", "asc"),
            "Rolling Avg Minutes": ("Mins", "desc"),
            "Price": ("Price", "desc"),
        }
        col, dir_ = sort_by_col_map.get(val, ("Proj Form xP", "desc"))
        self.sort_column = col
        self.sort_direction = dir
        return RollingFormState.load_data(False)

    def set_price_drag(self, val: list[float]):
        if val:
            try:
                self.max_price = round(float(val[0]), 1)
            except Exception:
                pass

    def set_price(self, val: list[float]):
        if val:
            try:
                self.max_price = round(float(val[0]), 1)
            except Exception:
                pass
        return RollingFormState.load_data(False)

    def set_only_my_squad(self, val: bool):
        self.only_my_squad = val
        return RollingFormState.load_data(False)

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return RollingFormState.load_data(False)

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

            cache_key = f"{c_gw}_{manager_id}_{ws}_{sq}_{mm}_{pf}_{sb}_{oms}_{mp:.1f}_{mmat}"

            if not force_refresh and cache_key in _rolling_form_cache:
                result = _rolling_form_cache[cache_key]
                self.top_cards = result.get("top_cards", result.get("cards", []))
                self.table_data = result.get("table", [])
                self.plot_fig = result.get("fig", go.Figure())
                self._apply_sort()
                self.is_loading = False
                return

            self.is_loading = True

        if force_refresh:
            _rolling_form_cache.clear()

        result = await asyncio.to_thread(
            run_rolling_analysis,
            c_gw, manager_id, ws, sq, mm, pf, sb, oms, mp, mmat
        )

        async with self:
            if result:
                _rolling_form_cache[cache_key] = result
                self.top_cards = result.get("top_cards", result.get("cards", []))
                self.table_data = result.get("table", [])
                self.plot_fig = result.get("fig", go.Figure())
                self._apply_sort()
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
