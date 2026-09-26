"""Match Simulator Page - Monte Carlo match simulation, Head-to-Head stress-testing, and Custom 15-Player Sandbox."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.simulator import SimulatorState
from fpl_strategic_dashboard_reflex.components import tour_button, loading_view, MotionDiv
from fpl_strategic_dashboard_reflex.styles.theme import (
    CARD_STYLE,
    FILTER_BAR_STYLE,
    METRIC_CARD_STYLE,
    TABLE_CONTAINER_STYLE,
    fdr_badge_style,
)
from fpl_strategic_dashboard_reflex.styles.constants import FDR_PALETTE


def _position_badge(pos: str) -> rx.Component:
    color_map = {
        "GKP": "amber",
        "DEF": "blue",
        "MID": "green",
        "FWD": "red",
    }
    return rx.badge(pos, variant="surface", color_scheme=color_map.get(pos, "gray"), size="1")


def _fdr_badge(fdr_var) -> rx.Component:
    """Renders a styled FDR difficulty badge using FDR_PALETTE color tokens."""
    d = fdr_var.to(int)
    return rx.cond(
        d <= 2,
        rx.badge(
            d.to_string(),
            variant="surface",
            size="1",
            style={
                "background": FDR_PALETTE[2]["bg"],
                "color": FDR_PALETTE[2]["color"],
                "fontWeight": "700",
                "padding": "0.15rem 0.5rem",
                "borderRadius": "6px",
                "minWidth": "28px",
                "justifyContent": "center",
                "textAlign": "center",
            },
        ),
        rx.cond(
            d == 3,
            rx.badge(
                d.to_string(),
                variant="surface",
                size="1",
                style={
                    "background": FDR_PALETTE[3]["bg"],
                    "color": FDR_PALETTE[3]["color"],
                    "fontWeight": "600",
                    "padding": "0.15rem 0.5rem",
                    "borderRadius": "6px",
                    "minWidth": "28px",
                    "justifyContent": "center",
                    "textAlign": "center",
                },
            ),
            rx.cond(
                d == 4,
                rx.badge(
                    d.to_string(),
                    variant="surface",
                    size="1",
                    style={
                        "background": FDR_PALETTE[4]["bg"],
                        "color": FDR_PALETTE[4]["color"],
                        "fontWeight": "700",
                        "padding": "0.15rem 0.5rem",
                        "borderRadius": "6px",
                        "minWidth": "28px",
                        "justifyContent": "center",
                        "textAlign": "center",
                    },
                ),
                rx.badge(
                    d.to_string(),
                    variant="surface",
                    size="1",
                    style={
                        "background": FDR_PALETTE[5]["bg"],
                        "color": FDR_PALETTE[5]["color"],
                        "fontWeight": "800",
                        "padding": "0.15rem 0.5rem",
                        "borderRadius": "6px",
                        "minWidth": "28px",
                        "justifyContent": "center",
                        "textAlign": "center",
                    },
                ),
            ),
        ),
    )


def _starting_xi_table() -> rx.Component:
    """Renders the Optimal Starting XI in an elegant table format matching the reference."""
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Player", style={"textAlign": "left", "paddingLeft": "1rem"}),
                    rx.table.column_header_cell("Pos", style={"textAlign": "center"}),
                    rx.table.column_header_cell("Club", style={"textAlign": "center"}),
                    rx.table.column_header_cell("Proj xP", style={"textAlign": "center"}),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    SimulatorState.starting_xi,
                    lambda row: rx.table.row(
                        rx.table.cell(
                            rx.hstack(
                                rx.image(
                                    src=row["photo"],
                                    width="28px",
                                    height="28px",
                                    border_radius="50%",
                                    object_fit="cover",
                                    fallback="https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp",
                                ),
                                rx.text(row["Player"], font_weight="600", font_size="0.85rem"),
                                rx.cond(
                                    row["is_captain"],
                                    rx.badge("(C)", variant="solid", color_scheme="amber", size="1"),
                                    rx.cond(
                                        row["is_vc"],
                                        rx.badge("(VC)", variant="surface", color_scheme="gray", size="1"),
                                        rx.box(),
                                    ),
                                ),
                                align="center",
                                spacing="2",
                            ),
                            style={"textAlign": "left", "paddingLeft": "1rem"},
                        ),
                        rx.table.cell(_position_badge(row["Pos"]), style={"textAlign": "center"}),
                        rx.table.cell(rx.text(row["Club"], font_size="0.85rem"), style={"textAlign": "center"}),
                        rx.table.cell(
                            rx.badge(
                                row["Proj_Pts"],
                                variant="soft",
                                color_scheme="green",
                                size="1",
                                font_weight="700",
                            ),
                            style={"textAlign": "center"},
                        ),
                    ),
                ),
            ),
            variant="surface",
            size="1",
            width="100%",
        ),
        style=TABLE_CONTAINER_STYLE,
    )


def simulator_page() -> rx.Component:
    """Renders the Monte Carlo Gameweek Simulator page view."""
    return rx.box(
        # Page Title & Guide Header
        rx.hstack(
            rx.hstack(
                rx.box(
                    width="4px",
                    height="32px",
                    background="var(--accent-9)",
                    border_radius="2px",
                    margin_right="0.5rem",
                ),
                rx.vstack(
                    rx.text("Monte Carlo Gameweek Simulator", class_name="section-header-title"),
                    rx.text(
                        "Stress-test your squad across thousands of probabilistic match outcomes.",
                        class_name="section-header-sub",
                    ),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.spacer(),
            rx.hstack(
                tour_button("match_simulator"),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=SimulatorState.refresh_simulation,
                    variant="outline",
                    size="2",
                    color_scheme="gray",
                ),
                align="center",
                spacing="2",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),

        # Target Gameweek Section
        rx.vstack(
            rx.text("Target Gameweek", font_weight="700", font_size="0.95rem", color="var(--text-main)"),
            rx.select(
                SimulatorState.available_sim_gws,
                value=rx.cond(
                    SimulatorState.target_sim_gw != "",
                    SimulatorState.target_sim_gw,
                    SimulatorState.current_gw.to_string(),
                ),
                on_change=SimulatorState.set_target_gw,
                size="2",
                variant="surface",
                width="100%",
            ),
            align="start",
            spacing="1",
            margin_bottom="1.25rem",
            width="100%",
            id="tour-sim-gw",
            custom_attrs={"data-tour-id": "tour-sim-gw"},
        ),

        # Squad Source Section (4 buttons matching reference layout)
        rx.vstack(
            rx.text("Squad Source", font_weight="700", font_size="0.95rem", color="var(--text-main)"),
            rx.grid(
                rx.button(
                    rx.hstack(
                        rx.icon("user", size=14),
                        rx.text("My Active Squad", font_weight="600"),
                        align="center",
                        spacing="2",
                    ),
                    variant=rx.cond(SimulatorState.is_active_mode, "solid", "surface"),
                    color_scheme=rx.cond(SimulatorState.is_active_mode, "amber", "gray"),
                    size="2",
                    width="100%",
                    on_click=lambda: SimulatorState.set_squad_mode("active"),
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("arrow-left-right", size=14),
                        rx.text("Post-Transfer Plan", font_weight="600"),
                        align="center",
                        spacing="2",
                    ),
                    variant=rx.cond(SimulatorState.is_transfer_plan_mode, "solid", "surface"),
                    color_scheme=rx.cond(SimulatorState.is_transfer_plan_mode, "cyan", "gray"),
                    size="2",
                    width="100%",
                    on_click=lambda: SimulatorState.set_squad_mode("transfer_plan"),
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("star", size=14),
                        rx.text("Budget Dream 15", font_weight="600"),
                        align="center",
                        spacing="2",
                    ),
                    variant=rx.cond(SimulatorState.is_dream15_mode, "solid", "surface"),
                    color_scheme=rx.cond(SimulatorState.is_dream15_mode, "purple", "gray"),
                    size="2",
                    width="100%",
                    on_click=lambda: SimulatorState.set_squad_mode("dream15"),
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("wrench", size=14),
                        rx.text("Custom Sandbox", font_weight="600", white_space="nowrap"),
                        align="center",
                        spacing="2",
                    ),
                    variant=rx.cond(SimulatorState.is_sandbox_mode, "solid", "surface"),
                    color_scheme=rx.cond(SimulatorState.is_sandbox_mode, "amber", "gray"),
                    size="2",
                    width="100%",
                    on_click=lambda: SimulatorState.set_squad_mode("sandbox"),
                ),
                columns=rx.breakpoints(initial="1", sm="2", md="4"),
                spacing="2",
                width="100%",
            ),
            align="start",
            spacing="2",
            margin_bottom="1.5rem",
            width="100%",
            id="tour-sim-squad",
            custom_attrs={"data-tour-id": "tour-sim-squad"},
        ),

        # Notice when in Post-Transfer Plan mode without a transfer plan
        rx.cond(
            SimulatorState.is_transfer_plan_mode & (~SimulatorState.has_transfer_plan),
            rx.box(
                rx.hstack(
                    rx.icon("info", size=20, color="#38bdf8"),
                    rx.vstack(
                        rx.text("No active transfer plan found in session state.", font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                        rx.text("Please visit the Transfer Solver to solve transfers first, then return here to simulate.", font_size="0.8rem", color="var(--text-sub)"),
                        align="start",
                        spacing="1",
                    ),
                    rx.spacer(),
                    rx.button(
                        "Go to Transfer Solver",
                        variant="solid",
                        color_scheme="blue",
                        size="2",
                        on_click=SimulatorState.go_to_transfer_solver,
                    ),
                    width="100%",
                    align="center",
                ),
                padding="1rem",
                border_radius="10px",
                background="rgba(56, 189, 248, 0.08)",
                border="1px solid rgba(56, 189, 248, 0.25)",
                margin_bottom="1.5rem",
                width="100%",
            ),
            rx.box(),
        ),

        # Custom Sandbox Wildcard Builder (visible when in sandbox mode)
        rx.cond(
            SimulatorState.is_sandbox_mode,
            MotionDiv.create(
                rx.box(
                    rx.vstack(
                    rx.hstack(
                        rx.vstack(
                            rx.hstack(
                                rx.icon("wrench", size=18, color="#f59e0b"),
                                rx.text("Custom 15-Player Sandbox Builder", font_weight="700", font_size="1rem", color="var(--text-main)"),
                                align="center",
                                spacing="2",
                            ),
                            rx.text("Select 15 players within £100.0m budget and max 3 per club.", font_size="0.8rem", color="var(--text-sub)"),
                            align="start",
                            spacing="1",
                        ),
                        rx.spacer(),
                        rx.hstack(
                            rx.button(
                                rx.hstack(rx.icon("arrow-left-right", size=13), rx.text("Load Post-Transfer"), align="center", spacing="1"),
                                variant="surface",
                                color_scheme="cyan",
                                size="2",
                                on_click=SimulatorState.load_sandbox_post_transfer_15,
                            ),
                            rx.button(
                                rx.hstack(rx.icon("user", size=13), rx.text("Load My Squad"), align="center", spacing="1"),
                                variant="surface",
                                color_scheme="blue",
                                size="2",
                                on_click=SimulatorState.load_sandbox_my_squad,
                            ),
                            rx.button("Load Budget 15", variant="surface", color_scheme="purple", size="2", on_click=SimulatorState.load_sandbox_budget_15),
                            rx.button("Random 15", variant="surface", color_scheme="amber", size="2", on_click=SimulatorState.load_sandbox_random_15),
                            rx.button("Clear All", variant="surface", color_scheme="red", size="2", on_click=SimulatorState.clear_sandbox),
                            align="center",
                            spacing="2",
                            wrap="wrap",
                        ),
                        width="100%",
                        align="center",
                        wrap="wrap",
                        gap="0.5rem",
                    ),

                    # Live Constraints Badges
                    rx.hstack(
                        rx.badge(
                            rx.concat("Players: ", SimulatorState.sandbox_selected_count.to_string(), " / 15"),
                            variant="surface",
                            color_scheme=rx.cond(SimulatorState.sandbox_selected_count == 15, "green", "amber"),
                            size="2",
                        ),
                        rx.badge(
                            rx.concat("Budget: £", SimulatorState.sandbox_total_cost.to_string(), "m (Left: £", SimulatorState.sandbox_budget_remaining.to_string(), "m)"),
                            variant="surface",
                            color_scheme=rx.cond(SimulatorState.sandbox_budget_remaining >= 0.0, "green", "red"),
                            size="2",
                        ),
                        rx.badge(rx.concat("GKP: ", SimulatorState.sandbox_gkp_count.to_string(), "/2"), variant="surface", color_scheme=rx.cond(SimulatorState.sandbox_gkp_count == 2, "green", "gray"), size="2"),
                        rx.badge(rx.concat("DEF: ", SimulatorState.sandbox_def_count.to_string(), "/5"), variant="surface", color_scheme=rx.cond(SimulatorState.sandbox_def_count == 5, "green", "gray"), size="2"),
                        rx.badge(rx.concat("MID: ", SimulatorState.sandbox_mid_count.to_string(), "/5"), variant="surface", color_scheme=rx.cond(SimulatorState.sandbox_mid_count == 5, "green", "gray"), size="2"),
                        rx.badge(rx.concat("FWD: ", SimulatorState.sandbox_fwd_count.to_string(), "/3"), variant="surface", color_scheme=rx.cond(SimulatorState.sandbox_fwd_count == 3, "green", "gray"), size="2"),
                        rx.badge(rx.concat("Club Limit: Max ", SimulatorState.sandbox_max_team_count.to_string(), "/3"), variant="surface", color_scheme=rx.cond(SimulatorState.sandbox_max_team_count <= 3, "green", "red"), size="2"),
                        wrap="wrap",
                        spacing="2",
                        width="100%",
                        margin_y="0.35rem",
                    ),

                    # Search & Pos filter
                    rx.hstack(
                        rx.input(
                            placeholder="Search player or club...",
                            value=SimulatorState.sandbox_search,
                            on_change=SimulatorState.set_sandbox_search,
                            size="2",
                            debounce_timeout=300,
                            width="16rem",
                        ),
                        rx.hstack(
                            rx.button("ALL", variant=rx.cond(SimulatorState.sandbox_pos_filter == "ALL", "solid", "surface"), size="1", color_scheme="gray", on_click=lambda: SimulatorState.set_sandbox_pos_filter("ALL")),
                            rx.button("GKP", variant=rx.cond(SimulatorState.sandbox_pos_filter == "GKP", "solid", "surface"), size="1", color_scheme="amber", on_click=lambda: SimulatorState.set_sandbox_pos_filter("GKP")),
                            rx.button("DEF", variant=rx.cond(SimulatorState.sandbox_pos_filter == "DEF", "solid", "surface"), size="1", color_scheme="blue", on_click=lambda: SimulatorState.set_sandbox_pos_filter("DEF")),
                            rx.button("MID", variant=rx.cond(SimulatorState.sandbox_pos_filter == "MID", "solid", "surface"), size="1", color_scheme="green", on_click=lambda: SimulatorState.set_sandbox_pos_filter("MID")),
                            rx.button("FWD", variant=rx.cond(SimulatorState.sandbox_pos_filter == "FWD", "solid", "surface"), size="1", color_scheme="red", on_click=lambda: SimulatorState.set_sandbox_pos_filter("FWD")),
                            align="center",
                            spacing="1",
                        ),
                        width="100%",
                        align="center",
                        wrap="wrap",
                        gap="0.5rem",
                    ),

                    # Pool Table
                    rx.cond(
                        SimulatorState.sandbox_is_loading_pool,
                        rx.center(rx.spinner(size="2"), padding="2rem", width="100%"),
                        rx.box(
                            rx.table.root(
                                rx.table.header(
                                    rx.table.row(
                                        rx.table.column_header_cell("Select", width="70px"),
                                        rx.table.column_header_cell("Player"),
                                        rx.table.column_header_cell("Club"),
                                        rx.table.column_header_cell("Pos"),
                                        rx.table.column_header_cell("Cost"),
                                        rx.table.column_header_cell("Proj xP"),
                                        rx.table.column_header_cell("Fixture"),
                                        rx.table.column_header_cell("FDR", style={"textAlign": "center"}),
                                    ),
                                ),
                                rx.table.body(
                                    rx.foreach(
                                        SimulatorState.filtered_sandbox_pool,
                                        lambda p: rx.table.row(
                                            rx.table.cell(
                                                rx.checkbox(
                                                    checked=SimulatorState.sandbox_selected_ids.contains(p["id"]),
                                                    on_change=lambda _: SimulatorState.toggle_sandbox_player(p["id"]),
                                                ),
                                            ),
                                            rx.table.cell(
                                                rx.hstack(
                                                    rx.image(src=p["photo"], width="24px", height="24px", border_radius="50%", fallback="shirt_0-66.webp"),
                                                    rx.text(p["Player"], font_weight="600"),
                                                    align="center",
                                                    spacing="2",
                                                ),
                                            ),
                                            rx.table.cell(rx.text(p["Team"])),
                                            rx.table.cell(_position_badge(p["Pos"])),
                                            rx.table.cell(rx.text(rx.concat("£", p["Cost"].to_string(), "m"))),
                                            rx.table.cell(rx.text(p["Proj_Pts"].to_string(), font_weight="700", color="#60a5fa")),
                                            rx.table.cell(rx.text(p["Opponent"], font_size="0.8rem")),
                                            rx.table.cell(_fdr_badge(p["FDR"]), style={"textAlign": "center"}),
                                        ),
                                    ),
                                ),
                                variant="surface",
                                size="1",
                                width="100%",
                            ),
                            style={
                                **TABLE_CONTAINER_STYLE,
                                "max_height": "320px",
                                "overflow_y": "auto",
                                "overflow_x": "auto",
                                "width": "100%",
                            },
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                style={
                    **CARD_STYLE,
                    "margin_bottom": "1.5rem",
                },
                width="100%",
            ),
            layout="position",
            initial={"opacity": 0, "y": -10},
            animate={"opacity": 1, "y": 0},
            transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
            width="100%",
        ),
        rx.box(),
    ),

        # Main Content: 2-Column Split matching Reference Screenshot
        rx.grid(
            # ── LEFT COLUMN: Optimal Starting XI Table + Controls ──────────────
            rx.box(
                rx.vstack(
                    rx.text("Optimal Starting XI (11 players)", font_weight="700", font_size="1rem", color="var(--text-main)"),
                    rx.cond(
                        SimulatorState.starting_xi.length() > 0,
                        _starting_xi_table(),
                        rx.box(
                            rx.center(
                                rx.text("Click 'Run Simulation' to resolve the optimal XI.", font_size="0.85rem", color="var(--text-sub)"),
                                padding="2rem",
                            ),
                            style=TABLE_CONTAINER_STYLE,
                        ),
                    ),

                    # Simulation Settings Card
                    rx.box(
                        rx.vstack(
                            rx.text("Simulation Settings", font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                            rx.hstack(
                                rx.text("Iterations:", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                                rx.hstack(
                                    rx.button("1000", variant=rx.cond(SimulatorState.iterations == 1000, "solid", "surface"), size="1", color_scheme="blue", on_click=lambda: SimulatorState.set_iterations(1000)),
                                    rx.button("5000", variant=rx.cond(SimulatorState.iterations == 5000, "solid", "surface"), size="1", color_scheme="blue", on_click=lambda: SimulatorState.set_iterations(5000)),
                                    rx.button("10000", variant=rx.cond(SimulatorState.iterations == 10000, "solid", "surface"), size="1", color_scheme="blue", on_click=lambda: SimulatorState.set_iterations(10000)),
                                    rx.button("20000", variant=rx.cond(SimulatorState.iterations == 20000, "solid", "surface"), size="1", color_scheme="blue", on_click=lambda: SimulatorState.set_iterations(20000)),
                                    spacing="1",
                                ),
                                align="center",
                                spacing="2",
                            ),
                            rx.hstack(
                                rx.checkbox(
                                    checked=SimulatorState.h2h_enabled,
                                    on_change=lambda _: SimulatorState.toggle_h2h(),
                                ),
                                rx.text("Compare Against Benchmark (H2H)", font_size="0.85rem", font_weight="600"),
                                align="center",
                                spacing="2",
                            ),
                            rx.button(
                                rx.hstack(
                                    rx.icon("play", size=16),
                                    rx.text("Run Monte Carlo Simulation", font_weight="700"),
                                    align="center",
                                    spacing="2",
                                ),
                                variant="solid",
                                color_scheme="blue",
                                size="3",
                                width="100%",
                                on_click=SimulatorState.refresh_simulation,
                                loading=SimulatorState.is_loading,
                            ),
                            spacing="3",
                            width="100%",
                        ),
                        style=CARD_STYLE,
                        width="100%",
                        id="tour-sim-iterations",
                        custom_attrs={"data-tour-id": "tour-sim-iterations"},
                    ),
                    spacing="3",
                    width="100%",
                ),
                min_width="0",
                max_width="100%",
                width="100%",
            ),

            # ── RIGHT COLUMN: Simulation Results (KPI Cards + Histogram + Tables) ─
            rx.box(
                rx.vstack(
                    rx.cond(
                        SimulatorState.is_loading,
                        loading_view(
                            status_message=SimulatorState.status_message,
                            title="Monte Carlo Match Engine",
                            badge_text="SIMULATION ENGINE",
                        ),
                        rx.cond(
                            SimulatorState.has_results,
                            MotionDiv.create(
                                rx.vstack(
                                    # Header with Exec Time
                                rx.hstack(
                                    rx.text("Simulation Results", font_size="1.25rem", font_weight="700", color="var(--text-main)"),
                                    rx.text(SimulatorState.exec_time_label, font_size="0.8rem", color="var(--text-sub)"),
                                    align="baseline",
                                    spacing="2",
                                ),

                                # 4 Metric Cards Matching Screenshot
                                rx.grid(
                                    rx.box(
                                        rx.vstack(
                                            rx.text("Median Score", font_size="0.75rem", color="var(--text-sub)", font_weight="600"),
                                            rx.text(SimulatorState.median_label, font_size="1.3rem", font_weight="700", color="var(--text-main)"),
                                            align="start",
                                            spacing="1",
                                        ),
                                        style=METRIC_CARD_STYLE,
                                        min_width="0",
                                    ),
                                    rx.box(
                                        rx.vstack(
                                            rx.text("Safe Floor (p10)", font_size="0.75rem", color="var(--text-sub)", font_weight="600"),
                                            rx.text(SimulatorState.floor_label, font_size="1.3rem", font_weight="700", color="#38bdf8"),
                                            align="start",
                                            spacing="1",
                                        ),
                                        style=METRIC_CARD_STYLE,
                                        min_width="0",
                                    ),
                                    rx.box(
                                        rx.vstack(
                                            rx.text("Haul Ceiling (p90)", font_size="0.75rem", color="var(--text-sub)", font_weight="600"),
                                            rx.text(SimulatorState.ceiling_label, font_size="1.3rem", font_weight="700", color="#a855f7"),
                                            align="start",
                                            spacing="1",
                                        ),
                                        style=METRIC_CARD_STYLE,
                                        min_width="0",
                                    ),
                                    rx.box(
                                        rx.vstack(
                                            rx.text("Volatility (±σ)", font_size="0.75rem", color="var(--text-sub)", font_weight="600"),
                                            rx.text(SimulatorState.volatility_label, font_size="1.3rem", font_weight="700", color="var(--text-main)"),
                                            align="start",
                                            spacing="1",
                                        ),
                                        style=METRIC_CARD_STYLE,
                                        min_width="0",
                                    ),
                                    columns=rx.breakpoints(initial="2", sm="2", xl="4"),
                                    spacing="3",
                                    width="100%",
                                ),

                                # Distribution Chart (Recharts BarChart)
                                rx.box(
                                    rx.vstack(
                                        rx.hstack(
                                            rx.text("Simulations", font_size="0.75rem", color="var(--text-sub)", font_weight="600"),
                                            rx.spacer(),
                                            rx.hstack(
                                                rx.box(width="8px", height="8px", border_radius="50%", background="#ef4444"),
                                                rx.text("Floor (p10)", font_size="0.7rem", color="var(--text-sub)"),
                                                rx.box(width="8px", height="8px", border_radius="50%", background="#22c55e", margin_left="6px"),
                                                rx.text("Median", font_size="0.7rem", color="var(--text-sub)"),
                                                rx.box(width="8px", height="8px", border_radius="50%", background="#eab308", margin_left="6px"),
                                                rx.text("Ceiling (p90)", font_size="0.7rem", color="var(--text-sub)"),
                                                align="center",
                                                spacing="1",
                                            ),
                                            width="100%",
                                            align="center",
                                        ),
                                        rx.recharts.bar_chart(
                                            rx.recharts.cartesian_grid(stroke_dasharray="3 3", stroke="#27272a"),
                                            rx.recharts.x_axis(data_key="points", stroke="#71717a", font_size="11px"),
                                            rx.recharts.y_axis(stroke="#71717a", font_size="11px"),
                                            rx.recharts.bar(data_key="simulations", fill="#3b82f6", radius=[2, 2, 0, 0]),
                                            rx.recharts.reference_line(x=SimulatorState.sim_p10_str, stroke="#ef4444", stroke_dasharray="4 4"),
                                            rx.recharts.reference_line(x=SimulatorState.sim_median_str, stroke="#22c55e", stroke_dasharray="4 4"),
                                            rx.recharts.reference_line(x=SimulatorState.sim_p90_str, stroke="#eab308", stroke_dasharray="4 4"),
                                            data=SimulatorState.hist_data,
                                            height=260,
                                            width="100%",
                                        ),
                                        spacing="2",
                                        width="100%",
                                    ),
                                    style=CARD_STYLE,
                                    width="100%",
                                    min_width="0",
                                    overflow_x="hidden",
                                ),

                                # Head-to-Head Comparison Banner (if enabled)
                                rx.cond(
                                    SimulatorState.h2h_enabled,
                                    rx.box(
                                        rx.vstack(
                                            rx.hstack(
                                                rx.icon("swords", size=18, color="#06b6d4"),
                                                rx.text(rx.concat("Head-to-Head Benchmark vs ", SimulatorState.h2h_benchmark_name), font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                                                align="center",
                                                spacing="2",
                                            ),
                                            rx.hstack(
                                                rx.badge(rx.concat("Your Win Rate: ", SimulatorState.h2h_win_pct_a.to_string(), "%"), variant="soft", color_scheme="green", size="2"),
                                                rx.badge(rx.concat("Draw: ", SimulatorState.h2h_draw_pct.to_string(), "%"), variant="surface", color_scheme="gray", size="2"),
                                                rx.badge(rx.concat(SimulatorState.h2h_benchmark_name, " Win: ", SimulatorState.h2h_win_pct_b.to_string(), "%"), variant="soft", color_scheme="red", size="2"),
                                                wrap="wrap",
                                                spacing="2",
                                            ),
                                            align="start",
                                            spacing="2",
                                            width="100%",
                                        ),
                                        padding="0.85rem",
                                        border_radius="8px",
                                        background="rgba(6, 182, 212, 0.06)",
                                        border="1px solid rgba(6, 182, 212, 0.25)",
                                        width="100%",
                                    ),
                                    rx.box(),
                                ),

                                # Player Distribution Analysis Table
                                rx.box(
                                    rx.text("Player Contribution Breakdown", font_weight="700", font_size="1rem", margin_bottom="0.65rem"),
                                    rx.box(
                                        rx.table.root(
                                            rx.table.header(
                                                rx.table.row(
                                                    rx.table.column_header_cell("Player"),
                                                    rx.table.column_header_cell("Pos"),
                                                    rx.table.column_header_cell("Club"),
                                                    rx.table.column_header_cell("Median Pts"),
                                                    rx.table.column_header_cell("Haul Prob (≥10)"),
                                                    rx.table.column_header_cell("Clean Sheet Prob"),
                                                ),
                                            ),
                                            rx.table.body(
                                                rx.foreach(
                                                    SimulatorState.player_stats,
                                                    lambda row: rx.table.row(
                                                        rx.table.cell(
                                                            rx.hstack(
                                                                rx.text(row["web_name"], font_weight="600"),
                                                                rx.cond(
                                                                    row["id"] == SimulatorState.captain_id,
                                                                    rx.badge("(C)", variant="solid", color_scheme="amber", size="1"),
                                                                    rx.cond(
                                                                        row["id"] == SimulatorState.vc_id,
                                                                        rx.badge("(VC)", variant="surface", color_scheme="gray", size="1"),
                                                                        rx.box(),
                                                                    ),
                                                                ),
                                                                align="center",
                                                                spacing="1",
                                                            ),
                                                        ),
                                                        rx.table.cell(_position_badge(row["pos"])),
                                                        rx.table.cell(rx.badge(row["team"], variant="surface", color_scheme="gray", size="1")),
                                                        rx.table.cell(rx.text(row["median"].to_string(), font_weight="700")),
                                                        rx.table.cell(
                                                            rx.cond(
                                                                row["haul_prob"].to(float) >= 15.0,
                                                                rx.badge(rx.concat(row["haul_prob"].to_string(), "%"), variant="soft", color_scheme="green", size="1"),
                                                                rx.badge(rx.concat(row["haul_prob"].to_string(), "%"), variant="surface", color_scheme="gray", size="1"),
                                                            ),
                                                        ),
                                                        rx.table.cell(
                                                            rx.cond(
                                                                row["cs_prob"].to(float) > 0.0,
                                                                rx.text(rx.concat(row["cs_prob"].to_string(), "%")),
                                                                rx.text("—", color="var(--text-muted)"),
                                                            ),
                                                        ),
                                                    ),
                                                ),
                                            ),
                                            variant="surface",
                                            size="1",
                                            width="100%",
                                        ),
                                        style=TABLE_CONTAINER_STYLE,
                                        width="100%",
                                        overflow_x="auto",
                                        min_width="0",
                                    ),
                                    width="100%",
                                    min_width="0",
                                ),
                                spacing="4",
                                width="100%",
                            ),
                            layout="position",
                            initial={"opacity": 0, "y": 15},
                            animate={"opacity": 1, "y": 0},
                            transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
                            width="100%",
                        ),
                            rx.center(
                                rx.vstack(
                                    rx.icon("activity", size=36, color="var(--text-muted)"),
                                    rx.text("Configure your squad and run the simulation to see distributions.", font_size="0.9rem", color="var(--text-sub)"),
                                    rx.button("Run Simulation Now", on_click=SimulatorState.refresh_simulation, variant="solid", color_scheme="blue", size="2"),
                                    align="center",
                                    spacing="3",
                                ),
                                padding="5rem",
                                width="100%",
                            ),
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                min_width="0",
                max_width="100%",
                width="100%",
                id="tour-sim-results",
                custom_attrs={"data-tour-id": "tour-sim-results"},
            ),
            columns=rx.breakpoints(initial="1", lg="5fr 7fr"),
            spacing="4",
            width="100%",
        ),
        width="100%",
        on_mount=SimulatorState.run_simulation,
    )
