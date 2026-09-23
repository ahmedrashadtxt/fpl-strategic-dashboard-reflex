"""Expected Stats Page - Pure presentation view for xG, xA, and xGI analytics."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.expected import ExpectedStatsState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    player_highlight_card,
    data_table,
    search_input,
    filter_select,
    MotionDiv,
)


def expected_metric_cards() -> rx.Component:
    """Isolated player highlight cards component matching Streamlit layout."""
    return rx.cond(
        ExpectedStatsState.has_data,
        MotionDiv.create(
            rx.grid(
                rx.foreach(
                    ExpectedStatsState.top_cards,
                    player_highlight_card,
                ),
                columns=rx.breakpoints(initial="1", sm="2", lg="4"),
                spacing="3",
                width="100%",
            ),
            layout="position",
            transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
            width="100%",
            margin_bottom="1.25rem",
        ),
        rx.box(),
    )


def expected_stats_controls() -> rx.Component:
    """Filter controls matching the Streamlit Expected Stats interface."""
    return rx.vstack(
        # Row 1: Search, Min Avg Mins, Position, Rank By
        rx.grid(
            rx.vstack(
                rx.text("Search Player / Club", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                search_input(
                    value=ExpectedStatsState.search_query,
                    on_change=ExpectedStatsState.set_search,
                    placeholder="e.g. Palmer, Haaland, Arsenal, MCI...",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.icon("clock", size=14, color="var(--text-sub)"),
                    rx.text("Min Avg Mins / GW", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(ExpectedStatsState.min_avg_mins, variant="surface", color_scheme="green", size="1"),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=0,
                    max=90,
                    step=5,
                    value=[ExpectedStatsState.min_avg_mins],
                    on_value_commit=ExpectedStatsState.set_min_mins,
                    color_scheme="green",
                    size="1",
                    width="100%",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            filter_select(
                "Filter Position",
                ["All", "GKP", "DEF", "MID", "FWD"],
                ExpectedStatsState.position_filter,
                ExpectedStatsState.set_pos,
            ),
            filter_select(
                "Rank By",
                [
                    "Projected Attacking xP",
                    "Expected Goal Involvements (xGI)",
                    "xGI per 90",
                    "Projected Attacking xP / 90",
                    "Career GI / 90 (Past Seasons)",
                    "Total Points",
                    "Clean Sheets",
                    "Goalkeeper Saves",
                ],
                ExpectedStatsState.sort_by,
                ExpectedStatsState.set_sort,
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="4"),
            spacing="4",
            width="100%",
            align_items="end",
        ),
        # Row 2: Max Price Slider & Toggles
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text("Filter Max Price (£M)", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        rx.concat("£", ExpectedStatsState.max_price),
                        variant="surface",
                        color_scheme="green",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=4.0,
                    max=15.5,
                    step=0.5,
                    value=[ExpectedStatsState.max_price],
                    on_value_commit=ExpectedStatsState.set_price,
                    color_scheme="green",
                    size="1",
                    width="260px",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.hstack(
                rx.switch(
                    checked=ExpectedStatsState.only_my_squad,
                    on_change=ExpectedStatsState.set_only_squad,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("crosshair", size=14, color="var(--text-sub)"),
                    rx.text("Only My Squad Players", font_size="0.8rem", color="var(--text-sub)"),
                    align="center",
                    spacing="1",
                ),
                align="center",
                spacing="2",
            ),
            rx.hstack(
                rx.switch(
                    checked=ExpectedStatsState.show_career_baseline,
                    on_change=ExpectedStatsState.set_career,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("landmark", size=14, color="var(--text-sub)"),
                    rx.text("Show Career Baselines (Past Seasons)", font_size="0.8rem", color="var(--text-sub)"),
                    align="center",
                    spacing="1",
                ),
                align="center",
                spacing="2",
            ),
            width="100%",
            align="center",
            wrap="wrap",
            gap="1.5rem",
        ),
        padding="1rem 1.25rem",
        background="rgba(255, 255, 255, 0.02)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        width="100%",
        spacing="3",
        margin_bottom="1.25rem",
    )


def expected_stats_page() -> rx.Component:
    """Renders the Expected Stats tab view."""
    return rx.box(
        # Page Title & Guide
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
                    rx.text("Expected Attacking Statistics (xG · xA · xGI)", class_name="section-header-title"),
                    rx.text("Identify regression and value opportunities by filtering players by underlying expected goals and assists.", class_name="section-header-sub"),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Expected Stats Guide",
                    subtitle="Underlying goal & assist expectations",
                    items=[
                        {"badge": "xGI/90", "title": "Expected Goal Involvement", "desc": "Calculates the rate at which players generate quality chances per 90 minutes played."},
                        {"badge": "Regression", "title": "Buy/Sell Signals", "desc": "Players underperforming xG are primed for positive regression (buy targets)."},
                        {"badge": "Baseline", "title": "Career Historical GI/90", "desc": "Multi-season historical baseline performance across previous Premier League campaigns to separate form from class."},
                    ],
                    tip="Filter by minimum 60 minutes per match to exclude substitute cameos.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=ExpectedStatsState.refresh_data,
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

        # Filter Controls
        expected_stats_controls(),

        # Top Metric Cards
        expected_metric_cards(),

        # Data Table with Player Avatars and Streamlit Columns
        data_table(
            headers=ExpectedStatsState.columns,
            rows=ExpectedStatsState.table_data,
            row_render_func=lambda row: rx.table.row(
                # Player (with avatar)
                rx.table.cell(
                    rx.hstack(
                        rx.avatar(
                            src=row["img_url"],
                            fallback=row["Pos"],
                            size="1",
                            radius="full",
                        ),
                        rx.text(row["Player"], font_weight="600"),
                        align="center",
                        spacing="2",
                    ),
                    text_align="left",
                ),
                # Club
                rx.table.cell(rx.text(row["Team"], font_size="0.85rem")),
                # Pos
                rx.table.cell(rx.badge(row["Pos"], variant="outline", color_scheme=row["Pos_Color"], size="1")),
                # Price
                rx.table.cell(rx.text(rx.concat("£", row["Price_Display"]))),
                # Mins
                rx.table.cell(rx.text(row["Minutes_Display"])),
                # Avg M/GW
                rx.table.cell(rx.text(rx.concat(row["Avg_Mins_GW"], "m"))),
                # Pts
                rx.table.cell(rx.text(row["Total_Points"], font_weight="700")),
                # Gls
                rx.table.cell(rx.text(row["Goals"])),
                # Ast
                rx.table.cell(rx.text(row["Assists"])),
                # CS
                rx.table.cell(rx.text(row["Clean_Sheets"])),
                # Saves
                rx.table.cell(rx.text(row["Saves"])),
                # xG
                rx.table.cell(rx.text(row["xG_Display"])),
                # xA
                rx.table.cell(rx.text(row["xA_Display"])),
                # xGI
                rx.table.cell(rx.text(row["xGI_Display"], font_weight="700")),
                # Proj xP (highlight pill)
                rx.table.cell(rx.badge(row["Proj_XP_Display"], variant="surface", color_scheme="green", size="1")),
                # xGI/90
                rx.table.cell(rx.text(row["xGI_90_Display"])),
                # Optional career baselines
                rx.cond(
                    ExpectedStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_GI_90_Display"])),
                    rx.fragment(),
                ),
                rx.cond(
                    ExpectedStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_Pts_90_Display"])),
                    rx.fragment(),
                ),
                rx.cond(
                    ExpectedStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_Mins_Display"])),
                    rx.fragment(),
                ),
            ),
            is_loading=ExpectedStatsState.is_loading,
        ),
        width="100%",
        on_mount=ExpectedStatsState.load_data,
    )
