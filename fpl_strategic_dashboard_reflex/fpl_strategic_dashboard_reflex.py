"""Main entry point and core shell for the FPL Strategic Dashboard Reflex App."""

import reflex as rx

from fpl_strategic_dashboard_reflex.states import (
    AppState,
    SquadAnalyzerState,
    TransferAnalyzerState,
    SimulatorState,
    ExpectedStatsState,
    DefensiveStatsState,
    RollingFormState,
    FixtureTickerState,
    TransferMarketState,
)
from fpl_strategic_dashboard_reflex.components import (
    header,
    global_stats_panel,
    id_dialog,
    motion_tab_content,
)
from fpl_strategic_dashboard_reflex.pages import (
    squad_analyzer_page,
    transfer_analyzer_page,
    simulator_page,
    expected_stats_page,
    defensive_stats_page,
    rolling_form_page,
    fixture_ticker_page,
    transfer_market_page,
)
from fpl_strategic_dashboard_reflex.styles.theme import (
    PAGE_PADDING_Y,
)


def index() -> rx.Component:
    """The main application view rendering the unified shell layout."""
    return rx.box(
        rx.container(
            header(),
            global_stats_panel(),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Squad Analyzer", value="squad_analyzer", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Transfer Solver", value="transfer_solver", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Match Simulator", value="match_simulator", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Expected Stats", value="expected_stats", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Defensive Stats", value="defensive_stats", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Rolling Form", value="rolling_form", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Fixture Ticker", value="fixture_ticker", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Transfer Market", value="transfer_market", class_name="tabs-trigger-custom"),
                    class_name="main-nav-tabs-list",
                ),
                rx.tabs.content(motion_tab_content(squad_analyzer_page()), value="squad_analyzer"),
                rx.tabs.content(motion_tab_content(transfer_analyzer_page()), value="transfer_solver"),
                rx.tabs.content(motion_tab_content(simulator_page()), value="match_simulator"),
                rx.tabs.content(motion_tab_content(expected_stats_page()), value="expected_stats"),
                rx.tabs.content(motion_tab_content(defensive_stats_page()), value="defensive_stats"),
                rx.tabs.content(motion_tab_content(rolling_form_page()), value="rolling_form"),
                # ── Live Fixture Ticker (migrated) ──────────────────────────
                rx.tabs.content(motion_tab_content(fixture_ticker_page()), value="fixture_ticker"),
                # ── Transfer Market ─────────────────────────────────────────
                rx.tabs.content(motion_tab_content(transfer_market_page()), value="transfer_market"),
                value=AppState.selected_tab,
                on_change=AppState.set_tab,
                width="100%",
            ),
            id_dialog(),
            max_width="1600px",
            padding_x="2rem",
            padding_top="0.5rem",
            padding_bottom=PAGE_PADDING_Y,
        ),
        min_height="100vh",
        background="var(--app-bg)",
        width="100%",
    )


app = rx.App(
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700;800&display=swap",
        "/custom.css",
    ],
)

app.add_page(
    index,
    title="fpl optimizer · Strategic Analytics & Squad Optimizer",
    on_load=[
        AppState.on_load,
        SquadAnalyzerState.load_squad,
    ],
)
