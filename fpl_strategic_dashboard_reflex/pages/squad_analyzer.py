"""Squad Analyzer Page - Tactical lineup analysis, pitch formation, and market analytics."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.squad import SquadAnalyzerState
from fpl_strategic_dashboard_reflex.components import (
    tour_button,
    metric_card,
    pitch_view,
    squad_list_view,
    loading_view,
    MotionDiv,
    AnimatePresence,
    directional_slide,
    count_up,
    rating_ring,
)


def model_vs_market_table() -> rx.Component:
    """Renders the Model vs Market discrepancy table."""
    return rx.box(
        rx.hstack(
            rx.icon("scale", size=18, color="#38bdf8"),
            rx.vstack(
                rx.text("Model vs Market", font_size="1rem", font_weight="700", color="var(--text-main)"),
                rx.text("Key divergence points where bookmaker pricing deviates from statistical projections", font_size="0.75rem", color="var(--text-sub)"),
                spacing="0",
                align="start",
            ),
            align="center",
            spacing="2",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            SquadAnalyzerState.has_market_disagreements,
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Club"),
                            rx.table.column_header_cell("Fixture"),
                            rx.table.column_header_cell("Model xG"),
                            rx.table.column_header_cell("Market xG"),
                            rx.table.column_header_cell("Diff"),
                            rx.table.column_header_cell("CS Prob"),
                            rx.table.column_header_cell("Verdict"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            SquadAnalyzerState.market_disagreements,
                            lambda r: rx.table.row(
                                rx.table.cell(rx.badge(r["Club"], variant="solid", color_scheme="gray", size="1")),
                                rx.table.cell(rx.text(r["Fixture"], font_weight="500", font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Model_xG"], font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Market_xG"], font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Diff"], color=r["Diff_Color"], font_weight="700", font_size="0.8rem")),
                                rx.table.cell(rx.text(r["CS_Prob"], font_size="0.8rem")),
                                rx.table.cell(rx.badge(r["Verdict"], color_scheme=r["Verdict_Color"], variant="surface", size="1")),
                            ),
                        ),
                    ),
                    variant="surface",
                    size="1",
                    width="100%",
                ),
                overflow_x="auto",
                width="100%",
            ),
            rx.center(
                rx.hstack(
                    rx.icon("info", size=15, color="var(--text-muted)"),
                    rx.text("No large divergence (≥0.30 xG) between Model & Bookmakers for your squad's fixtures.", font_size="0.8rem", color="var(--text-muted)"),
                    align="center",
                    spacing="2",
                    padding="1.25rem",
                ),
                width="100%",
                background="rgba(255, 255, 255, 0.01)",
                border_radius="8px",
            ),
        ),
        padding="1rem",
        background="var(--surface-1, rgba(255, 255, 255, 0.035))",
        border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
        border_radius="10px",
        width="100%",
        id="tour-model-market-table",
        custom_attrs={"data-tour-id": "tour-model-market-table"},
    )


def line_movement_table() -> rx.Component:
    """Renders the Line Movement (Open vs Now) odds velocity table."""
    return rx.box(
        rx.hstack(
            rx.icon("zap", size=18, color="#eab308"),
            rx.vstack(
                rx.text("Line Movement (Open vs Now)", font_size="1rem", font_weight="700", color="var(--text-main)"),
                rx.text("Real-time betting velocity, market shortenings, and late sharp money signals", font_size="0.75rem", color="var(--text-sub)"),
                spacing="0",
                align="start",
            ),
            align="center",
            spacing="2",
            margin_bottom="0.75rem",
        ),
        rx.cond(
            SquadAnalyzerState.has_market_movements,
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell("Club"),
                            rx.table.column_header_cell("Fixture"),
                            rx.table.column_header_cell("Open xG"),
                            rx.table.column_header_cell("Current xG"),
                            rx.table.column_header_cell("Δ xG"),
                            rx.table.column_header_cell("Trend"),
                            rx.table.column_header_cell("Signal"),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            SquadAnalyzerState.market_movements,
                            lambda r: rx.table.row(
                                rx.table.cell(rx.badge(r["Club"], variant="solid", color_scheme="gray", size="1")),
                                rx.table.cell(rx.text(r["Fixture"], font_weight="500", font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Open_xG"], font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Current_xG"], font_size="0.8rem")),
                                rx.table.cell(rx.text(r["Delta_xG"], color=r["Delta_Color"], font_weight="700", font_size="0.8rem")),
                                rx.table.cell(rx.badge(r["Trend"], color_scheme=r["Trend_Color"], variant="surface", size="1")),
                                rx.table.cell(rx.text(r["Signal"], font_size="0.75rem", color="var(--text-sub)")),
                            ),
                        ),
                    ),
                    variant="surface",
                    size="1",
                    width="100%",
                ),
                overflow_x="auto",
                width="100%",
            ),
            rx.center(
                rx.hstack(
                    rx.icon("info", size=15, color="var(--text-muted)"),
                    rx.text("No significant line movement observed yet for current fixtures.", font_size="0.8rem", color="var(--text-muted)"),
                    align="center",
                    spacing="2",
                    padding="1.25rem",
                ),
                width="100%",
                background="rgba(255, 255, 255, 0.01)",
                border_radius="8px",
            ),
        ),
        padding="1rem",
        background="var(--surface-1, rgba(255, 255, 255, 0.035))",
        border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
        border_radius="10px",
        width="100%",
    )


def match_center_banner() -> rx.Component:
    """Renders the Live Match Center / Performance Review / Squad Rating header banner."""
    rating_color = rx.cond(
        SquadAnalyzerState.banner_diff_color == "green",
        "var(--color-positive, #22c55e)",
        rx.cond(SquadAnalyzerState.banner_diff_color == "red", "var(--color-negative, #ef4444)", "var(--color-interactive, #38bdf8)"),
    )
    return rx.cond(
        SquadAnalyzerState.show_banner,
        rx.box(
            rx.hstack(
                rx.hstack(
                    rx.box(
                        rx.icon(
                            rx.cond(
                                SquadAnalyzerState.is_live_or_finished,
                                "activity",
                                "gauge",
                            ),
                            size=20,
                            color=rating_color,
                        ),
                        padding="0.5rem",
                        background=rx.cond(
                            SquadAnalyzerState.banner_diff_color == "green",
                            "var(--color-positive-subtle, rgba(34, 197, 94, 0.12))",
                            rx.cond(SquadAnalyzerState.banner_diff_color == "red", "var(--color-negative-subtle, rgba(239, 68, 68, 0.12))", "var(--color-interactive-subtle, rgba(56, 189, 248, 0.12))"),
                        ),
                        border_radius="8px",
                    ),
                    rx.vstack(
                        rx.text(SquadAnalyzerState.banner_title, font_size="1.1rem", font_weight="700", color="var(--text-main)"),
                        rx.text(SquadAnalyzerState.banner_subtext, font_size="0.82rem", color="var(--text-sub)"),
                        align="start",
                        spacing="1",
                    ),
                    align="center",
                    spacing="3",
                ),
                rx.spacer(),
                rx.cond(
                    SquadAnalyzerState.banner_diff_text != "",
                    rx.hstack(
                        # Circular Rating Ring for GW6 Squad Rating (pathLength animated via whileInView)
                        rx.cond(
                            ~SquadAnalyzerState.is_live_or_finished,
                            rating_ring(
                                value=SquadAnalyzerState.banner_rating_ratio,
                                color=rating_color,
                                size=44,
                            ),
                            rx.box(),
                        ),
                        rx.box(
                            count_up(
                                value=SquadAnalyzerState.banner_diff_text,
                                duration=0.8,
                                decimals=1,
                                style={
                                    "fontSize": "1.4rem",
                                    "fontWeight": "800",
                                    "color": rating_color,
                                    "fontFamily": "'Outfit', sans-serif",
                                },
                            ),
                            padding="0.3rem 0.85rem",
                            background=rx.cond(
                                SquadAnalyzerState.banner_diff_color == "green",
                                "rgba(34, 197, 94, 0.12)",
                                rx.cond(SquadAnalyzerState.banner_diff_color == "red", "rgba(239, 68, 68, 0.12)", "rgba(255, 255, 255, 0.05)"),
                            ),
                            border="1px solid",
                            border_color=rx.cond(
                                SquadAnalyzerState.banner_diff_color == "green",
                                "rgba(34, 197, 94, 0.3)",
                                rx.cond(SquadAnalyzerState.banner_diff_color == "red", "rgba(239, 68, 68, 0.3)", "rgba(255, 255, 255, 0.1)"),
                            ),
                            border_radius="8px",
                        ),
                        align="center",
                        spacing="3",
                    ),
                    rx.box(),
                ),
                align="center",
                width="100%",
            ),
            # Animate the Squad Rating progress bar via width using whileInView (once: true)
            rx.cond(
                ~SquadAnalyzerState.is_live_or_finished & (SquadAnalyzerState.banner_diff_text != ""),
                rx.box(
                    MotionDiv.create(
                        initial={"width": "0%"},
                        while_in_view={"width": SquadAnalyzerState.banner_diff_text},
                        viewport={"once": True},
                        transition={"duration": 0.85, "ease": "easeOut"},
                        height="4px",
                        border_radius="2px",
                        background=rating_color,
                    ),
                    width="100%",
                    height="4px",
                    background="rgba(255, 255, 255, 0.08)",
                    border_radius="2px",
                    overflow="hidden",
                    margin_top="0.75rem",
                ),
                rx.box(),
            ),
            class_name="match-banner-card",
            padding="1rem 1.25rem",
            background="var(--surface-1, rgba(255, 255, 255, 0.035))",
            border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
            border_radius="10px",
            margin_bottom="1rem",
            width="100%",
            id="tour-squad-rating",
            custom_attrs={"data-tour-id": "tour-squad-rating"},
        ),
        rx.box(),
    )


def match_center_kpi_cards() -> rx.Component:
    """Renders the second layer of KPI metric cards (Net GW Points Live, Gameweek Rank, Players Played, Captain Points)."""
    return rx.cond(
        SquadAnalyzerState.show_banner,
        rx.grid(
            metric_card(
                SquadAnalyzerState.kpi2_card1_label,
                SquadAnalyzerState.kpi2_card1_val,
                delta=SquadAnalyzerState.kpi2_card1_delta,
                delta_color=SquadAnalyzerState.kpi2_card1_delta_color,
            ),
            metric_card(
                SquadAnalyzerState.kpi2_card2_label,
                SquadAnalyzerState.kpi2_card2_val,
                delta=SquadAnalyzerState.kpi2_card2_delta,
                delta_color=SquadAnalyzerState.kpi2_card2_delta_color,
            ),
            metric_card(
                SquadAnalyzerState.kpi2_card3_label,
                SquadAnalyzerState.kpi2_card3_val,
                delta=SquadAnalyzerState.kpi2_card3_delta,
                delta_color=SquadAnalyzerState.kpi2_card3_delta_color,
            ),
            metric_card(
                SquadAnalyzerState.kpi2_card4_label,
                SquadAnalyzerState.kpi2_card4_val,
                delta=SquadAnalyzerState.kpi2_card4_delta,
                delta_color=SquadAnalyzerState.kpi2_card4_delta_color,
            ),
            columns=rx.breakpoints(initial="1", sm="2", md="4"),
            spacing="3",
            width="100%",
            margin_bottom="1.25rem",
        ),
        rx.box(),
    )


def squad_lineup_tabs_content() -> rx.Component:
    """Renders pitch and list views with directional slide on Gameweek change (GW5->GW6 enters from right, reverse from left)."""
    pitch_content = rx.cond(
        SquadAnalyzerState.enable_comparison,
        rx.grid(
            pitch_view(SquadAnalyzerState.base_pitch_html, header_text=SquadAnalyzerState.squad_header_text),
            pitch_view(SquadAnalyzerState.comp_pitch_html, header_text=SquadAnalyzerState.comp_header_text),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="4",
            width="100%",
        ),
        pitch_view(SquadAnalyzerState.base_pitch_html, header_text=SquadAnalyzerState.squad_header_text),
    )

    list_content = rx.cond(
        SquadAnalyzerState.enable_comparison,
        rx.grid(
            squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench, header_text=SquadAnalyzerState.squad_header_text),
            squad_list_view(SquadAnalyzerState.compare_starters, SquadAnalyzerState.compare_bench, header_text=SquadAnalyzerState.comp_header_text),
            columns=rx.breakpoints(initial="1", md="2"),
            spacing="4",
            width="100%",
        ),
        squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench, header_text=SquadAnalyzerState.squad_header_text),
    )

    return rx.box(
        rx.tabs.content(
            AnimatePresence.create(
                directional_slide(
                    pitch_content,
                    direction=SquadAnalyzerState.gw_direction,
                    key=SquadAnalyzerState.selected_eval_label,
                ),
                mode="wait",
            ),
            value="pitch",
        ),
        rx.tabs.content(
            AnimatePresence.create(
                directional_slide(
                    list_content,
                    direction=SquadAnalyzerState.gw_direction,
                    key=SquadAnalyzerState.selected_eval_label,
                ),
                mode="wait",
            ),
            value="list",
        ),
        width="100%",
        id="tour-pitch-formation",
        custom_attrs={"data-tour-id": "tour-pitch-formation"},
    )


def squad_market_section() -> rx.Component:
    """Renders market divergence and velocity tables when betting overlay is enabled."""
    return rx.cond(
        SquadAnalyzerState.show_betting_controls & SquadAnalyzerState.enable_betting,
        MotionDiv.create(
            rx.vstack(
                rx.grid(
                    model_vs_market_table(),
                    line_movement_table(),
                    columns=rx.breakpoints(initial="1", lg="2"),
                    spacing="4",
                    width="100%",
                ),
                width="100%",
                margin_top="1rem",
            ),
            layout="position",
            initial={"opacity": 0, "y": 15},
            animate={"opacity": 1, "y": 0},
            transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
            width="100%",
        ),
        rx.box(),
    )


def squad_controls_bar() -> rx.Component:
    """Renders filter controls bar with client-side pitch/list toggle and market options."""
    return rx.box(
        rx.vstack(
            # Row 1: Gameweek Radio Selector & Refresh
            rx.hstack(
                rx.vstack(
                    rx.hstack(
                        rx.icon("calendar", size=14, color="var(--accent-9)"),
                        rx.text("Select Gameweek:", font_size="0.85rem", color="var(--text-primary)", font_weight="600"),
                        align="center",
                        spacing="1",
                    ),
                    rx.radio_group(
                        SquadAnalyzerState.gw_labels,
                        value=SquadAnalyzerState.selected_eval_label,
                        on_change=SquadAnalyzerState.set_eval_label,
                        direction="row",
                        color_scheme="blue",
                        size="2",
                    ),
                    align="start",
                    spacing="2",
                    id="tour-select-gw",
                    custom_attrs={"data-tour-id": "tour-select-gw"},
                ),
                rx.spacer(),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh", font_size="0.85rem"),
                        align="center",
                        spacing="1",
                    ),
                    variant="surface",
                    color_scheme="gray",
                    size="2",
                    on_click=SquadAnalyzerState.refresh_squad,
                    loading=SquadAnalyzerState.is_loading,
                ),
                width="100%",
                align="center",
                wrap="wrap",
                gap="1rem",
            ),
            rx.divider(border_color="rgba(255, 255, 255, 0.06)"),
            # Row 2: View Toggles, Comparison, Betting Market, Slider, Checkbox
            rx.hstack(
                # Segmented Client-Side Pitch vs List View Toggle
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.cond(
                            SquadAnalyzerState.pitch_view,
                            MotionDiv.create(
                                class_name="view-tab-active-indicator",
                                layout_id="view-indicator",
                                transition={"type": "spring", "stiffness": 380, "damping": 30},
                            ),
                        ),
                        rx.hstack(
                            rx.icon("layout-grid", size=14),
                            rx.text("Pitch View"),
                            align="center",
                            spacing="1",
                            class_name="view-tab-label",
                        ),
                        value="pitch",
                        class_name="view-trigger-custom",
                    ),
                    rx.tabs.trigger(
                        rx.cond(
                            ~SquadAnalyzerState.pitch_view,
                            MotionDiv.create(
                                class_name="view-tab-active-indicator",
                                layout_id="view-indicator",
                                transition={"type": "spring", "stiffness": 380, "damping": 30},
                            ),
                        ),
                        rx.hstack(
                            rx.icon("list", size=14),
                            rx.text("List View"),
                            align="center",
                            spacing="1",
                            class_name="view-tab-label",
                        ),
                        value="list",
                        class_name="view-trigger-custom",
                    ),
                    id="tour-view-toggle",
                    custom_attrs={"data-tour-id": "tour-view-toggle"},
                ),
                # Comparison Switch
                rx.hstack(
                    rx.switch(
                        checked=SquadAnalyzerState.enable_comparison,
                        on_change=SquadAnalyzerState.set_enable_comparison,
                        color_scheme="blue",
                        size="2",
                    ),
                    rx.hstack(
                        rx.icon("scale", size=14, color="#38bdf8"),
                        rx.text("Comparison", font_size="0.85rem", font_weight="600"),
                        align="center",
                        spacing="1",
                    ),
                    align="center",
                    spacing="2",
                    id="tour-comparison-toggle",
                    custom_attrs={"data-tour-id": "tour-comparison-toggle"},
                ),
                # Super Team Switch (Visible when Comparison is enabled)
                rx.cond(
                    SquadAnalyzerState.enable_comparison,
                    MotionDiv.create(
                        rx.hstack(
                            rx.switch(
                                checked=SquadAnalyzerState.super_team_mode,
                                on_change=SquadAnalyzerState.set_super_team_mode,
                                color_scheme="amber",
                                size="2",
                            ),
                            rx.hstack(
                                rx.icon("star", size=14, color="#f59e0b"),
                                rx.text("Super Team", font_size="0.85rem", font_weight="600"),
                                align="center",
                                spacing="1",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        layout="position",
                        initial={"opacity": 0, "scale": 0.95},
                        animate={"opacity": 1, "scale": 1},
                        transition={"duration": 0.2},
                        id="tour-super-team-toggle",
                        custom_attrs={"data-tour-id": "tour-super-team-toggle"},
                    ),
                    rx.box(),
                ),
                # Betting Market Options (Hidden in Finished or Live Gameweeks)
                rx.cond(
                    SquadAnalyzerState.show_betting_controls,
                    rx.hstack(
                        rx.hstack(
                            rx.switch(
                                checked=SquadAnalyzerState.enable_betting,
                                on_change=SquadAnalyzerState.set_enable_betting,
                                color_scheme="blue",
                                size="2",
                            ),
                            rx.hstack(
                                rx.icon("trending-up", size=14, color="#38bdf8"),
                                rx.text("Betting Market", font_size="0.85rem", font_weight="600"),
                                align="center",
                                spacing="1",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        # Market Weight Slider (Visible when Betting Market is enabled)
                        rx.cond(
                            SquadAnalyzerState.enable_betting,
                            rx.hstack(
                                rx.vstack(
                                    rx.hstack(
                                        rx.text("Market Weight", font_size="0.75rem", color="var(--text-sub)"),
                                        rx.tooltip(
                                            rx.icon("circle-help", size=12, color="var(--text-muted)"),
                                            content="0.0 = 100% Statistical Model | 1.0 = 100% Bookmaker Odds",
                                        ),
                                        rx.text(SquadAnalyzerState.market_weight_display, font_size="0.8rem", font_weight="700", color="#38bdf8"),
                                        align="center",
                                        spacing="1",
                                    ),
                                    rx.slider(
                                        value=SquadAnalyzerState.market_weight_pct,
                                        min=0,
                                        max=100,
                                        step=5,
                                        width="110px",
                                        color_scheme="blue",
                                        size="1",
                                        on_change=SquadAnalyzerState.set_market_weight_drag,
                                        on_value_commit=SquadAnalyzerState.set_market_weight,
                                    ),
                                    spacing="1",
                                    align="start",
                                ),
                                align="center",
                                padding_x="0.25rem",
                            ),
                            rx.box(),
                        ),
                        # Line Movement Checkbox (Visible when Betting Market is enabled)
                        rx.cond(
                            SquadAnalyzerState.enable_betting,
                            rx.hstack(
                                rx.icon("zap", size=14, color="#38bdf8"),
                                rx.checkbox(
                                    "Line Movement",
                                    checked=SquadAnalyzerState.factor_movement,
                                    on_change=SquadAnalyzerState.set_factor_movement,
                                    color_scheme="blue",
                                    size="2",
                                ),
                                align="center",
                                spacing="1",
                            ),
                            rx.box(),
                        ),
                        align="center",
                        spacing="4",
                        id="tour-betting-controls",
                        custom_attrs={"data-tour-id": "tour-betting-controls"},
                    ),
                    rx.box(),
                ),
                width="100%",
                align="center",
                wrap="wrap",
                gap="1.25rem",
            ),
            width="100%",
            spacing="3",
        ),
        padding="1rem 1.25rem",
        background="var(--surface-1, rgba(255, 255, 255, 0.035))",
        border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
        border_radius="10px",
        margin_bottom="1.5rem",
        width="100%",
    )


def squad_content_section() -> rx.Component:
    """Renders main content: Loading overlay vs Squad Pitch/List + Market section."""
    return rx.cond(
        SquadAnalyzerState.is_loading,
        loading_view(
            status_message=SquadAnalyzerState.status_message,
            title="Optimizing Tactical Formation",
            badge_text="TACTICAL ENGINE",
        ),
        rx.cond(
            SquadAnalyzerState.has_data,
            rx.vstack(
                match_center_banner(),
                match_center_kpi_cards(),
                squad_lineup_tabs_content(),
                squad_market_section(),
                width="100%",
                spacing="4",
            ),
            rx.center(
                rx.vstack(
                    rx.icon("user-x", size=32, color="var(--text-muted)"),
                    rx.text("No squad data found. Enter your FPL Team ID in the header to load your team.", font_size="0.9rem", color="var(--text-sub)"),
                    rx.button("Enter FPL Team ID", on_click=SquadAnalyzerState.open_id_dialog, variant="solid", color_scheme="blue", size="2"),
                    align="center",
                    spacing="3",
                ),
                padding="4rem",
                width="100%",
            ),
        ),
    )


def squad_analyzer_page() -> rx.Component:
    """Renders the Squad Analyzer page view with client-side tabs."""
    return rx.tabs.root(
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
                    rx.text("Active Squad & Pitch Formation", class_name="section-header-title"),
                    rx.text("Analyze tactical team structure, expected points distribution, captaincy choices, and benchmark against Dream 15.", class_name="section-header-sub"),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.spacer(),
            tour_button("squad_analyzer"),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),
        squad_controls_bar(),
        squad_content_section(),
        value=rx.cond(SquadAnalyzerState.pitch_view, "pitch", "list"),
        on_change=SquadAnalyzerState.set_view_mode,
        class_name="segmented-view-tabs",
        width="100%",
        on_mount=SquadAnalyzerState.load_squad,
    )
