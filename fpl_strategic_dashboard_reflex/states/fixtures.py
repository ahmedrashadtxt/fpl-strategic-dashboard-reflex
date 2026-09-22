"""Domain State for Fixture Ticker."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.fixtures import _build_ticker_rows


class FixtureTickerState(AppState):
    """Sub-state managing the 5-GW forward fixture difficulty rating (FDR) matrix."""

    search_query: str = ""
    only_my_squad: bool = False
    rows: List[Dict[str, Any]] = []
    is_loading: bool = False

    # Cache tracking fields
    last_loaded_gw: int = 0
    last_loaded_mgr: str = ""
    last_search: str = ""
    last_only_squad: bool = False

    @rx.var
    def has_rows(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def gw_col_labels(self) -> list[str]:
        base = self.current_gw
        return [f"GW {base + i}" for i in range(5)]

    @rx.var
    def horizon_label(self) -> str:
        base = self.current_gw
        return f"GW{base}–GW{base + 4}"

    @rx.var
    def needs_manager_id(self) -> bool:
        return self.only_my_squad and (not self.manager_id or self.manager_id.strip() == "")

    def set_search(self, val: str):
        self.search_query = val
        return FixtureTickerState.load_data(True)

    def toggle_only_my_squad(self, val: bool):
        self.only_my_squad = val
        return FixtureTickerState.load_data(True)

    def on_tab_visible(self):
        return FixtureTickerState.load_data(False)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches ticker data bypassing caches."""
        return FixtureTickerState.load_data(True)

    @rx.event(background=True)
    async def load_data(self, force_refresh: bool = False):
        async with self:
            current_gw = self.current_gw
            search_query = self.search_query
            only_my_squad = self.only_my_squad
            manager_id = self.manager_id

            if self.has_rows and not force_refresh and (
                current_gw == self.last_loaded_gw
                and manager_id == self.last_loaded_mgr
                and search_query == self.last_search
                and only_my_squad == self.last_only_squad
            ):
                return

            self.is_loading = True

        data = await asyncio.to_thread(
            _build_ticker_rows,
            current_gw,
            search_query,
            only_my_squad,
            manager_id,
        )

        async with self:
            self.rows = data
            self.last_loaded_gw = current_gw
            self.last_loaded_mgr = manager_id
            self.last_search = search_query
            self.last_only_squad = only_my_squad
            self.is_loading = False
