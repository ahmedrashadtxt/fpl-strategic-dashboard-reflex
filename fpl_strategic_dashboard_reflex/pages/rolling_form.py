"""Rolling Form Page - Moving averages, momentum analysis, and fixture opportunity mapping."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.rolling import RollingFormState
from fpl_strategic_dashboard_reflex.components import (
    tour_button,
    player_highlight_card,
    data_table,
    search_input,
    filter_select,
    MotionDiv,
)


def rolling_metric_cards() -> rx.Component:
    """Isolated player highlight cards component matching Streamlit layout."""
    return rx.box(
        rx.cond(
            RollingFormState.has_data,
            MotionDiv.create(
                rx.grid(
                    rx.foreach(
                        RollingFormState.top_cards,
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
        ),
        id="tour-form-kpis",
        custom_attrs={"data-tour-id": "tour-form-kpis"},
        width="100%",
    )


def rolling_form_controls() -> rx.Component:
    """Filter controls matching the Streamlit Rolling Form interface."""
    return rx.vstack(
        # Row 1: Search, Position, Rank By, Squad Filter
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
            # Position select
            filter_select(
                "Position",
                ["All", "GKP", "DEF", "MID", "FWD"],
                RollingFormState.position_filter,
                RollingFormState.set_pos,
                vertical=True,
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
                vertical=True,
                width="100%",
            ),
            # Squad toggle
            rx.vstack(
                rx.text("Squad Filter", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                rx.hstack(
                    rx.switch(
                        checked=RollingFormState.only_my_squad,
                        on_change=RollingFormState.set_only_squad,
                        color_scheme="blue",
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
                    height="32px",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="4"),
            spacing="3",
            width="100%",
            align_items="start",
        ),
        # Row 2: Match Window, Min Matches, Min Avg Mins, Max Price sliders
        rx.grid(
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
                rx.box(
                    rx.slider(
                        min=1,
                        max=10,
                        step=1,
                        value=RollingFormState.window_size_list,
                        on_change=RollingFormState.set_window_drag,
                        on_value_commit=RollingFormState.set_window,
                        color_scheme="blue",
                        size="1",
                        width="100%",
                    ),
                    width="100%",
                    height="32px",
                    display="flex",
                    align_items="center",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Min Matches slider
            rx.vstack(
                rx.hstack(
                    rx.text("Min Matches", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        RollingFormState.min_matches,
                        variant="surface",
                        color_scheme="blue",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.box(
                    rx.slider(
                        min=1,
                        max=10,
                        step=1,
                        value=RollingFormState.min_matches_list,
                        on_change=RollingFormState.set_min_matches_drag,
                        on_value_commit=RollingFormState.set_min_matches,
                        color_scheme="blue",
                        size="1",
                        width="100%",
                    ),
                    width="100%",
                    height="32px",
                    display="flex",
                    align_items="center",
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
                        color_scheme="blue",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.box(
                    rx.slider(
                        min=0,
                        max=90,
                        step=15,
                        value=RollingFormState.min_avg_mins_list,
                        on_change=RollingFormState.set_min_mins_drag,
                        on_value_commit=RollingFormState.set_min_mins,
                        color_scheme="blue",
                        size="1",
                        width="100%",
                    ),
                    width="100%",
                    height="32px",
                    display="flex",
                    align_items="center",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            # Filter Max Price slider
            rx.vstack(
                rx.hstack(
                    rx.text("Filter Max Price (£M)", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.badge(
                        rx.concat("£", RollingFormState.max_price),
                        variant="surface",
                        color_scheme="blue",
                        size="1",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.box(
                    rx.slider(
                        min=4.0,
                        max=17.0,
                        step=0.5,
                        value=RollingFormState.max_price_list,
                        on_change=RollingFormState.set_price_drag,
                        on_value_commit=RollingFormState.set_price,
                        color_scheme="blue",
                        size="1",
                        width="100%",
                    ),
                    width="100%",
                    height="32px",
                    display="flex",
                    align_items="center",
                ),
                align="start",
                spacing="1",
                width="100%",
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="4"),
            spacing="3",
            width="100%",
            align_items="start",
        ),
        width="100%",
        spacing="3",
        padding="1rem",
        background="var(--surface-1, rgba(255, 255, 255, 0.035))",
        border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
        border_radius="10px",
        margin_bottom="1.25rem",
        overflow="hidden",
        id="tour-form-filters",
        custom_attrs={"data-tour-id": "tour-form-filters"},
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
            rx.spacer(),
            rx.hstack(
                tour_button("rolling_form"),
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
                min_width="0",
                background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                border_radius="10px",
                padding="0.5rem",
                margin_bottom="1.25rem",
                overflow="hidden",
                id="tour-form-scatter",
                custom_attrs={"data-tour-id": "tour-form-scatter"},
            ),
            rx.box(),
        ),

        # Top Highlight Cards
        rolling_metric_cards(),

        # Data Table with Player Avatars and Streamlit Columns
        rx.box(
            data_table(
                headers=RollingFormState.columns,
                rows=RollingFormState.table_data,
                sort_col=RollingFormState.sort_column,
                sort_dir=RollingFormState.sort_direction,
                on_sort=RollingFormState.handle_sort,
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
            id="tour-form-table",
            custom_attrs={"data-tour-id": "tour-form-table"},
            width="100%",
        ),
        width="100%",
        on_mount=RollingFormState.load_data,
    )
