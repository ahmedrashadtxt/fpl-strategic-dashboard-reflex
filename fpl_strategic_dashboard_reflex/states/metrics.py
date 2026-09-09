"""State for high-level dashboard metrics overview bar."""

import asyncio
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.db import get_connection, get_summary_stats


class DashboardMetricsState(AppState):
    """Sub-state managing global overview metrics displayed on the top bar."""

    total_players: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    heating_transfers: int = 0
    cooling_transfers: int = 0
    is_loading_metrics: bool = False

    @rx.event(background=True)
    async def load_metrics(self):
        async with self:
            self.is_loading_metrics = True

        def _fetch():
            conn = get_connection()
            df = get_summary_stats(conn)
            if not df.empty:
                r = df.iloc[0]
                return (
                    int(r.get("total", 0) or 0),
                    int(r.get("buy_signals", 0) or 0),
                    int(r.get("sell_signals", 0) or 0),
                    int(r.get("heating", 0) or 0),
                    int(r.get("cooling", 0) or 0),
                )
            return (0, 0, 0, 0, 0)

        tot, buy, sell, heat, cool = await asyncio.to_thread(_fetch)

        async with self:
            self.total_players = tot
            self.buy_signals = buy
            self.sell_signals = sell
            self.heating_transfers = heat
            self.cooling_transfers = cool
            self.is_loading_metrics = False

