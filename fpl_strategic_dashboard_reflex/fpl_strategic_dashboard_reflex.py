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
    MotionConfig,
    MotionDiv,
    AnimatePresence,
    tour_driver,
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


def _main_tab_trigger(label: str, value: str) -> rx.Component:
    """Renders a main navigation tab trigger with a single shared sliding indicator."""
    return rx.tabs.trigger(
        rx.cond(
            AppState.selected_tab == value,
            MotionDiv.create(
                class_name="main-tab-active-indicator",
                layout_id="main-tab-indicator",
                transition={"type": "spring", "stiffness": 380, "damping": 30},
            ),
        ),
        rx.text(label, class_name="tab-trigger-label"),
        value=value,
        class_name="tabs-trigger-custom",
    )


def index() -> rx.Component:
    """The main application view rendering the unified shell layout."""
    return MotionConfig.create(
        rx.box(
            rx.container(
                header(),
                global_stats_panel(),
                rx.tabs.root(
                    rx.tabs.list(
                        _main_tab_trigger("Squad Analyzer", "squad_analyzer"),
                        _main_tab_trigger("Transfer Solver", "transfer_solver"),
                        _main_tab_trigger("Match Simulator", "match_simulator"),
                        _main_tab_trigger("Expected Stats", "expected_stats"),
                        _main_tab_trigger("Defensive Stats", "defensive_stats"),
                        _main_tab_trigger("Rolling Form", "rolling_form"),
                        _main_tab_trigger("Fixture Ticker", "fixture_ticker"),
                        _main_tab_trigger("Transfer Market", "transfer_market"),
                        class_name="main-nav-tabs-list",
                        id="tour-main-tabs",
                        custom_attrs={"data-tour-id": "tour-main-tabs"},
                    ),
                    AnimatePresence.create(
                        MotionDiv.create(
                            rx.match(
                                AppState.selected_tab,
                                ("squad_analyzer", squad_analyzer_page()),
                                ("transfer_solver", transfer_analyzer_page()),
                                ("match_simulator", simulator_page()),
                                ("expected_stats", expected_stats_page()),
                                ("defensive_stats", defensive_stats_page()),
                                ("rolling_form", rolling_form_page()),
                                ("fixture_ticker", fixture_ticker_page()),
                                ("transfer_market", transfer_market_page()),
                                squad_analyzer_page(),
                            ),
                            key=AppState.selected_tab,
                            initial={"opacity": 0, "y": 8},
                            animate={"opacity": 1, "y": 0},
                            exit={"opacity": 0, "y": -8},
                            transition={"duration": 0.18, "ease": [0.16, 1, 0.3, 1]},
                            width="100%",
                        ),
                        mode="wait",
                    ),
                    value=AppState.selected_tab,
                    on_change=AppState.set_tab,
                    width="100%",
                ),
                id_dialog(),
                tour_driver(),
                max_width="1600px",
                padding_x="2rem",
                padding_top="0.5rem",
                padding_bottom=PAGE_PADDING_Y,
            ),
            min_height="100vh",
            background="var(--app-bg)",
            width="100%",
        ),
        reduced_motion="user",
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
