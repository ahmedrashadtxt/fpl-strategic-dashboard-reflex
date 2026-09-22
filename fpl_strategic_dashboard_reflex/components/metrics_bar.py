"""Summary metrics overview bar."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.metrics import DashboardMetricsState
from fpl_strategic_dashboard_reflex.components.metric_card import metric_card


def metrics_bar() -> rx.Component:
    """Renders the top summary KPIs bar."""
    return rx.hstack(
        metric_card("Active Assets", DashboardMetricsState.total_players.to_string(), "Tracked", "gray"),
        metric_card("Underperforming xG", DashboardMetricsState.buy_signals.to_string(), "Buy Signals", "green"),
        metric_card("Overperforming xG", DashboardMetricsState.sell_signals.to_string(), "Sell Signals", "red"),
        metric_card("Transfer Momentum", DashboardMetricsState.heating_transfers.to_string(), "Heating 🔥", "amber"),
        metric_card("Cold Outflows", DashboardMetricsState.cooling_transfers.to_string(), "Cooling ❄️", "blue"),
        metric_card("Transfer Momentum", DashboardMetricsState.heating_transfers.to_string(), "High Inflow", "amber"),
        metric_card("Cold Outflows", DashboardMetricsState.cooling_transfers.to_string(), "High Outflow", "blue"),
        width="100%",
        spacing="3",
        wrap="wrap",
        margin_bottom="1.5rem",
    )
