"""Match Simulator Page - Monte Carlo match simulation and Head-to-Head stress-testing."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.simulator import SimulatorState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    data_table,
)


def simulator_page() -> rx.Component:
    """Renders the Monte Carlo Gameweek Simulator page view."""
    return rx.box(
        # Page Title & Guide
        rx.hstack(
            rx.vstack(
                rx.text("Monte Carlo Gameweek Simulator", class_name="section-header-title"),
                rx.text("Stress-test your squad across thousands of probabilistic match outcomes based on bookmaker odds.", class_name="section-header-sub"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            guide_popover(
                title="Monte Carlo Simulator Guide",
                subtitle="Probabilistic outcome modelling and variance testing",
                items=[
                    {"badge": "Iterations", "title": "5,000+ Simulations", "desc": "Runs thousands of match simulations using Poisson goal arrival processes."},
                    {"badge": "Floor vs Ceiling", "title": "Risk Quantiles", "desc": "Assess 10th percentile floor safety when protecting rank, and 90th percentile ceiling when chasing."},
                    {"badge": "H2H Mode", "title": "Opponent Benchmark", "desc": "Benchmark your team head-to-head against the Budget Dream 15 to compute win probability."},
                ],
                tip="A high haul probability (>25%) indicates strong upside potential for captaincy candidates.",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),

        # KPI Metrics Cards (Simulation Percentiles)
        rx.cond(
            SimulatorState.has_results,
            rx.hstack(
                metric_card("Expected Mean", SimulatorState.sim_mean.to_string(), "Average", "blue"),
                metric_card("10th Percentile Floor", SimulatorState.sim_p10.to_string(), "Safety Floor", "amber"),
                metric_card("Median Expectation", SimulatorState.sim_median.to_string(), "50th %ile", "green"),
                metric_card("90th Percentile Ceiling", SimulatorState.sim_p90.to_string(), "Boom Ceiling", "purple"),
                metric_card("Variance (Std Dev)", rx.concat("±", SimulatorState.sim_std.to_string()), "Volatility", "gray"),
                width="100%",
                spacing="3",
                wrap="wrap",
                margin_bottom="1.25rem",
            ),
            rx.box(),
        ),

        # Controls Bar
        rx.box(
            rx.hstack(
                # Gameweek Select
                rx.hstack(
                    rx.text("Simulate GW:", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.select(
                        [str(gw) for gw in range(1, 39)],
                        value=SimulatorState.target_sim_gw,
                        on_change=SimulatorState.set_target_gw,
                        size="2",
                        variant="surface",
                    ),
                    align="center",
                    spacing="2",
                ),

                # Squad Source Segmented Control
                rx.hstack(
                    rx.button(
                        "Active Squad",
                        variant=rx.cond(SimulatorState.squad_mode == "active", "solid", "surface"),
                        color_scheme="blue",
                        size="2",
                        on_click=lambda: SimulatorState.set_squad_mode("active"),
                    ),
                    rx.button(
                        "Budget Dream 15",
                        variant=rx.cond(SimulatorState.squad_mode == "dream15", "solid", "surface"),
                        color_scheme="purple",
                        size="2",
                        on_click=lambda: SimulatorState.set_squad_mode("dream15"),
                    ),
                    align="center",
                    spacing="2",
                ),

                # Iterations
                rx.hstack(
                    rx.text("Iterations: 5,000", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    align="center",
                ),

                rx.spacer(),

                # Action Buttons
                rx.hstack(
                    rx.button(
                        rx.cond(SimulatorState.h2h_enabled, "Disable H2H", "Benchmark H2H"),
                        variant=rx.cond(SimulatorState.h2h_enabled, "solid", "surface"),
                        color_scheme="cyan",
                        size="2",
                        on_click=SimulatorState.toggle_h2h,
                    ),
                    rx.button(
                        rx.icon("play", size=16),
                        "Run Simulation",
                        variant="solid",
                        color_scheme="blue",
                        size="2",
                        on_click=SimulatorState.run_simulation,
                    ),
                    align="center",
                    spacing="2",
                ),

                width="100%",
                align="center",
                wrap="wrap",
                gap="1rem",
            ),
            padding="1rem",
            background="rgba(255, 255, 255, 0.02)",
            border="1px solid var(--border-color)",
            border_radius="10px",
            margin_bottom="1.5rem",
            width="100%",
        ),

        # Head-to-Head Results Banner (if enabled)
        rx.cond(
            SimulatorState.h2h_enabled,
            rx.box(
                rx.vstack(
                    rx.text("Head-to-Head Benchmark vs Dream 15:", font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                    rx.hstack(
                        metric_card("Your Win Rate", rx.concat(SimulatorState.h2h_win_pct_a.to_string(), "%"), "Outperform", "green"),
                        metric_card("Draw Probability", rx.concat(SimulatorState.h2h_draw_pct.to_string(), "%"), "Tie", "gray"),
                        metric_card("Opponent Win Rate", rx.concat(SimulatorState.h2h_win_pct_b.to_string(), "%"), "Dream 15", "red"),
                        metric_card("Your Median", SimulatorState.h2h_median_a.to_string(), "You", "blue"),
                        metric_card("Opponent Median", SimulatorState.h2h_median_b.to_string(), "Benchmark", "purple"),
                        width="100%",
                        spacing="3",
                        wrap="wrap",
                    ),
                    align="start",
                    spacing="2",
                ),
                padding="1rem",
                border_radius="10px",
                background="rgba(34, 197, 94, 0.06)",
                border="1px solid rgba(34, 197, 94, 0.2)",
                margin_bottom="1.5rem",
                width="100%",
            ),
            rx.box(),
        ),

        # Main Content: Loading vs Player Distributions Table
        rx.cond(
            SimulatorState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text(SimulatorState.status_message, font_size="0.85rem", color="var(--text-sub)"),
                    align="center",
                    spacing="2",
                ),
                padding="4rem",
                width="100%",
            ),
            rx.cond(
                SimulatorState.has_results,
                rx.box(
                    rx.text("Player Distribution Analysis", font_weight="700", font_size="1rem", margin_bottom="0.75rem"),
                    data_table(
                        headers=["Player", "Club", "Pos", "Projected xP", "Simulated Median", "Haul Probability (≥10 pts)"],
                        rows=SimulatorState.player_stats,
                        row_render_func=lambda row: rx.table.row(
                            rx.table.cell(rx.text(row["web_name"], font_weight="600")),
                            rx.table.cell(rx.badge(row["team"], variant="surface", color_scheme="gray", size="1")),
                            rx.table.cell(rx.text(row["pos"], font_size="0.8rem")),
                            rx.table.cell(rx.text(row["proj_pts"], font_weight="700", color="#60a5fa")),
                            rx.table.cell(rx.text(row["median"], font_weight="600")),
                            rx.table.cell(
                                rx.cond(
                                    row["haul_prob"].to(float) >= 20.0,
                                    rx.badge(rx.concat(row["haul_prob"], "%"), variant="soft", color_scheme="green", size="1"),
                                    rx.badge(rx.concat(row["haul_prob"], "%"), variant="surface", color_scheme="gray", size="1"),
                                )
                            ),
                        ),
                        is_loading=SimulatorState.is_loading,
                    ),
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("activity", size=32, color="var(--text-muted)"),
                        rx.text("Select a gameweek and click 'Run Simulation' to model outcomes.", font_size="0.9rem", color="var(--text-sub)"),
                        rx.button("Run Simulation Now", on_click=SimulatorState.run_simulation, variant="solid", color_scheme="blue", size="2"),
                        align="center",
                        spacing="3",
                    ),
                    padding="4rem",
                    width="100%",
                ),
            ),
        ),
        width="100%",
    )
