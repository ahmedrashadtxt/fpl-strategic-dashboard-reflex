"""Summary metrics overview bar."""

import reflex as rx
from fpl_strategic_dashboard_reflex.state import AppState
from fpl_strategic_dashboard_reflex.states.metrics import DashboardMetricsState
from fpl_strategic_dashboard_reflex.components.metric_card import metric_card


def metric_item(label: str, value: rx.Var, badge_text: str = "", color: str = "blue") -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(label, class_name="metric-card-label"),
                rx.text(value, class_name="metric-card-value"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.cond(
                badge_text != "",
                rx.badge(badge_text, variant="soft", color_scheme=color, radius="full", size="1"),
                rx.box(),
            ),
            align="center",
            width="100%",
        ),
        class_name="metric-card",
        flex="1",
        min_width="160px",
    )


def metrics_bar() -> rx.Component:
    """Renders the top summary KPIs bar."""
    return rx.hstack(
        metric_item("Active Assets", AppState.total_players.to_string(), "Tracked", "gray"),
        metric_item("Underperforming xG", AppState.buy_signals.to_string(), "Buy Signals", "green"),
        metric_item("Overperforming xG", AppState.sell_signals.to_string(), "Sell Signals", "red"),
        metric_item("Transfer Momentum", AppState.heating_transfers.to_string(), "Heating 🔥", "amber"),
        metric_item("Cold Outflows", AppState.cooling_transfers.to_string(), "Cooling ❄️", "blue"),
        metric_card("Active Assets", DashboardMetricsState.total_players.to_string(), "Tracked", "gray"),
        metric_card("Underperforming xG", DashboardMetricsState.buy_signals.to_string(), "Buy Signals", "green"),
        metric_card("Overperforming xG", DashboardMetricsState.sell_signals.to_string(), "Sell Signals", "red"),
        metric_card("Transfer Momentum", DashboardMetricsState.heating_transfers.to_string(), "Heating 🔥", "amber"),
        metric_card("Cold Outflows", DashboardMetricsState.cooling_transfers.to_string(), "Cooling ❄️", "blue"),
        width="100%",
        spacing="3",
        wrap="wrap",
        margin_bottom="1.5rem",
    )

