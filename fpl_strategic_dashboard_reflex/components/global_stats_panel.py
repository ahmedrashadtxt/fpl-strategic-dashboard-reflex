"""Global stats panel — hero GW points, gameweek average points, overall rank, and secondary manager metrics.
Rendered above the tab bar on every page so key numbers are always visible.
Faithfully styled after the modern FPL Optimizer design system with hardware-accelerated CSS transitions.
"""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState


def _hero_gw_card() -> rx.Component:
    """Hero card: Active GW Points with CSS transitions and hardware-accelerated themes."""
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(
                    AppState.active_gw_label,
                    class_name="hero-label",
                ),
                rx.text(
                    AppState.active_gw_display,
                    class_name="hero-pts",
                ),
                align="start",
                spacing="2",
            ),
            rx.spacer(),
            rx.box(
                rx.icon(
                    "pie-chart",
                    size=42,
                    class_name="hero-icon",
                ),
                opacity="0.85",
                padding_right="0.5rem",
            ),
            align="center",
            width="100%",
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
    )


def _avg_gw_card() -> rx.Component:
    """Secondary hero element: Gameweek Average Points + comparison delta."""
    return rx.box(
        rx.vstack(
            rx.text(
                AppState.gw_avg_label,
                font_size="0.82rem",
                font_weight="500",
                color="#94a3b8",
                letter_spacing="0.02em",
            ),
            rx.text(
                AppState.gw_avg_display,
                font_size="2.35rem",
                font_weight="800",
                color="#ffffff",
                line_height="1.1",
                font_family="'Outfit', sans-serif",
                letter_spacing="-0.02em",
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
                rx.box(),
            ),
            align="start",
            justify="center",
            spacing="1",
            height="100%",
        ),
        padding="1rem 1.25rem",
        width="100%",
        height="100%",
    )


def _rank_card() -> rx.Component:
    """Secondary hero element: Overall Rank + rank-change delta."""
    return rx.box(
        rx.vstack(
            rx.text(
                "Overall rank",
                font_size="0.82rem",
                font_weight="500",
                color="#94a3b8",
                letter_spacing="0.02em",
            ),
            rx.text(
                AppState.overall_rank_display,
                font_size="2.35rem",
                font_weight="800",
                color="#ffffff",
                line_height="1.1",
                font_family="'Outfit', sans-serif",
                letter_spacing="-0.02em",
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
                rx.box(),
            ),
            align="start",
            justify="center",
            spacing="1",
            height="100%",
        ),
        padding="1rem 1.25rem",
        width="100%",
        height="100%",
    )


def _secondary_stat(label: str, value: rx.Var | str) -> rx.Component:
    """Flat secondary stat column — label + bold value matching screenshot."""
    return rx.box(
        rx.vstack(
            rx.text(
                label,
                font_size="0.82rem",
                font_weight="500",
                color="#94a3b8",
                letter_spacing="0.01em",
            ),
            rx.text(
                value,
                font_size="1.55rem",
                font_weight="700",
                color="#ffffff",
                line_height="1.1",
                font_family="'Outfit', sans-serif",
            ),
            align="start",
            spacing="1",
        ),
        padding_y="0.35rem",
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
        rx.vstack(
            # Row A: Hero GW card + GW Average Card + Overall Rank Card
            rx.grid(
                _hero_gw_card(),
                _avg_gw_card(),
                _rank_card(),
                columns=rx.breakpoints(initial="1", md="5fr 3.5fr 3.5fr"),
                spacing="4",
                align_items="center",
                width="100%",
            ),
            # Row B: Secondary stats — Manager, Total Points, Squad Value, In the Bank
            rx.grid(
                _secondary_stat("Manager", AppState.mgr_name),
                _secondary_stat("Total points", AppState.total_points.to_string()),
                _secondary_stat("Squad value", AppState.squad_value_display),
                _secondary_stat("In the bank", AppState.bank_balance_display),
                columns=rx.breakpoints(initial="2", sm="4"),
                spacing="4",
                width="100%",
                padding_top="0.5rem",
            ),
            spacing="4",
            width="100%",
            margin_top="0.75rem",
            margin_bottom="1.75rem",
        ),
        rx.box(height="0.5rem"),
    )
