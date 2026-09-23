"""Global stats panel — hero GW points, gameweek average points, overall rank, and secondary manager metrics.
Rendered above the tab bar on every page so key numbers are always visible.
Faithfully styled after the modern FPL Optimizer design system with hardware-accelerated CSS transitions.
"""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState
from .motion import MotionDiv


def _hero_gw_card() -> rx.Component:
    """Hero card: Active GW Points with CSS transitions and hardware-accelerated themes."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(
                    AppState.active_gw_label,
                    class_name="hero-label",
                ),
                rx.spacer(),
                rx.icon(
                    "pie-chart",
                    size=20,
                    class_name="hero-icon",
                    opacity="0.85",
                ),
                align="center",
                width="100%",
            ),
            rx.text(
                AppState.active_gw_display,
                class_name="hero-pts",
            ),
            rx.cond(
                AppState.gw_avg_diff_str != "",
                rx.text(
                    AppState.gw_avg_diff_str,
                    class_name=rx.cond(
                        AppState.hero_perf_status == "green",
                        "rank-delta-badge-green",
                        rx.cond(
                            AppState.hero_perf_status == "red",
                            "rank-delta-badge-red",
                            "rank-delta-badge-gray",
                        ),
                    ),
                ),
                rx.text(
                    "Gameweek Score",
                    class_name="rank-delta-badge-gray",
                ),
            ),
            align="start",
            justify="between",
            spacing="2",
            height="100%",
        ),
        class_name=rx.cond(
            AppState.hero_perf_status == "green",
            "hero-gw-card hero-card-perf-green",
            rx.cond(
                AppState.hero_perf_status == "red",
                "hero-gw-card hero-card-perf-red",
                "hero-gw-card hero-card-perf-gray",
            ),
        ),
        width="100%",
        height="100%",
    )


def _avg_gw_card() -> rx.Component:
    """Primary card: Gameweek Average Points."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(
                    AppState.gw_avg_label,
                    class_name="metric-label",
                ),
                rx.spacer(),
                rx.icon(
                    "users",
                    size=20,
                    class_name="metric-icon",
                    opacity="0.85",
                ),
                align="center",
                width="100%",
            ),
            rx.text(
                AppState.gw_avg_display,
                class_name="metric-value",
            ),
            rx.text(
                "League Average",
                class_name="rank-delta-badge-gray",
            ),
            align="start",
            justify="between",
            spacing="2",
            height="100%",
        ),
        class_name="top-metric-card",
        width="100%",
        height="100%",
    )


def _rank_card() -> rx.Component:
    """Primary card: Overall Rank + rank delta badge."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.text(
                    "Overall rank",
                    class_name="metric-label",
                ),
                rx.spacer(),
                rx.icon(
                    "trophy",
                    size=20,
                    class_name="metric-icon",
                    opacity="0.85",
                ),
                align="center",
                width="100%",
            ),
            rx.text(
                AppState.overall_rank_display,
                class_name="metric-value",
            ),
            rx.cond(
                AppState.rank_delta != "",
                rx.text(
                    AppState.rank_delta,
                    class_name=rx.cond(
                        AppState.rank_delta_color == "green",
                        "rank-delta-badge-green",
                        rx.cond(
                            AppState.rank_delta_color == "red",
                            "rank-delta-badge-red",
                            "rank-delta-badge-gray",
                        ),
                    ),
                ),
                rx.text(
                    "Global Standing",
                    class_name="rank-delta-badge-gray",
                ),
            ),
            align="start",
            justify="between",
            spacing="2",
            height="100%",
        ),
        class_name="top-metric-card",
        width="100%",
        height="100%",
    )


def _secondary_stat(icon_name: str, label: str, value: rx.Var | str) -> rx.Component:
    """Styled secondary portfolio metric card with icon, label, and clean value typography."""
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.icon(
                    icon_name,
                    size=15,
                    class_name="secondary-stat-icon",
                ),
                rx.text(
                    label,
                    class_name="secondary-stat-label",
                ),
                align="center",
                spacing="2",
            ),
            rx.text(
                value,
                class_name="secondary-stat-value",
            ),
            align="start",
            spacing="1",
            justify="center",
            width="100%",
        ),
        class_name="secondary-stat-card",
        width="100%",
    )


def global_stats_panel() -> rx.Component:
    """
    Global stats panel rendered above the tab bar on every page.
    Shows hero GW points (color coded vs average), GW average points, overall rank,
    and secondary manager metrics.
    Hidden until squad data is loaded.
    """
    return rx.cond(
        AppState.has_data,
        MotionDiv.create(
            rx.vstack(
                # Row 1: Hero GW card + GW Average Card + Overall Rank Card (1fr 1fr 1fr)
                rx.grid(
                    _hero_gw_card(),
                    _avg_gw_card(),
                    _rank_card(),
                    columns=rx.breakpoints(initial="1", md="3"),
                    spacing="3",
                    align_items="stretch",
                    width="100%",
                ),
                # Row 2: Secondary portfolio stats — Manager, Total Points, Squad Value, In the Bank
                rx.grid(
                    _secondary_stat("user", "Manager", AppState.display_title),
                    _secondary_stat("award", "Total points", AppState.total_points.to_string()),
                    _secondary_stat("trending-up", "Squad value", AppState.squad_value_display),
                    _secondary_stat("wallet", "In the bank", AppState.bank_balance_display),
                    columns=rx.breakpoints(initial="2", sm="4"),
                    spacing="3",
                    width="100%",
                ),
                spacing="3",
                width="100%",
                margin_top="0.75rem",
                margin_bottom="1.5rem",
            ),
            layout="position",
            initial={"opacity": 0, "y": -6},
            animate={"opacity": 1, "y": 0},
            transition={"duration": 0.3, "ease": [0.16, 1, 0.3, 1]},
            width="100%",
        ),
        rx.box(height="0.5rem"),
    )
