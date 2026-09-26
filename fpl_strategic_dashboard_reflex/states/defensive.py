"""Domain State for Defensive Contributions."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.defensive import run_defensive_analysis
from fpl_strategic_dashboard_reflex.services.table_sort import DEFENSIVE_STATS_KEY_MAP, sort_table_rows

_defensive_stats_cache: Dict[str, Dict[str, Any]] = {}


class DefensiveStatsState(AppState):
    """Sub-state managing defensive statistics (xGC, Clean Sheets, CBI, Saves)."""

    is_loading: bool = False

    search_query: str = ""
    min_avg_mins: int = 0
    position_filter: str = "All"
    sort_by: str = "Projected Defensive xP"
    max_price: float = 17.0
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
    sort_column: str = "Proj Def xP"
    sort_direction: str = "desc"

    def handle_sort(self, col: str):
        if self.sort_column == col:
            self.sort_direction = "asc" if self.sort_direction == "desc" else "desc"
        else:
            self.sort_column = col
            self.sort_direction = "asc" if col in ("Player", "Club", "Pos") else "desc"
        self._apply_sort()

    def _apply_sort(self):
        if self.sort_column and self.table_data:
            self.table_data = sort_table_rows(
                self.table_data,
                self.sort_column,
                reverse=(self.sort_direction == "desc"),
                key_map=DEFENSIVE_STATS_KEY_MAP,
            )

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> list[str]:
        base_cols = [
            "Player", "Club", "Pos", "Price", "Mins", "Avg M/GW",
            "Pts", "CS", "GC", "xGC", "Proj Def xP", "xGC/90",
            "DC", "DC/90", "CBI", "R", "T"
        ]
        if self.show_career_baseline:
            return base_cols + ["Career GC/90", "Career CS/90", "Career Pts/90", "Career Mins"]
        return base_cols

    @rx.var
    def min_avg_mins_list(self) -> list[int]:
        return [self.min_avg_mins]

    @rx.var
    def max_price_list(self) -> list[float]:
        return [self.max_price]

    def set_search(self, val: str):
        self.search_query = val
        return DefensiveStatsState.load_data(False)

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
        return DefensiveStatsState.load_data(False)

    def set_pos(self, val: str):
        self.position_filter = val
        return DefensiveStatsState.load_data(False)

    def set_sort(self, val: str):
        self.sort_by = val
        sort_by_col_map = {
            "Projected Defensive xP": "Proj Def xP",
            "Expected Goals Conceded (xGC)": "xGC",
            "xGC per 90": "xGC/90",
            "Defensive Contributions (DC)": "DC",
            "DC per 90": "DC/90",
            "Clean Sheets": "CS",
            "Goalkeeper Saves": "Saves",
            "Total Points": "Pts",
            "Clearances, Blocks, Interceptions (CBI)": "CBI",
        }
        self.sort_column = sort_by_col_map.get(val, "Proj Def xP")
        self.sort_direction = "desc"
        return DefensiveStatsState.load_data(False)

    def set_price_drag(self, val: list[float]):
        if val:
            try:
                self.max_price = round(float(val[0]), 1)
            except Exception:
                pass

    def set_price(self, val: list[float] | list[int]):
        if val:
            try:
                self.max_price = round(float(val[0]), 1)
            except Exception:
                pass
        return DefensiveStatsState.load_data(False)

    def set_only_my_squad(self, val: bool):
        self.only_my_squad = val
        return DefensiveStatsState.load_data(False)

    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return DefensiveStatsState.load_data(False)

    def set_career(self, val: bool):
        self.show_career_baseline = val
        return DefensiveStatsState.load_data(False)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches defensive stats data bypassing caches."""
        return DefensiveStatsState.load_data(True)

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

            cache_key = f"{c_gw}_{manager_id}_{sq}_{mm}_{pf}_{sb}_{mp:.1f}_{oms}_{scb}"

            if not force_refresh and cache_key in _defensive_stats_cache:
                result = _defensive_stats_cache[cache_key]
                self.top_cards = result.get("cards", [])
                self.table_data = result.get("table", [])
                self._apply_sort()
                self.is_loading = False
                return

            self.is_loading = True

        if force_refresh:
            _defensive_stats_cache.clear()

        result = await asyncio.to_thread(
            run_defensive_analysis,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb
        )

        async with self:
            if result:
                _defensive_stats_cache[cache_key] = result
                self.top_cards = result.get("cards", [])
                self.table_data = result.get("table", [])
                self._apply_sort()
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
