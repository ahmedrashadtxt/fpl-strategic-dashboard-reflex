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

    @rx.var
    def has_rows(self) -> bool:
        return len(self.rows) > 0

    @rx.var
    def gw_col_labels(self) -> list[str]:
        base = self.current_gw
        return [f"GW {base + i}" for i in range(5)]

    def set_search(self, val: str):
        self.search_query = val
        return FixtureTickerState.load_data

    def toggle_only_my_squad(self, val: bool):
        self.only_my_squad = val
        return FixtureTickerState.load_data

    def on_tab_visible(self):
        return FixtureTickerState.load_data

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            current_gw = self.current_gw
            search_query = self.search_query
            only_my_squad = self.only_my_squad
            manager_id = self.manager_id

        data = await asyncio.to_thread(
            _build_ticker_rows,
            current_gw,
            search_query,
            only_my_squad,
            manager_id,
        )

        async with self:
            self.rows = data
            self.is_loading = False

