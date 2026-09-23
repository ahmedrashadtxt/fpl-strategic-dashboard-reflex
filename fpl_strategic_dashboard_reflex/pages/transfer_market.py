"""Transfer Market Page - Transfer Target Finder with player pictures, stats, and price change indicators."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.market import TransferMarketState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    player_highlight_card,
    data_table,
    search_input,
    filter_select,
    MotionDiv,
)


def market_metric_cards() -> rx.Component:
    """Isolated player highlight cards component matching Streamlit layout."""
    return rx.cond(
        TransferMarketState.has_data,
        MotionDiv.create(
            rx.grid(
                rx.foreach(
                    TransferMarketState.top_cards,
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


def market_controls() -> rx.Component:
    """Filter controls matching the Streamlit Transfer Target Finder interface."""
    return rx.vstack(
        # Row 1: Search, Filter Position, Rank Targets By
        rx.grid(
            # Search
            rx.vstack(
                rx.text("Search Player / Club", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                search_input(
                    value=TransferMarketState.search_query,
                    on_change=TransferMarketState.set_search,
                    placeholder="e.g. Eze, Semenyo, Arsenal, LIV...",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Filter Position
            filter_select(
                "Filter Position",
                ["All", "GKP", "DEF", "MID", "FWD"],
                TransferMarketState.pos_filter,
                TransferMarketState.set_pos_filter,
            ),
            # Rank Targets By
            filter_select(
                "Rank Targets By",
                [
                    "Projected Points (xP)",
                    "Value Efficiency (xP / £M)",
                    "Current Form",
                    "Total Season Points",
                    "Price (Low to High)",
                    "Ownership % (Low to High)",
                ],
                TransferMarketState.sort_by,
                TransferMarketState.set_sort_by,
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="3"),
            spacing="3",
            width="100%",
            align_items="end",
        ),
        # Row 2: Target Max Price Slider, Exclude My Squad Toggle, Apply Betting Odds Toggle
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.text("Target Max Price (£M)", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        rx.concat("£", TransferMarketState.max_price),
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
                    value=[TransferMarketState.max_price],
                    on_value_commit=TransferMarketState.set_max_price,
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
                    checked=TransferMarketState.exclude_my_squad,
                    on_change=TransferMarketState.toggle_exclude,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("ban", size=15, color="var(--text-sub)"),
                    rx.text("Exclude My Squad", font_size="0.85rem", color="var(--text-sub)", font_weight="600"),
                    align="center",
                    spacing="1",
                ),
                align="center",
                spacing="2",
            ),
            rx.hstack(
                rx.switch(
                    checked=TransferMarketState.enable_betting,
                    on_change=TransferMarketState.toggle_betting,
                    color_scheme="green",
                    size="1",
                ),
                rx.hstack(
                    rx.icon("bar-chart-2", size=15, color="var(--text-sub)"),
                    rx.text("Apply Betting Odds", font_size="0.85rem", color="var(--text-sub)", font_weight="600"),
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
            gap="1.25rem",
        ),
        width="100%",
        spacing="3",
        padding="1rem",
        background="var(--gray-2)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        margin_bottom="1.25rem",
    )


def transfer_market_page() -> rx.Component:
    """Renders the Transfer Market tab view."""
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
                    rx.text("Transfer Target Finder", class_name="section-header-title"),
                    rx.text(
                        "Identify high-EV incoming transfer targets ranked by projected points and value efficiency",
                        class_name="section-header-sub",
                    ),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Transfer Target Finder",
                    subtitle="Identify high-EV incoming transfer targets ranked by projected points and value efficiency",
                    items=[
                        {
                            "badge": "Hybrid xP",
                            "title": "Projected Points (Proj xP)",
                            "desc": "Hybrid projection blending baseline statistical rates, betting market implied goals, and sharp line velocity.",
                            "color": "#38bdf8",
                        },
                        {
                            "badge": "xP / £M",
                            "title": "Points Value Efficiency",
                            "desc": "Expected points generated per million pounds spent. Highlights budget gems that liberate bank budget for premiums.",
                            "color": "#10b981",
                        },
                        {
                            "badge": "Price Trends",
                            "title": "Nightly Price Dynamics",
                            "desc": "Identifies players with rising/falling price predictions driven by official FPL net transfer velocity.",
                            "color": "#f59e0b",
                        },
                        {
                            "badge": "Budget Cap",
                            "title": "Max Price Slider",
                            "desc": "Set your exact bank constraints to display the highest projected replacements within your price range.",
                            "color": "#818cf8",
                        },
                        {
                            "badge": "Exclude Squad",
                            "title": "Ownership Filter",
                            "desc": "Automatically hides players already in your current squad so you only evaluate genuine replacement targets.",
                            "color": "#f59e0b",
                        },
                    ],
                    tip="Sort by xP / £M within your exact price ceiling to find under-the-radar enablers with favorable upcoming runs.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=TransferMarketState.refresh_data,
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

        # Filter Bar
        market_controls(),

        # Top Targets Highlight Cards (isolated)
        market_metric_cards(),

        # Data Table with Player Avatars, Price Trends, and Streamlit Columns
        data_table(
            headers=TransferMarketState.columns,
            rows=TransferMarketState.table_data,
            row_render_func=lambda row: rx.table.row(
                # Target Player (with Avatar)
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
                    padding_left="1rem",
                ),
                # Club
                rx.table.cell(rx.text(row["Team"], font_size="0.85rem")),
                # Pos
                rx.table.cell(rx.badge(row["Pos"], variant="outline", color_scheme=row["Pos_Color"], size="1")),
                # Price
                rx.table.cell(rx.text(row["Price_Display"], font_weight="600")),
                # Price Trend (increasing/decreasing badge)
                rx.table.cell(
                    rx.badge(
                        row["Price_Trend_Label"],
                        variant="surface",
                        color_scheme=row["Price_Trend_Color"],
                        size="1",
                        font_weight="600",
                    )
                ),
                # GW Fixture
                rx.table.cell(rx.text(row["Fixture"])),
                # FDR
                rx.table.cell(
                    rx.badge(row["FDR"], variant="surface", color_scheme=row["FDR_Color"], size="1", font_weight="700")
                ),
                # Proj xP
                rx.table.cell(
                    rx.badge(row["Proj_xP"], variant="surface", color_scheme="green", size="1", font_weight="700")
                ),
                # xP / £M
                rx.table.cell(rx.text(row["xP_per_Mil"], font_weight="700")),
                # Form
                rx.table.cell(rx.text(row["Form"])),
                # Own %
                rx.table.cell(rx.text(row["Own_Pct"])),
                # Season Pts
                rx.table.cell(rx.text(row["Season_Points"])),
            ),
            is_loading=TransferMarketState.is_loading,
        ),
        width="100%",
        on_mount=TransferMarketState.load_data,
    )
