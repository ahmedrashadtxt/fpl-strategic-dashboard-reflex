"""Squad Analyzer Page - Tactical lineup analysis, pitch formation, and market analytics."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.squad import SquadAnalyzerState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    pitch_view,
    squad_list_view,
    loading_view,
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
        background="rgba(15, 23, 42, 0.4)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        width="100%",
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
        background="rgba(15, 23, 42, 0.4)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        width="100%",
    )


def match_center_banner() -> rx.Component:
    """Renders the Live Match Center / Performance Review / Squad Rating header banner."""
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
                            color=rx.cond(
                                SquadAnalyzerState.banner_diff_color == "green",
                                "#22c55e",
                                rx.cond(SquadAnalyzerState.banner_diff_color == "red", "#ef4444", "#38bdf8"),
                            ),
                        ),
                        padding="0.5rem",
                        background=rx.cond(
                            SquadAnalyzerState.banner_diff_color == "green",
                            "rgba(34, 197, 94, 0.12)",
                            rx.cond(SquadAnalyzerState.banner_diff_color == "red", "rgba(239, 68, 68, 0.12)", "rgba(56, 189, 248, 0.12)"),
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
                    rx.box(
                        rx.text(
                            SquadAnalyzerState.banner_diff_text,
                            font_size="1.4rem",
                            font_weight="800",
                            color=rx.cond(
                                SquadAnalyzerState.banner_diff_color == "green",
                                "#22c55e",
                                rx.cond(SquadAnalyzerState.banner_diff_color == "red", "#ef4444", "var(--text-main)"),
                            ),
                            font_family="'Outfit', sans-serif",
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
                    rx.box(),
                ),
                align="center",
                width="100%",
            ),
            padding="1rem 1.25rem",
            background="rgba(255, 255, 255, 0.02)",
            border="1px solid var(--border-color)",
            border_radius="10px",
            margin_bottom="1rem",
            width="100%",
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
    """Renders pitch and list views as client-side tabs content with zero round-trip latency."""
    return rx.box(
        rx.tabs.content(
            rx.cond(
                SquadAnalyzerState.enable_comparison,
                rx.grid(
                    pitch_view(SquadAnalyzerState.base_pitch_html, header_text=SquadAnalyzerState.squad_header_text),
                    pitch_view(SquadAnalyzerState.comp_pitch_html, header_text=SquadAnalyzerState.comp_header_text),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="4",
                    width="100%",
                ),
                pitch_view(SquadAnalyzerState.base_pitch_html, header_text=SquadAnalyzerState.squad_header_text),
            ),
            value="pitch",
        ),
        rx.tabs.content(
            rx.cond(
                SquadAnalyzerState.enable_comparison,
                rx.grid(
                    squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench, header_text=SquadAnalyzerState.squad_header_text),
                    squad_list_view(SquadAnalyzerState.compare_starters, SquadAnalyzerState.compare_bench, header_text=SquadAnalyzerState.comp_header_text),
                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="4",
                    width="100%",
                ),
                squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench, header_text=SquadAnalyzerState.squad_header_text),
            ),
            value="list",
        ),
        width="100%",
    )


def squad_market_section() -> rx.Component:
    """Renders market divergence and velocity tables when betting overlay is enabled."""
    return rx.cond(
        SquadAnalyzerState.show_betting_controls & SquadAnalyzerState.enable_betting,
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
        rx.box(),
    )


def squad_controls_bar() -> rx.Component:
    """Renders filter controls bar with client-side pitch/list toggle and market options."""
    return rx.box(
        rx.vstack(
            # Row 1: Gameweek Radio Selector & Refresh
            rx.hstack(
                rx.vstack(
                    rx.text("📅 Select Gameweek:", font_size="0.85rem", color="var(--text-primary)", font_weight="600"),
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
                        color_scheme="green",
                        size="2",
                    ),
                    align="start",
                    spacing="2",
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
                        rx.hstack(
                            rx.icon("layout-grid", size=14),
                            rx.text("Pitch View"),
                            align="center",
                            spacing="1",
                        ),
                        value="pitch",
                    ),
                    rx.tabs.trigger(
                        rx.hstack(
                            rx.icon("list", size=14),
                            rx.text("List View"),
                            align="center",
                            spacing="1",
                        ),
                        value="list",
                    ),
                ),
                # Comparison Switch
                rx.hstack(
                    rx.switch(
                        checked=SquadAnalyzerState.enable_comparison,
                        on_change=SquadAnalyzerState.set_enable_comparison,
                        color_scheme="cyan",
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
                ),
                # Super Team Switch (Visible when Comparison is enabled)
                rx.cond(
                    SquadAnalyzerState.enable_comparison,
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
                                color_scheme="green",
                                size="2",
                            ),
                            rx.hstack(
                                rx.icon("trending-up", size=14, color="#4ade80"),
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
                                        rx.text(SquadAnalyzerState.market_weight_display, font_size="0.8rem", font_weight="700", color="#4ade80"),
                                        align="center",
                                        spacing="1",
                                    ),
                                    rx.slider(
                                        value=SquadAnalyzerState.market_weight_pct,
                                        min=0,
                                        max=100,
                                        step=5,
                                        width="110px",
                                        color_scheme="green",
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
                                rx.icon("zap", size=14, color="#eab308"),
                                rx.checkbox(
                                    "Line Movement",
                                    checked=SquadAnalyzerState.factor_movement,
                                    on_change=SquadAnalyzerState.set_factor_movement,
                                    color_scheme="green",
                                    size="2",
                                ),
                                align="center",
                                spacing="1",
                            ),
                            rx.box(),
                        ),
                        align="center",
                        spacing="4",
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
        background="rgba(255, 255, 255, 0.02)",
        border="1px solid var(--border-color)",
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
            guide_popover(
                title="Squad Analyzer Guide",
                subtitle="Tactical lineup and formation optimization",
                items=[
                    {"badge": "Pitch View", "title": "Tactical Formation", "desc": "Interactive 2D pitch showing player roles, fixture FDR ratings, and projected xP."},
                    {"badge": "Comparison", "title": "Dream 15 Benchmark", "desc": "Compare your starting XI against the mathematically optimal budget Dream 15."},
                    {"badge": "Betting Market", "title": "Market Overlay", "desc": "Blend statistical models with bookmaker odds and real-time line movement."},
                ],
                tip="Click on any player shirt on the pitch to view detailed underlying metric popups.",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),
        squad_controls_bar(),
        squad_content_section(),
        default_value="pitch",
        class_name="segmented-view-tabs",
        width="100%",
        on_mount=SquadAnalyzerState.load_squad,
    )
