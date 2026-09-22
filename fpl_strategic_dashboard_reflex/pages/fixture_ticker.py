"""Fixture Ticker Page - 5-GW forward fixture difficulty matrix with club crests and squad visibility."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.fixtures import FixtureTickerState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    search_input,
)
from fpl_strategic_dashboard_reflex.styles.theme import TABLE_CONTAINER_STYLE


def _fdr_badge(diff_var, label_var, blank_var) -> rx.Component:
    """Renders a styled fixture pill reflecting fixture difficulty."""
    d = diff_var.to(int)
    return rx.cond(
        blank_var,
        rx.badge("Blank", variant="surface", color_scheme="gray", size="2", width="100%", justify="center"),
        rx.cond(
            d <= 2,
            rx.badge(label_var, variant="surface", color_scheme="green", size="2", font_weight="600", width="100%", justify="center"),
            rx.cond(
                d == 3,
                rx.badge(label_var, variant="surface", color_scheme="gray", size="2", font_weight="600", width="100%", justify="center"),
                rx.cond(
                    d == 4,
                    rx.badge(label_var, variant="surface", color_scheme="orange", size="2", font_weight="700", width="100%", justify="center"),
                    rx.badge(label_var, variant="surface", color_scheme="red", size="2", font_weight="800", width="100%", justify="center"),
                ),
            ),
        ),
    )


def fixture_ticker_page() -> rx.Component:
    """Renders the Fixture Ticker page view."""
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
                    rx.text(rx.concat("Fixture Difficulty · ", FixtureTickerState.horizon_label), class_name="section-header-title"),
                    rx.text("Upcoming schedule ranked by difficulty", class_name="section-header-sub"),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Fixture Difficulty Ticker",
                    subtitle="Upcoming schedule ranked by official FDR and venue difficulty",
                    items=[
                        {
                            "badge": "FDR Sum",
                            "title": "Cumulative Difficulty Score",
                            "desc": "Sum of official Premier League FDR scores across the upcoming 5 gameweeks (green = easy run, red = tough test).",
                        },
                        {
                            "badge": "Venue",
                            "title": "Home & Away Adjustments",
                            "desc": "(H) vs. (A) tags show home pitch advantage and away fixture handicaps across the 5-match window.",
                        },
                        {
                            "badge": "Swings",
                            "title": "Fixture Swing Timing",
                            "desc": "Identify key turning points where clubs swing from tough runs (FDR 15+) into prime attackable schedules (FDR <= 10).",
                        },
                        {
                            "badge": "Squad Clubs",
                            "title": "My Squad Club Filter",
                            "desc": "Instantly filter the ticker to isolate the clubs represented in your current 15-player squad.",
                        },
                        {
                            "badge": "Search",
                            "title": "Club & Player Quick Lookup",
                            "desc": "Search by player name or 3-letter club abbreviation to immediately locate specific club schedules.",
                        },
                    ],
                    tip="Plan transfers 2 to 3 gameweeks ahead of major green fixture swings to beat transfer price rises and capture maximum haul windows.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=FixtureTickerState.refresh_data,
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

        # Filter Bar matching Streamlit layout
        rx.hstack(
            rx.vstack(
                rx.text("Search Player / Club", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                search_input(
                    value=FixtureTickerState.search_query,
                    on_change=FixtureTickerState.set_search,
                    placeholder="e.g. Saka, Arsenal, Haaland, MCI...",
                ),
                align="start",
                spacing="1",
                width="340px",
            ),
            rx.spacer(),
            rx.hstack(
                rx.switch(
                    checked=FixtureTickerState.only_my_squad,
                    on_change=FixtureTickerState.toggle_only_my_squad,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("crosshair", size=15, color="var(--text-sub)"),
                    rx.text("Only My Squad Clubs", font_size="0.85rem", color="var(--text-sub)", font_weight="600"),
                    align="center",
                    spacing="1",
                ),
                align="center",
                spacing="2",
                padding_top="1.4rem",
            ),
            width="100%",
            align="start",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),

        # Notice when squad filter active but no Team ID configured
        rx.cond(
            FixtureTickerState.needs_manager_id,
            rx.box(
                rx.hstack(
                    rx.icon("info", size=16, color="#38bdf8"),
                    rx.text("Enter your FPL Team ID in the top bar to filter by your squad.", font_size="0.85rem", color="#38bdf8", font_weight="500"),
                    align="center",
                    spacing="2",
                ),
                padding="0.75rem 1rem",
                background="rgba(56, 189, 248, 0.08)",
                border="1px solid rgba(56, 189, 248, 0.25)",
                border_radius="8px",
                margin_bottom="1rem",
                width="100%",
            ),
            rx.box(),
        ),

        # Fixture Matrix Table
        rx.box(
            rx.cond(
                FixtureTickerState.is_loading,
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Calculating fixture schedules...", font_size="0.85rem", color="var(--text-sub)"),
                        align="center",
                        spacing="2",
                    ),
                    padding="3rem",
                    width="100%",
                ),
                rx.cond(
                    FixtureTickerState.has_rows,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Club", font_weight="700", text_align="left", padding_left="1rem"),
                                rx.cond(
                                    FixtureTickerState.only_my_squad,
                                    rx.table.column_header_cell("Squad Players", font_weight="700", text_align="left"),
                                    rx.fragment(),
                                ),
                                rx.table.column_header_cell(FixtureTickerState.gw_col_labels[0], font_weight="700", text_align="center"),
                                rx.table.column_header_cell(FixtureTickerState.gw_col_labels[1], font_weight="700", text_align="center"),
                                rx.table.column_header_cell(FixtureTickerState.gw_col_labels[2], font_weight="700", text_align="center"),
                                rx.table.column_header_cell(FixtureTickerState.gw_col_labels[3], font_weight="700", text_align="center"),
                                rx.table.column_header_cell(FixtureTickerState.gw_col_labels[4], font_weight="700", text_align="center"),
                                rx.table.column_header_cell("Total FDR (5 GW)", font_weight="700", text_align="center"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                FixtureTickerState.rows,
                                lambda row: rx.table.row(
                                    # Club (Crest logo + Club name)
                                    rx.table.cell(
                                        rx.hstack(
                                            rx.image(
                                                src=row["crest_url"],
                                                width="24px",
                                                height="24px",
                                                object_fit="contain",
                                                flex_shrink="0",
                                            ),
                                            rx.text(row["club_display"], font_weight="600"),
                                            align="center",
                                            spacing="2",
                                        ),
                                        text_align="left",
                                        padding_left="1rem",
                                    ),
                                    # Squad Players (only visible when My Squad is active)
                                    rx.cond(
                                        FixtureTickerState.only_my_squad,
                                        rx.table.cell(
                                            rx.text(
                                                row["my_players"],
                                                font_weight="600",
                                                font_size="0.85rem",
                                                color="#60a5fa",
                                            ),
                                            text_align="left",
                                        ),
                                        rx.fragment(),
                                    ),
                                    # 5 Gameweek Badges
                                    rx.table.cell(_fdr_badge(row["gw0_diff"], row["gw0_label"], row["gw0_blank"]), text_align="center"),
                                    rx.table.cell(_fdr_badge(row["gw1_diff"], row["gw1_label"], row["gw1_blank"]), text_align="center"),
                                    rx.table.cell(_fdr_badge(row["gw2_diff"], row["gw2_label"], row["gw2_blank"]), text_align="center"),
                                    rx.table.cell(_fdr_badge(row["gw3_diff"], row["gw3_label"], row["gw3_blank"]), text_align="center"),
                                    rx.table.cell(_fdr_badge(row["gw4_diff"], row["gw4_label"], row["gw4_blank"]), text_align="center"),
                                    # Total FDR (5 GW)
                                    rx.table.cell(
                                        rx.text(
                                            row["difficulty_rating"].to_string(),
                                            font_weight="800",
                                            font_size="0.95rem",
                                            color=row["total_fdr_color"],
                                        ),
                                        text_align="center",
                                    ),
                                ),
                            )
                        ),
                        variant="surface",
                        size="2",
                        width="100%",
                    ),
                    rx.center(
                        rx.text("No clubs matched search or squad criteria.", font_size="0.85rem", color="var(--text-sub)"),
                        padding="3rem",
                        width="100%",
                    ),
                ),
            ),
            style=TABLE_CONTAINER_STYLE,
            width="100%",
        ),
        width="100%",
        on_mount=FixtureTickerState.load_data,
    )
