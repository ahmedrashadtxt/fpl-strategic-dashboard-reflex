"""Rolling Form Page - Moving averages, momentum analysis, and fixture opportunity mapping."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.rolling import RollingFormState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    player_highlight_card,
    data_table,
    search_input,
    filter_select,
)


def rolling_metric_cards() -> rx.Component:
    """Isolated player highlight cards component matching Streamlit layout."""
    return rx.cond(
        RollingFormState.has_data,
        rx.grid(
            rx.foreach(
                RollingFormState.top_cards,
                player_highlight_card,
            ),
            columns=rx.breakpoints(initial="1", sm="2", lg="4"),
            spacing="3",
            width="100%",
            margin_bottom="1.25rem",
        ),
        rx.box(),
    )


def rolling_form_controls() -> rx.Component:
    """Filter controls matching the Streamlit Rolling Form interface."""
    return rx.vstack(
        # Row 1: Search, Match Window, Position, Min Matches, Min Avg Mins, Rank By
        rx.grid(
            # Search
            rx.vstack(
                rx.text("Search Player / Club", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                search_input(
                    value=RollingFormState.search_query,
                    on_change=RollingFormState.set_search,
                    placeholder="e.g. Cherki, Saka, Chelsea, ARS...",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Match Window slider
            rx.vstack(
                rx.hstack(
                    rx.text("Match Window", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        rx.concat("L", RollingFormState.window_size),
                        variant="surface",
                        color_scheme="blue",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=1,
                    max=10,
                    step=1,
                    value=[RollingFormState.window_size],
                    on_value_commit=RollingFormState.set_window,
                    color_scheme="blue",
                    size="1",
                    width="100%",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Position select
            filter_select(
                "Position",
                ["All", "GKP", "DEF", "MID", "FWD"],
                RollingFormState.position_filter,
                RollingFormState.set_pos,
            ),
            # Min Matches slider
            rx.vstack(
                rx.hstack(
                    rx.text("Min Matches", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        RollingFormState.min_matches,
                        variant="surface",
                        color_scheme="green",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=1,
                    max=10,
                    step=1,
                    value=[RollingFormState.min_matches],
                    on_value_commit=RollingFormState.set_min_matches,
                    color_scheme="green",
                    size="1",
                    width="100%",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Min Avg Mins slider
            rx.vstack(
                rx.hstack(
                    rx.text("Min Avg Mins", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        RollingFormState.min_avg_mins,
                        variant="surface",
                        color_scheme="green",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=0,
                    max=90,
                    step=15,
                    value=[RollingFormState.min_avg_mins],
                    on_value_commit=RollingFormState.set_min_mins,
                    color_scheme="green",
                    size="1",
                    width="100%",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Rank By select
            filter_select(
                "Rank By",
                [
                    "Projected Form xP / Match",
                    "Rolling Avg Points",
                    "Rolling Sum xGI",
                    "Rolling xGI / 90",
                    "Upcoming Fixture Ease",
                    "Rolling Avg Minutes",
                    "Price",
                ],
                RollingFormState.sort_by,
                RollingFormState.set_sort,
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="3", lg="6"),
            spacing="3",
            width="100%",
            align_items="end",
        ),
        # Row 2: Max Price slider & Squad toggle
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text("Filter Max Price (£M)", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        rx.concat("£", RollingFormState.max_price),
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
                    value=[RollingFormState.max_price],
                    on_value_commit=RollingFormState.set_price,
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
                    checked=RollingFormState.only_my_squad,
                    on_change=RollingFormState.set_only_squad,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("crosshair", size=14, color="var(--text-sub)"),
                    rx.text("Only My Squad Players", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    align="center",
                    spacing="1",
                ),
                align="center",
                spacing="2",
            ),
            width="100%",
            align="center",
            padding_top="0.5rem",
            wrap="wrap",
            gap="1rem",
        ),
        width="100%",
        spacing="3",
        padding="1rem",
        background="var(--gray-2)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        margin_bottom="1.25rem",
    )


def rolling_form_page() -> rx.Component:
    """Renders the Rolling Form tab view."""
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
                    rx.text("Rolling Form & Projected xP Trends", class_name="section-header-title"),
                    rx.text(
                        "Analyze rolling points output and expected points trajectory vs fixture schedule",
                        class_name="section-header-sub",
                    ),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Rolling Form & Projected xP Trends",
                    subtitle="Analyze rolling points output and expected points trajectory vs fixture schedule",
                    items=[
                        {
                            "badge": "Form xP",
                            "title": "Projected Form xP",
                            "desc": "Blended expected points per match combining underlying rolling xGI/90, actual match points form, playing security, and upcoming 5-GW difficulty.",
                        },
                        {
                            "badge": "5-GW FDR",
                            "title": "Fixture Difficulty Run",
                            "desc": "Cumulative official FDR rating across the upcoming 5 gameweeks (lower score indicates an easy, green schedule).",
                        },
                        {
                            "badge": "Scatter Matrix",
                            "title": "Quadrant Opportunity Map",
                            "desc": "Visual scatter plot mapping form against schedule difficulty to spot elite targets in Quadrant I (top-left).",
                        },
                        {
                            "badge": "Price & Match Filters",
                            "title": "Budget & Sample Security",
                            "desc": "Filters players by max budget ceiling and minimum appearances to eliminate low-minute noise.",
                        },
                        {
                            "badge": "Rolling xGI",
                            "title": "Expected Underlying Trajectory",
                            "desc": "5-match rolling expected goal involvement trajectory to catch upward and downward form trends before market price changes.",
                        },
                    ],
                    tip="Target Quadrant I players (high rolling xGI entering an easy 5-GW green run) for maximum captaincy and price appreciation upside.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=RollingFormState.refresh_data,
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
        rolling_form_controls(),

        # Scatter Matrix (Projected Form vs Fixture Run)
        rx.cond(
            RollingFormState.has_data,
            rx.box(
                rx.plotly(
                    data=RollingFormState.plot_fig,
                    height="450px",
                    width="100%",
                ),
                width="100%",
                background="rgba(15, 23, 42, 0.4)",
                border="1px solid var(--border-color)",
                border_radius="10px",
                padding="0.5rem",
                margin_bottom="1.25rem",
                overflow="hidden",
            ),
            rx.box(),
        ),

        # Top Highlight Cards
        rolling_metric_cards(),

        # Data Table with Player Avatars and Streamlit Columns
        data_table(
            headers=RollingFormState.columns,
            rows=RollingFormState.table_data,
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
                # GW
                rx.table.cell(rx.text(row["Latest_GW"])),
                # Proj Form xP
                rx.table.cell(
                    rx.badge(
                        row["Proj_Form_XP_Display"],
                        variant="surface",
                        color_scheme="green",
                        size="1",
                        font_weight="700",
                    )
                ),
                # Avg Pts
                rx.table.cell(rx.text(row["Rolling_Avg_Pts_Display"], font_weight="700")),
                # xGI
                rx.table.cell(rx.text(row["Rolling_Sum_xGI_Display"])),
                # xGI/90
                rx.table.cell(rx.text(row["Rolling_xGI_90_Display"])),
                # Next 5 FDR
                rx.table.cell(
                    rx.badge(
                        row["FDR_Display"],
                        variant="solid",
                        color_scheme=row["FDR_Color"],
                        size="1",
                        font_weight="800",
                    )
                ),
                # Mins
                rx.table.cell(rx.text(row["Rolling_Avg_Mins_Display"])),
                # Apps
                rx.table.cell(rx.text(row["Rolling_Matches_Played"])),
            ),
            is_loading=RollingFormState.is_loading,
        ),
        width="100%",
        on_mount=RollingFormState.load_data,
    )
