"""Main entry point and core shell for the FPL Strategic Dashboard Reflex App."""

import reflex as rx
from fpl_strategic_dashboard_reflex.state import AppState

from fpl_strategic_dashboard_reflex.states import (
    AppState,
    DashboardMetricsState,
    SquadAnalyzerState,
    TransferAnalyzerState,
    SimulatorState,
    ExpectedStatsState,
    DefensiveStatsState,
    RollingFormState,
    FixtureTickerState,
    TransferMarketState,
    AuditJournalState,
)
from fpl_strategic_dashboard_reflex.components import (
    header,
    id_dialog,
    

    expected_stats_tab,
    defensive_stats_tab,
    rolling_form_tab,
    transfer_market_tab,
    audit_journal_tab,
    metrics_bar,
)
from fpl_strategic_dashboard_reflex.pages import transfer_market_page, TransferMarketState, fixture_ticker_page, FixtureTickerState, squad_analyzer_page, SquadAnalyzerState, transfer_analyzer_page, TransferAnalyzerState, defensive_stats_page, DefensiveStatsState, expected_stats_page, ExpectedStatsState, rolling_form_page, RollingFormState, audit_journal_page, AuditJournalState
from fpl_strategic_dashboard_reflex.pages import (
    squad_analyzer_page,
    transfer_analyzer_page,
    simulator_page,
    expected_stats_page,
    defensive_stats_page,
    rolling_form_page,
    fixture_ticker_page,
    transfer_market_page,
    audit_journal_page,
)
from fpl_strategic_dashboard_reflex.styles.theme import (
    MAX_CONTENT_WIDTH,
    PAGE_PADDING_X,
    PAGE_PADDING_Y,
)


def _on_tab_change(tab: str):
    """Event sequence triggered upon tab navigation."""
    return [
        AppState.set_tab(tab),
        rx.cond(
            tab == "fixture_ticker",
            FixtureTickerState.on_tab_visible(),
            tab == "squad_analyzer",
            SquadAnalyzerState.load_squad(),
            rx.cond(
                tab == "squad_analyzer",
                SquadAnalyzerState.load_squad(),
                tab == "transfer_solver",
                TransferAnalyzerState.analyze(),
                rx.cond(
                    tab == "transfer_solver",
                    TransferAnalyzerState.analyze(),
                    tab == "match_simulator",
                    SimulatorState.run_simulation(),
                    rx.cond(
                        tab == "defensive_stats",
                        DefensiveStatsState.load_data(),
                        tab == "expected_stats",
                        ExpectedStatsState.load_data(),
                        rx.cond(
                            tab == "expected_stats",
                            ExpectedStatsState.load_data(),
                            tab == "defensive_stats",
                            DefensiveStatsState.load_data(),
                            rx.cond(
                                tab == "rolling_form",
                                RollingFormState.load_data(),
                                rx.cond(
                                    tab == "audit_journal",
                                    AuditJournalState.load_data(),
                                    tab == "fixture_ticker",
                                    FixtureTickerState.on_tab_visible(),
                                    rx.cond(
                                        tab == "transfer_market",
                                        TransferMarketState.load_data(),
                                        rx.noop()
                                    )
                                )
                            )
                        )
                    )
                )
            )
                                        rx.cond(
                                            tab == "audit_journal",
                                            AuditJournalState.load_data(),
                                            rx.noop(),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    ]


def index() -> rx.Component:
    """The main application view rendering the unified shell layout."""
    return rx.box(
        rx.container(
            header(),
            
            metrics_bar(),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("Squad Analyzer", value="squad_analyzer", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Transfer Solver", value="transfer_solver", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Match Simulator", value="match_simulator", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Expected Stats", value="expected_stats", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Defensive Contributions", value="defensive_stats", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Rolling Form", value="rolling_form", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Fixture Ticker", value="fixture_ticker", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Transfer Market", value="transfer_market", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("🤖 Journey & Social", value="audit_journal", class_name="tabs-trigger-custom"),
                    rx.tabs.trigger("Audit Journal", value="audit_journal", class_name="tabs-trigger-custom"),
                    border_bottom="1px solid var(--border-color)",
                    margin_bottom="1.5rem",
                    overflow_x="auto",
                ),
                rx.tabs.content(squad_analyzer_page(), value="squad_analyzer"),
                rx.tabs.content(transfer_analyzer_page(), value="transfer_solver"),
                rx.tabs.content(simulator_page(), value="match_simulator"),
                rx.tabs.content(expected_stats_page(), value="expected_stats"),
                rx.tabs.content(defensive_stats_page(), value="defensive_stats"),
                rx.tabs.content(rolling_form_page(), value="rolling_form"),
                # ── Live Fixture Ticker (migrated) ──────────────────────────
                rx.tabs.content(fixture_ticker_page(), value="fixture_ticker"),
                # ── Remaining placeholders ──────────────────────────────────
                rx.tabs.content(transfer_market_page(), value="transfer_market"),
                rx.tabs.content(audit_journal_page(), value="audit_journal"),
                value=AppState.selected_tab,
                on_change=_on_tab_change,
                width="100%",
            ),
            id_dialog(on_save_handler=_on_tab_change),
            max_width="1240px",
            padding_x="1rem",
            max_width=MAX_CONTENT_WIDTH,
            padding_x=PAGE_PADDING_X,
            padding_top="0.5rem",
            padding_bottom="3rem",
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
    title="FPL Optimizer · Strategic Analytics & Squad Optimizer",
    on_load=AppState.on_load,
    on_load=[
        AppState.on_load,
        DashboardMetricsState.load_metrics,
        SquadAnalyzerState.load_squad,
    ],
)
