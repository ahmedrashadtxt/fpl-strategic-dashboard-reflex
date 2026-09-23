"""Defensive Stats Page - Pure presentation view for defensive metrics and rankings."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.defensive import DefensiveStatsState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    player_highlight_card,
    data_table,
    search_input,
    filter_select,
    MotionDiv,
)


def defensive_metric_cards() -> rx.Component:
    """Isolated player highlight cards component matching Streamlit layout."""
    return rx.cond(
        DefensiveStatsState.has_data,
        MotionDiv.create(
            rx.grid(
                rx.foreach(
                    DefensiveStatsState.top_cards,
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


def defensive_stats_controls() -> rx.Component:
    """Filter controls matching the Streamlit Defensive Contributions interface."""
    return rx.vstack(
        # Row 1: Search, Min Avg Mins, Position, Rank By
        rx.grid(
            rx.vstack(
                rx.text("Search Player / Club", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                search_input(
                    value=DefensiveStatsState.search_query,
                    on_change=DefensiveStatsState.set_search,
                    placeholder="e.g. Gabriel, Raya, Saliba, ARS...",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            rx.vstack(
                rx.hstack(
                    rx.icon("clock", size=14, color="var(--text-sub)"),
                    rx.text("Min Avg Mins / GW", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(DefensiveStatsState.min_avg_mins, variant="surface", color_scheme="green", size="1"),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=0,
                    max=90,
                    step=5,
                    value=[DefensiveStatsState.min_avg_mins],
                    on_value_commit=DefensiveStatsState.set_min_mins,
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
                ["DEF", "All", "GKP", "MID"],
                DefensiveStatsState.position_filter,
                DefensiveStatsState.set_pos,
            ),
            filter_select(
                "Rank By",
                [
                    "Projected Defensive xP",
                    "DC per 90",
                    "Total DC",
                    "Projected Defensive xP / 90",
                    "CBI (Clearances, Blocks, Int)",
                    "Tackles (T)",
                    "Recoveries (R)",
                    "Expected Goals Conceded (Lowest xGC)",
                    "Clean Sheets",
                    "Total Points",
                    "Goalkeeper Saves",
                ],
                DefensiveStatsState.sort_by,
                DefensiveStatsState.set_sort,
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
                        rx.concat("£", DefensiveStatsState.max_price),
                        variant="surface",
                        color_scheme="green",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.slider(
                    min=3.5,
                    max=15.5,
                    step=0.5,
                    value=[DefensiveStatsState.max_price],
                    on_value_commit=DefensiveStatsState.set_price,
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
                    checked=DefensiveStatsState.only_my_squad,
                    on_change=DefensiveStatsState.set_only_squad,
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
                    checked=DefensiveStatsState.show_career_baseline,
                    on_change=DefensiveStatsState.set_career,
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


def defensive_stats_page() -> rx.Component:
    """Renders the Defensive Contributions tab view."""
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
                    rx.text("Defensive Rotation & CS Odds", class_name="section-header-title"),
                    rx.text("Identify clean sheet probabilities, defensive contributions (CBI, saves, tackles), and optimal budget enablers.", class_name="section-header-sub"),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Defensive Analysis Guide",
                    subtitle="Metrics for defenders and goalkeepers",
                    items=[
                        {"badge": "CS Prob", "title": "Clean Sheet Probability", "desc": "Market-implied probability of keeping a clean sheet."},
                        {"badge": "CBI", "title": "Defensive Involvements", "desc": "Clearances, blocks, interceptions that contribute to BPS and bonus floor."},
                        {"badge": "Saves", "title": "Save Points Potential", "desc": "High-volume save keepers (1pt per 3 saves) from mid-table clubs."},
                    ],
                    tip="Target defenders with high CBI baseline who play for teams with high CS probability.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=DefensiveStatsState.refresh_data,
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
        defensive_stats_controls(),

        # Top Metric Cards
        defensive_metric_cards(),

        # Data Table with Player Avatars and Streamlit Columns
        data_table(
            headers=DefensiveStatsState.columns,
            rows=DefensiveStatsState.table_data,
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
                # CS
                rx.table.cell(rx.text(row["Clean_Sheets"])),
                # GC
                rx.table.cell(rx.text(row["Goals_Conceded"])),
                # xGC
                rx.table.cell(rx.text(row["xGC_Display"])),
                # Proj Def xP (blue pill)
                rx.table.cell(rx.badge(row["Proj_Def_XP_Display"], variant="surface", color_scheme="blue", size="1")),
                # xGC/90
                rx.table.cell(rx.text(row["xGC_90_Display"])),
                # DC
                rx.table.cell(rx.text(row["DC"], font_weight="700")),
                # DC/90
                rx.table.cell(rx.text(row["DC_90_Display"])),
                # CBI
                rx.table.cell(rx.text(row["CBI"])),
                # R
                rx.table.cell(rx.text(row["R"])),
                # T
                rx.table.cell(rx.text(row["T"])),
                # Optional career baselines
                rx.cond(
                    DefensiveStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_GC_90_Display"])),
                    rx.fragment(),
                ),
                rx.cond(
                    DefensiveStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_CS_90_Display"])),
                    rx.fragment(),
                ),
                rx.cond(
                    DefensiveStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_Pts_90_Display"])),
                    rx.fragment(),
                ),
                rx.cond(
                    DefensiveStatsState.show_career_baseline,
                    rx.table.cell(rx.text(row["Career_Mins_Display"])),
                    rx.fragment(),
                ),
            ),
            is_loading=DefensiveStatsState.is_loading,
        ),
        width="100%",
        on_mount=DefensiveStatsState.load_data,
    )
