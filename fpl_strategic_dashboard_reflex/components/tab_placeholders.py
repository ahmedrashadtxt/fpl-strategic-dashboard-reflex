"""Placeholder views for each tab in the FPL Strategic Dashboard."""

import reflex as rx
from fpl_strategic_dashboard_reflex.state import AppState


def section_header(title: str, description: str = "") -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(title, font_family="'Outfit', sans-serif", font_weight="700", font_size="1.2rem", color="var(--text-main)"),
            rx.cond(
                description != "",
                rx.text(description, font_size="0.82rem", color="var(--text-sub)", font_weight="500"),
                rx.box(),
            ),
            spacing="1",
            align="start",
        ),
        class_name="section-card",
    )


def placeholder_card(icon: str, title: str, description: str, tab_id: str) -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.text(icon, font_size="2rem"),
            class_name="placeholder-icon",
        ),
        rx.text(title, class_name="placeholder-title"),
        rx.text(description, class_name="placeholder-desc"),
        rx.hstack(
            rx.badge("Reflex Shell Ready", variant="surface", color_scheme="green", radius="full"),
            rx.badge(f"Gameweek: {AppState.selected_gw}", variant="surface", color_scheme="blue", radius="full"),
            rx.cond(
                AppState.manager_id != "",
                rx.badge(f"Team ID: #{AppState.manager_id}", variant="surface", color_scheme="purple", radius="full"),
                rx.badge("No Team Connected", variant="surface", color_scheme="gray", radius="full"),
            ),
            spacing="2",
            wrap="wrap",
            justify="center",
        ),
        rx.text(
            "Backend logic and SQLite connection initialized. UI migration will be hooked in the next phase.",
            font_size="0.78rem",
            color="var(--text-meta)",
            font_style="italic",
        ),
        class_name="placeholder-card",
        width="100%",
        spacing="3",
    )


# ── Tab Placeholders ──────────────────────────────────────────────────────────

def squad_analyzer_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Squad Analyzer & Lineup Optimizer",
            "Deep-dive performance projections, interactive pitch view, and automated optimal XI solver.",
        ),
        placeholder_card(
            "⚽",
            "Squad Analyzer",
            "Evaluate your 15-man squad against upcoming fixtures. Calculate probabilistic projected points (xP) and solve for your starting XI and bench order.",
            "squad_analyzer",
        ),
        width="100%",
        spacing="4",
    )


def transfer_solver_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Transfer Solver & Horizon Optimizer",
            "Simulate free transfers, target transfers, and multi-gameweek chip strategies.",
        ),
        placeholder_card(
            "🔄",
            "Transfer Solver",
            "Multi-GW heuristic solver finding the highest-gain moves within your budget, accounting for chip horizons and price movements.",
            "transfer_solver",
        ),
        width="100%",
        spacing="4",
    )


def expected_stats_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Expected Attacking Stats",
            "Underlying xG, xA, and xGI metrics to reveal clinical finishers vs unsustainable overperformers.",
        ),
        placeholder_card(
            "📊",
            "Expected Stats (xG / xA)",
            "Detailed breakdown of expected goals and expected assists across all Premier League players with position and price filters.",
            "expected_stats",
        ),
        width="100%",
        spacing="4",
    )


def defensive_stats_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Defensive Contributions",
            "Team and individual defensive solidity, expected goals conceded (xGC), and clean sheet rates.",
        ),
        placeholder_card(
            "🛡️",
            "Defensive Contributions",
            "Analysis of defensive assets, clean sheet potential, expected goals conceded, and value goalkeepers.",
            "defensive_stats",
        ),
        width="100%",
        spacing="4",
    )


def rolling_form_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Rolling Form & Momentum",
            "Windowed rolling averages (L3, L5, L8) to spot form shifts ahead of the template.",
        ),
        placeholder_card(
            "📈",
            "Rolling Form Analyzer",
            "Calculates rolling window metrics from player match histories to highlight emerging value and dipping assets.",
            "rolling_form",
        ),
        width="100%",
        spacing="4",
    )


def fixture_ticker_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Fixture Difficulty Ticker (FDR)",
            "Official FDR schedules across upcoming gameweeks ranked by difficulty and run quality.",
        ),
        placeholder_card(
            "🗓️",
            "Fixture Ticker",
            "Upcoming schedule matrix for all 20 Premier League clubs, highlighting green fixture swings and blank/double gameweeks.",
            "fixture_ticker",
        ),
        width="100%",
        spacing="4",
    )


def transfer_market_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "Transfer Market & Price Predictor",
            "Live net transfer velocity, ownership changes, and nightly price rise/fall probability estimates.",
        ),
        placeholder_card(
            "💹",
            "Transfer Market & Price Rises",
            "Predicts nightly price rises (🚀) and falls (⚠️) based on ownership volume thresholds, flags, and net transfers.",
            "transfer_market",
        ),
        width="100%",
        spacing="4",
    )


def audit_journal_tab() -> rx.Component:
    return rx.vstack(
        section_header(
            "🤖 Journey, Audit Journal & Community",
            "Track historical model predictions vs actual match outcomes and review your gameweek decisions.",
        ),
        placeholder_card(
            "🤖",
            "Audit Journal & Social",
            "Log pre-gameweek snapshots, compare actual points against xP predictions, and calculate model variance.",
            "audit_journal",
        ),
        width="100%",
        spacing="4",
    )

