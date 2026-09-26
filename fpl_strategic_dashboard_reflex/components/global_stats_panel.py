"""Global stats panel — hero GW points, gameweek average points, overall rank, and secondary manager metrics.
Rendered above the tab bar on every page so key numbers are always visible.
Faithfully styled after the modern FPL Optimizer design system with hardware-accelerated Motion transitions.

Phase 1 Motion features:
- Staggered fade/rise entrance (y: 8 → 0, opacity 0 → 1, 50ms stagger per card)
- CountUp numbers for GW pts, GW average, overall rank, total points, squad value, and in the bank (~800ms ease-out)
- Delta badges scale-pop in (0.9 → 1) with tight spring starting after count-up finishes (~0.8s)
"""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState
from .motion import MotionDiv
from .count_up import count_up


def _hero_gw_card(delay: float = 0.0) -> rx.Component:
    """Hero card: Active GW Points with CSS transitions and hardware-accelerated themes.
    Staggered fade/rise (y: 8 → 0, opacity 0 → 1) with CountUp number.
    Delta badge scale-pop in (0.9 → 1) starts after count-up settles (~0.8s).
    """
    return MotionDiv.create(
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
            count_up(
                value=AppState.active_gw_pts,
                suffix=" pts",
                duration=0.8,
                class_name="hero-pts",
            ),
            rx.cond(
                AppState.gw_avg_diff_str != "",
                MotionDiv.create(
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
                    initial={"opacity": 0, "scale": 0.9},
                    animate={"opacity": 1, "scale": 1},
                    transition={
                        "type": "spring",
                        "stiffness": 380,
                        "damping": 25,
                        "delay": 0.8,
                    },
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
        initial={"opacity": 0, "y": 8},
        animate={"opacity": 1, "y": 0},
        transition={
            "type": "spring",
            "stiffness": 360,
            "damping": 28,
            "delay": delay,
        },
        layout="position",
    )


def _avg_gw_card(delay: float = 0.05) -> rx.Component:
    """Primary card: Gameweek Average Points.
    Staggered fade/rise (y: 8 → 0, opacity 0 → 1) with CountUp number.
    """
    return MotionDiv.create(
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
            count_up(
                value=AppState.gw_avg_pts,
                suffix=" pts",
                duration=0.8,
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
        initial={"opacity": 0, "y": 8},
        animate={"opacity": 1, "y": 0},
        transition={
            "type": "spring",
            "stiffness": 360,
            "damping": 28,
            "delay": delay,
        },
        layout="position",
    )


def _rank_card(delay: float = 0.10) -> rx.Component:
    """Primary card: Overall Rank + rank delta badge.
    Staggered fade/rise (y: 8 → 0, opacity 0 → 1) with CountUp number.
    Delta badge scale-pop in (0.9 → 1) starts after count-up settles (~0.85s).
    """
    return MotionDiv.create(
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
            count_up(
                value=AppState.overall_rank,
                use_group=True,
                duration=0.8,
                class_name="metric-value",
            ),
            rx.cond(
                AppState.rank_delta != "",
                MotionDiv.create(
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
                    initial={"opacity": 0, "scale": 0.9},
                    animate={"opacity": 1, "scale": 1},
                    transition={
                        "type": "spring",
                        "stiffness": 380,
                        "damping": 25,
                        "delay": 0.85,
                    },
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
        initial={"opacity": 0, "y": 8},
        animate={"opacity": 1, "y": 0},
        transition={
            "type": "spring",
            "stiffness": 360,
            "damping": 28,
            "delay": delay,
        },
        layout="position",
    )


def _secondary_stat(
    icon_name: str,
    label: str,
    value: rx.Component | rx.Var | str,
    delay: float = 0.0,
) -> rx.Component:
    """Styled secondary portfolio metric card with icon, label, and clean value typography.
    Staggered fade/rise: y: 8 → 0, opacity: 0 → 1.
    """
    val_component = (
        value if isinstance(value, rx.Component)
        else rx.text(value, class_name="secondary-stat-value")
    )
    return MotionDiv.create(
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
            val_component,
            align="start",
            spacing="1",
            justify="center",
            width="100%",
        ),
        class_name="secondary-stat-card",
        width="100%",
        initial={"opacity": 0, "y": 8},
        animate={"opacity": 1, "y": 0},
        transition={
            "type": "spring",
            "stiffness": 360,
            "damping": 28,
            "delay": delay,
        },
        layout="position",
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
                # Row 1: Hero GW card + GW Average Card + Overall Rank Card (stagger delays: 0.0s, 0.05s, 0.10s)
                rx.grid(
                    _hero_gw_card(delay=0.00),
                    _avg_gw_card(delay=0.05),
                    _rank_card(delay=0.10),
                    columns=rx.breakpoints(initial="1", md="3"),
                    spacing="3",
                    align_items="stretch",
                    width="100%",
                ),
                # Row 2: Secondary portfolio stats (stagger delays: 0.15s, 0.20s, 0.25s, 0.30s)
                rx.grid(
                    _secondary_stat("user", "Manager", AppState.display_title, delay=0.15),
                    _secondary_stat(
                        "award",
                        "Total points",
                        count_up(value=AppState.total_points, duration=0.8, class_name="secondary-stat-value"),
                        delay=0.20,
                    ),
                    _secondary_stat(
                        "trending-up",
                        "Squad value",
                        count_up(value=AppState.squad_value, prefix="£", suffix="m", decimals=2, duration=0.8, class_name="secondary-stat-value"),
                        delay=0.25,
                    ),
                    _secondary_stat(
                        "wallet",
                        "In the bank",
                        count_up(value=AppState.bank_balance, prefix="£", suffix="m", decimals=1, duration=0.8, class_name="secondary-stat-value"),
                        delay=0.30,
                    ),
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
