"""Domain State for Transfer Market, Price Predictions, and Target Scout."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.market import run_market_analysis

_market_cache: Dict[str, Dict[str, Any]] = {}


class TransferMarketState(AppState):
    """Sub-state managing transfer targets and scout analysis."""

    is_loading: bool = False

    search_query: str = ""
    pos_filter: str = "All"
    sort_by: str = "Projected Points (xP)"
    max_price: float = 15.5
    exclude_my_squad: bool = True
    enable_betting: bool = True

    # Cache tracking fields
    last_loaded_gw: int = 0
    last_loaded_mgr: str = ""
    last_sq: str = ""
    last_pf: str = ""
    last_sb: str = ""
    last_mp: float = 0.0
    last_ems: bool = False
    last_eb: bool = False

    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []

    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0

    @rx.var
    def columns(self) -> List[str]:
        return [
            "Target Player", "Club", "Pos", "Price", "Price Trend",
            "GW Fixture", "FDR", "Proj xP", "xP / £M", "Form", "Own %", "Season Pts"
        ]

    def set_search(self, value: str):
        self.search_query = value
        return TransferMarketState.load_data(False)

    def set_pos_filter(self, value: str):
        self.pos_filter = value
        return TransferMarketState.load_data(False)

    def set_sort_by(self, value: str):
        self.sort_by = value
        return TransferMarketState.load_data(False)

    def set_max_price(self, value: list[float]):
        try:
            self.max_price = float(value[0])
        except Exception:
            pass
        return TransferMarketState.load_data(False)

    def toggle_exclude(self, value: bool):
        self.exclude_my_squad = value
        return TransferMarketState.load_data(False)

    def toggle_betting(self, value: bool):
        self.enable_betting = value
        return TransferMarketState.load_data(False)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches market data bypassing caches."""
        return TransferMarketState.load_data(True)

    @rx.event(background=True)
    async def load_data(self, force_refresh: bool = False):
        async with self:
            mgr_id = self.manager_id
            c_gw = self.current_gw
            sq = self.search_query
            pf = self.pos_filter
            sb = self.sort_by
            mp = self.max_price
            ems = self.exclude_my_squad
            eb = self.enable_betting

            cache_key = f"{c_gw}_{mgr_id}_{sq}_{pf}_{sb}_{mp:.1f}_{ems}_{eb}"

            if not force_refresh and cache_key in _market_cache:
                result = _market_cache[cache_key]
                self.top_cards = result.get("top_cards", result.get("cards", []))
                self.table_data = result.get("table", [])
                self.is_loading = False
                return

            self.is_loading = True

        if force_refresh:
            _market_cache.clear()

        try:
            result = await asyncio.to_thread(
                run_market_analysis,
                c_gw, mgr_id, sq, pf, sb, mp, ems, eb
            )
        except Exception as ex:
            print(f"Transfer market load error: {ex}")
            result = {"top_cards": [], "cards": [], "table": []}

        async with self:
            if result:
                _market_cache[cache_key] = result
                self.top_cards = result.get("top_cards", result.get("cards", []))
                self.table_data = result.get("table", [])
            self.last_loaded_gw = c_gw
            self.last_loaded_mgr = mgr_id
            self.last_sq = sq
            self.last_pf = pf
            self.last_sb = sb
            self.last_mp = mp
            self.last_ems = ems
            self.last_eb = eb
            self.is_loading = False
