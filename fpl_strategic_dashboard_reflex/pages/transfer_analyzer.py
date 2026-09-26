"""Transfer Analyzer / Solver Page - Pure presentation page layout."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.transfer import TransferAnalyzerState
from fpl_strategic_dashboard_reflex.components import (
    tour_button,
    pitch_view,
    squad_list_view,
    loading_view,
    MotionDiv,
)


def transfer_lineup_panel() -> rx.Component:
    """Renders current vs proposed squad lineup with client-side pitch/list toggle."""
    return MotionDiv.create(
        rx.tabs.root(
            rx.hstack(
                rx.hstack(
                    rx.icon("users", size=18, color="#60a5fa"),
                    rx.text(
                        rx.cond(
                            TransferAnalyzerState.has_solved,
                            "Squad Lineup Comparison (Current vs Proposed)",
                            "Current Squad Starting Lineup",
                        ),
                        font_size="1rem",
                        font_weight="700",
                        color="var(--text-main)",
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.spacer(),
                # Segmented Pitch View / List View Toggle (Client-Side)
                rx.tabs.list(
                    rx.tabs.trigger(
                        rx.cond(
                            TransferAnalyzerState.pitch_view,
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
                            ~TransferAnalyzerState.pitch_view,
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
                ),
                width="100%",
                align="center",
                margin_bottom="1rem",
            ),
            # Pitch Content
            rx.tabs.content(
                rx.cond(
                    TransferAnalyzerState.has_solved,
                    rx.grid(
                        pitch_view(TransferAnalyzerState.base_pitch_html, header_text="Current Squad Lineup"),
                        pitch_view(TransferAnalyzerState.comp_pitch_html, header_text="Proposed Transfer Squad"),
                        columns=rx.breakpoints(initial="1", md="2"),
                        spacing="4",
                        width="100%",
                    ),
                    pitch_view(TransferAnalyzerState.base_pitch_html, header_text="Current Squad Lineup"),
                ),
                value="pitch",
            ),
            # List Content
            rx.tabs.content(
                rx.cond(
                    TransferAnalyzerState.has_solved,
                    rx.grid(
                        squad_list_view(TransferAnalyzerState.base_starters, TransferAnalyzerState.base_bench, header_text="Current Squad Lineup"),
                        squad_list_view(TransferAnalyzerState.trans_starters, TransferAnalyzerState.trans_bench, header_text="Proposed Transfer Squad"),
                        columns=rx.breakpoints(initial="1", md="2"),
                        spacing="4",
                        width="100%",
                    ),
                    squad_list_view(TransferAnalyzerState.base_starters, TransferAnalyzerState.base_bench, header_text="Current Squad Lineup"),
                ),
                value="list",
            ),
            value=rx.cond(TransferAnalyzerState.pitch_view, "pitch", "list"),
            on_change=TransferAnalyzerState.set_view_mode,
            class_name="segmented-view-tabs",
            width="100%",
        ),
        layout="position",
        transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
        width="100%",
        id="tour-transfer-pitch",
        custom_attrs={"data-tour-id": "tour-transfer-pitch"},
    )


def transfer_solution_panel() -> rx.Component:
    """Renders solved strategy metrics and transfer swap cards."""
    return rx.cond(
        TransferAnalyzerState.has_solved,
        MotionDiv.create(
            rx.vstack(
                # Row of 4 Metric Cards
            rx.grid(
                # Metric 1: Starting XI xP
                rx.vstack(
                    rx.text(TransferAnalyzerState.solved_starting_title, font_size="0.75rem", color="var(--text-sub)"),
                    rx.hstack(
                        rx.text(TransferAnalyzerState.metric_starting_xp, font_size="1.25rem", font_weight="800", color="var(--text-main)"),
                        rx.badge(TransferAnalyzerState.metric_starting_delta, variant="surface", color_scheme="blue", size="1"),
                        align="center",
                        spacing="2",
                    ),
                    spacing="1",
                    padding="0.75rem 1rem",
                    background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                    border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                    border_radius="8px",
                    width="100%",
                ),
                # Metric 2: Net Projected Gain
                rx.vstack(
                    rx.text("Net Projected Gain", font_size="0.75rem", color="var(--text-sub)"),
                    rx.hstack(
                        rx.text(TransferAnalyzerState.metric_net_gain, font_size="1.25rem", font_weight="800", color="#38bdf8"),
                        rx.badge(
                            TransferAnalyzerState.metric_net_delta,
                            variant="surface",
                            color_scheme=rx.cond(TransferAnalyzerState.has_hit_penalty, "red", "green"),
                            size="1",
                        ),
                        align="center",
                        spacing="2",
                    ),
                    spacing="1",
                    padding="0.75rem 1rem",
                    background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                    border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                    border_radius="8px",
                    width="100%",
                ),
                # Metric 3: Remaining In Bank
                rx.vstack(
                    rx.text("Remaining In Bank", font_size="0.75rem", color="var(--text-sub)"),
                    rx.text(TransferAnalyzerState.metric_bank_after, font_size="1.25rem", font_weight="800", color="var(--text-main)"),
                    spacing="1",
                    padding="0.75rem 1rem",
                    background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                    border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                    border_radius="8px",
                    width="100%",
                ),
                # Metric 4: Moves Executed
                rx.vstack(
                    rx.text("Moves Executed", font_size="0.75rem", color="var(--text-sub)"),
                    rx.text(TransferAnalyzerState.metric_moves_executed, font_size="1.25rem", font_weight="800", color="var(--text-main)"),
                    spacing="1",
                    padding="0.75rem 1rem",
                    background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                    border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                    border_radius="8px",
                    width="100%",
                ),
                columns=rx.breakpoints(initial="1", sm="2", md="4"),
                spacing="3",
                width="100%",
                margin_bottom="1rem",
            ),
            # Strategy Header & Swaps
            rx.vstack(
                rx.hstack(
                    rx.icon("route", size=18, color="#38bdf8"),
                    rx.heading(TransferAnalyzerState.solved_route_title, size="4", weight="bold"),
                    align="center",
                    spacing="2",
                    margin_bottom="0.5rem",
                ),
                rx.cond(
                    TransferAnalyzerState.has_swaps,
                    rx.vstack(
                        rx.foreach(
                            TransferAnalyzerState.swaps,
                            lambda s: rx.grid(
                                # OUT card
                                rx.box(
                                    rx.vstack(
                                        rx.badge(
                                            rx.cond(s["forced_out"], "[!] FORCED SALE", "[OUT] TRANSFER OUT"),
                                            variant="surface",
                                            color_scheme="red",
                                            size="1",
                                            font_weight="800",
                                        ),
                                        rx.hstack(
                                            rx.text(s["out_name"], font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                                            rx.text("(", s["out_team"], ") · £", s["out_cost"], "m", font_size="0.8rem", color="var(--text-sub)"),
                                            align="baseline",
                                            spacing="1",
                                        ),
                                        rx.text(
                                            TransferAnalyzerState.horizon_len, "-GW xP: ", s["out_xp"], " xP",
                                            font_size="0.75rem",
                                            color="var(--text-muted)",
                                        ),
                                        spacing="1",
                                        align="start",
                                    ),
                                    padding="0.65rem 0.85rem",
                                    border_radius="8px",
                                    background="rgba(239, 68, 68, 0.08)",
                                    border="1px solid rgba(239, 68, 68, 0.25)",
                                    width="100%",
                                ),
                                # IN card
                                rx.box(
                                    rx.vstack(
                                        rx.badge(
                                            rx.cond(s["target"], "[TARGET] TARGET SIGNING", "[IN] TRANSFER IN"),
                                            variant="surface",
                                            color_scheme=rx.cond(s["target"], "blue", "green"),
                                            size="1",
                                            font_weight="800",
                                        ),
                                        rx.hstack(
                                            rx.text(s["in_name"], font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                                            rx.text("(", s["in_team"], ") · £", s["in_cost"], "m", font_size="0.8rem", color="var(--text-sub)"),
                                            align="baseline",
                                            spacing="1",
                                        ),
                                        rx.text(
                                            TransferAnalyzerState.horizon_len, "-GW xP: ", s["in_xp"], " xP",
                                            font_size="0.75rem",
                                            color="var(--text-muted)",
                                        ),
                                        spacing="1",
                                        align="start",
                                    ),
                                    padding="0.65rem 0.85rem",
                                    border_radius="8px",
                                    background=rx.cond(s["target"], "rgba(56, 189, 248, 0.08)", "rgba(34, 197, 94, 0.08)"),
                                    border=rx.cond(s["target"], "1px solid rgba(56, 189, 248, 0.3)", "1px solid rgba(34, 197, 94, 0.25)"),
                                    width="100%",
                                ),
                                # Delta card
                                rx.box(
                                    rx.vstack(
                                        rx.text("Expected Gain:", font_size="0.72rem", color="var(--text-sub)"),
                                        rx.text("+", s["gain"], " xP", font_size="1.1rem", font_weight="800", color="#38bdf8"),
                                        rx.text("Cost: £", s["cost_diff"], "m", font_size="0.72rem", color="var(--text-muted)"),
                                        spacing="1",
                                        align="center",
                                        justify="center",
                                    ),
                                    padding="0.65rem 0.85rem",
                                    border_radius="8px",
                                    background="rgba(15, 23, 42, 0.6)",
                                    border="1px solid rgba(255, 255, 255, 0.08)",
                                    width="100%",
                                    display="flex",
                                    align_items="center",
                                    justify_content="center",
                                ),
                                columns=rx.breakpoints(initial="1", md="3"),
                                spacing="3",
                                width="100%",
                            ),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                    rx.box(
                        rx.hstack(
                            rx.icon("circle-check", size=18, color="#4ade80"),
                            rx.text(
                                "Your current squad is optimal for this horizon. No transfer yields higher starting points within your budget.",
                                font_size="0.85rem",
                                color="#4ade80",
                                font_weight="500",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        padding="0.75rem 1rem",
                        border_radius="8px",
                        background="rgba(34, 197, 94, 0.08)",
                        border="1px solid rgba(34, 197, 94, 0.25)",
                        width="100%",
                    ),
                ),
                width="100%",
            ),
            width="100%",
            margin_bottom="1.25rem",
        ),
        layout="position",
        initial={"opacity": 0, "y": 15},
        animate={"opacity": 1, "y": 0},
        transition={"duration": 0.35, "ease": [0.16, 1, 0.3, 1]},
        width="100%",
    ),
    rx.box(),
)


def transfer_analyzer_page() -> rx.Component:
    """Renders the Transfer Solver page view."""
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
                    rx.text("Transfer Planner & Horizon Solver", class_name="section-header-title"),
                    rx.text(
                        "Formulate optimal multi-gameweek transfer routes with customized player locking and budget management",
                        class_name="section-header-sub",
                    ),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.spacer(),
            rx.hstack(
                tour_button("transfer_solver"),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=TransferAnalyzerState.refresh_planner,
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

        # Parameters & Horizon Card
        rx.box(
            rx.vstack(
                # Card Title
                rx.hstack(
                    rx.icon("settings", size=18, color="#38bdf8"),
                    rx.text("Parameters & Horizon", font_size="1.1rem", font_weight="700", color="var(--text-main)"),
                    align="center",
                    spacing="2",
                    margin_bottom="0.5rem",
                ),

                # Strategy Mode Radio
                rx.vstack(
                    rx.text("Strategy Mode:", font_size="0.8rem", font_weight="600", color="var(--text-sub)"),
                    rx.radio_group(
                        ["Regular Transfers", "Wildcard", "Free Hit"],
                        value=TransferAnalyzerState.strategy_mode,
                        on_change=TransferAnalyzerState.set_strategy_mode,
                        direction="row",
                        spacing="5",
                        size="2",
                        color_scheme="blue",
                    ),
                    align="start",
                    spacing="2",
                    margin_bottom="0.75rem",
                    id="tour-transfer-mode",
                    custom_attrs={"data-tour-id": "tour-transfer-mode"},
                ),

                # Row 1: Parameters Row (Regular Transfers = 4 cols, Wildcard/Free Hit = 2 cols)
                rx.cond(
                    TransferAnalyzerState.is_regular,
                    # 4-Column Grid for Regular Transfers
                    rx.grid(
                        # 1. Evaluation Horizon
                        rx.vstack(
                            rx.text("Evaluation Horizon", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.select(
                                TransferAnalyzerState.horizon_options,
                                value=TransferAnalyzerState.selected_horizon_label,
                                on_change=TransferAnalyzerState.set_horizon_label,
                                size="2",
                                variant="surface",
                                width="100%",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                            id="tour-transfer-horizon",
                            custom_attrs={"data-tour-id": "tour-transfer-horizon"},
                        ),

                        # 2. Free Transfers (+/- Stepper)
                        rx.vstack(
                            rx.text("Free Transfers", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.hstack(
                                rx.text(
                                    TransferAnalyzerState.ft_count.to_string(),
                                    font_size="0.95rem",
                                    font_weight="700",
                                    min_width="24px",
                                    text_align="center",
                                ),
                                rx.spacer(),
                                rx.icon_button(
                                    rx.icon("minus", size=14),
                                    variant="surface",
                                    color_scheme="gray",
                                    size="1",
                                    cursor="pointer",
                                    on_click=TransferAnalyzerState.decrement_fts,
                                ),
                                rx.icon_button(
                                    rx.icon("plus", size=14),
                                    variant="surface",
                                    color_scheme="gray",
                                    size="1",
                                    cursor="pointer",
                                    on_click=TransferAnalyzerState.increment_fts,
                                ),
                                align="center",
                                padding="0.35rem 0.6rem",
                                background="rgba(255, 255, 255, 0.03)",
                                border="1px solid var(--border-color)",
                                border_radius="8px",
                                width="100%",
                                height="32px",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                        ),

                        # 3. Max Hits (-4) (+/- Stepper)
                        rx.vstack(
                            rx.text("Max Hits (-4)", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.hstack(
                                rx.text(
                                    TransferAnalyzerState.max_hits.to_string(),
                                    font_size="0.95rem",
                                    font_weight="700",
                                    min_width="24px",
                                    text_align="center",
                                ),
                                rx.spacer(),
                                rx.icon_button(
                                    rx.icon("minus", size=14),
                                    variant="surface",
                                    color_scheme="gray",
                                    size="1",
                                    cursor="pointer",
                                    on_click=TransferAnalyzerState.decrement_max_hits,
                                ),
                                rx.icon_button(
                                    rx.icon("plus", size=14),
                                    variant="surface",
                                    color_scheme="gray",
                                    size="1",
                                    cursor="pointer",
                                    on_click=TransferAnalyzerState.increment_max_hits,
                                ),
                                align="center",
                                padding="0.35rem 0.6rem",
                                background="rgba(255, 255, 255, 0.03)",
                                border="1px solid var(--border-color)",
                                border_radius="8px",
                                width="100%",
                                height="32px",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                            id="tour-transfer-hits",
                            custom_attrs={"data-tour-id": "tour-transfer-hits"},
                        ),

                        # 4. Planned Moves Card
                        rx.vstack(
                            rx.text("Planned Moves", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.hstack(
                                rx.text(
                                    TransferAnalyzerState.planned_moves_text,
                                    font_size="0.95rem",
                                    font_weight="700",
                                    color="var(--text-main)",
                                ),
                                rx.cond(
                                    TransferAnalyzerState.has_hit_penalty,
                                    rx.badge(
                                        TransferAnalyzerState.hits_penalty_text,
                                        color_scheme="red",
                                        variant="surface",
                                        size="1",
                                    ),
                                    rx.box(),
                                ),
                                align="center",
                                spacing="2",
                                padding="0.35rem 0.75rem",
                                background="rgba(255, 255, 255, 0.03)",
                                border="1px solid var(--border-color)",
                                border_radius="8px",
                                width="100%",
                                height="32px",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                        ),

                        columns=rx.breakpoints(initial="1", sm="2", md="4"),
                        spacing="3",
                        width="100%",
                        align_items="end",
                        margin_bottom="1rem",
                    ),

                    # 2-Column Grid for Wildcard & Free Hit
                    rx.grid(
                        # 1. Evaluation Horizon
                        rx.vstack(
                            rx.text("Evaluation Horizon", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.select(
                                TransferAnalyzerState.horizon_options,
                                value=TransferAnalyzerState.selected_horizon_label,
                                on_change=TransferAnalyzerState.set_horizon_label,
                                size="2",
                                variant="surface",
                                width="100%",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                        ),

                        # 2. Available Budget Card
                        rx.vstack(
                            rx.text("Available Budget", font_size="0.75rem", font_weight="600", color="var(--text-sub)"),
                            rx.hstack(
                                rx.text(
                                    TransferAnalyzerState.team_val_display,
                                    font_size="0.95rem",
                                    font_weight="700",
                                    color="#4ade80",
                                ),
                                align="center",
                                padding="0.35rem 0.75rem",
                                background="rgba(255, 255, 255, 0.03)",
                                border="1px solid var(--border-color)",
                                border_radius="8px",
                                width="100%",
                                height="32px",
                            ),
                            align="start",
                            spacing="1",
                            width="100%",
                        ),

                        columns=rx.breakpoints(initial="1", sm="2"),
                        spacing="3",
                        width="100%",
                        align_items="end",
                        margin_bottom="1rem",
                    ),
                ),

                # Chip Active Banners
                rx.cond(
                    TransferAnalyzerState.is_wildcard,
                    rx.box(
                        rx.hstack(
                            rx.icon("sparkles", size=16, color="#38bdf8"),
                            rx.text(
                                "Wildcard Active: Optimizing a permanent 15-man squad over the selected horizon with 0 point deductions.",
                                font_size="0.85rem",
                                color="#38bdf8",
                                font_weight="500",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        padding="0.65rem 0.85rem",
                        border_radius="8px",
                        background="rgba(56, 189, 248, 0.08)",
                        border="1px solid rgba(56, 189, 248, 0.25)",
                        margin_bottom="1rem",
                        width="100%",
                    ),
                    rx.box(),
                ),
                rx.cond(
                    TransferAnalyzerState.is_free_hit,
                    rx.box(
                        rx.hstack(
                            rx.icon("zap", size=16, color="#eab308"),
                            rx.text(
                                "Free Hit Active: Optimizing a single-gameweek £100m+ roster with 0 point deductions. Reverts automatically next gameweek.",
                                font_size="0.85rem",
                                color="#facc15",
                                font_weight="500",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        padding="0.65rem 0.85rem",
                        border_radius="8px",
                        background="rgba(234, 179, 8, 0.08)",
                        border="1px solid rgba(234, 179, 8, 0.25)",
                        margin_bottom="1rem",
                        width="100%",
                    ),
                    rx.box(),
                ),

                # Row 2: Betting Market, Weight, Min Mins
                rx.grid(
                    # Betting Market Switch
                    rx.hstack(
                        rx.switch(
                            checked=TransferAnalyzerState.enable_betting,
                            on_change=TransferAnalyzerState.set_enable_betting,
                            color_scheme="blue",
                            size="2",
                        ),
                        rx.hstack(
                            rx.icon("trending-up", size=14, color="#38bdf8"),
                            rx.text("Betting Market xG", font_size="0.85rem", font_weight="600"),
                            align="center",
                            spacing="1",
                        ),
                        align="center",
                        spacing="2",
                    ),

                    # Market Weight Slider
                    rx.cond(
                        TransferAnalyzerState.enable_betting,
                        rx.vstack(
                            rx.hstack(
                                rx.text("Market Weight", font_size="0.75rem", color="var(--text-sub)"),
                                rx.tooltip(
                                    rx.icon("circle-help", size=12, color="var(--text-muted)"),
                                    content="0.0 = 100% Statistical Model | 1.0 = 100% Bookmaker Odds",
                                ),
                                rx.text(
                                    TransferAnalyzerState.market_weight_display,
                                    font_size="0.8rem",
                                    font_weight="700",
                                    color="#38bdf8",
                                ),
                                align="center",
                                spacing="1",
                            ),
                            rx.slider(
                                value=TransferAnalyzerState.market_weight_pct,
                                min=0,
                                max=100,
                                step=5,
                                width="100%",
                                color_scheme="blue",
                                size="1",
                                on_change=TransferAnalyzerState.set_market_weight_drag,
                                on_value_commit=TransferAnalyzerState.set_market_weight,
                            ),
                            spacing="1",
                            width="100%",
                            align="start",
                        ),
                        rx.box(),
                    ),

                    # Min Avg Mins / GW Slider
                    rx.vstack(
                        rx.hstack(
                            rx.text("Min Avg Mins / GW", font_size="0.75rem", color="var(--text-sub)"),
                            rx.tooltip(
                                rx.icon("circle-help", size=12, color="var(--text-muted)"),
                                content="Filters out fringe players and cameo risks from transfer suggestions",
                            ),
                            rx.text(
                                TransferAnalyzerState.min_mins.to_string(),
                                font_size="0.8rem",
                                font_weight="700",
                                color="#38bdf8",
                            ),
                            align="center",
                            spacing="1",
                        ),
                        rx.slider(
                            value=TransferAnalyzerState.min_mins_list,
                            min=0,
                            max=90,
                            step=5,
                            width="100%",
                            color_scheme="blue",
                            size="1",
                            on_change=TransferAnalyzerState.set_min_mins_drag,
                            on_value_commit=TransferAnalyzerState.set_min_mins,
                        ),
                        spacing="1",
                        width="100%",
                        align="start",
                    ),

                    columns=rx.breakpoints(initial="1", sm="3"),
                    spacing="4",
                    align_items="center",
                    width="100%",
                    margin_bottom="1.25rem",
                ),

                # Row 3: Priorities & Locks & Forced Sales & Blacklist
                rx.grid(
                    # Priorities & Locks
                    rx.vstack(
                        rx.hstack(
                            rx.text("Priorities & Locks", font_size="0.8rem", font_weight="600", color="var(--text-main)"),
                            rx.tooltip(
                                rx.icon("circle-help", size=12, color="var(--text-muted)"),
                                content="Select squad players you want to lock and market players you want to prioritize buying.",
                            ),
                            align="center",
                            spacing="1",
                        ),
                        rx.popover.root(
                            rx.popover.trigger(
                                rx.button(
                                    rx.hstack(
                                        rx.text(
                                            TransferAnalyzerState.pos_placeholder,
                                            font_size="0.85rem",
                                            color="var(--text-sub)",
                                        ),
                                        rx.spacer(),
                                        rx.icon("chevrons-up-down", size=14, color="var(--text-muted)"),
                                        width="100%",
                                        align="center",
                                    ),
                                    variant="surface",
                                    width="100%",
                                    size="2",
                                    cursor="pointer",
                                )
                            ),
                            rx.popover.content(
                                rx.vstack(
                                    rx.input(
                                        placeholder="Search players...",
                                        value=TransferAnalyzerState.pos_search,
                                        on_change=TransferAnalyzerState.set_pos_search,
                                        size="1",
                                        debounce_timeout=250,
                                        width="100%",
                                    ),
                                    rx.scroll_area(
                                        rx.cond(
                                            TransferAnalyzerState.has_pos_options,
                                            rx.vstack(
                                                rx.foreach(
                                                    TransferAnalyzerState.filtered_pos_options,
                                                    lambda opt: rx.hstack(
                                                        rx.checkbox(
                                                            checked=TransferAnalyzerState.selected_positive.contains(opt["id"]),
                                                            on_change=lambda _: TransferAnalyzerState.toggle_positive(opt["id"]),
                                                            size="1",
                                                        ),
                                                        rx.text(
                                                            opt["label"],
                                                            font_size="0.8rem",
                                                            cursor="pointer",
                                                            on_click=lambda: TransferAnalyzerState.toggle_positive(opt["id"]),
                                                        ),
                                                        spacing="2",
                                                        align="center",
                                                        width="100%",
                                                    ),
                                                ),
                                                spacing="1",
                                                align="start",
                                                width="100%",
                                            ),
                                            rx.box(
                                                rx.text("No matching players found", font_size="0.8rem", color="var(--text-muted)"),
                                                padding="0.75rem 0.5rem",
                                            ),
                                        ),
                                        max_height="220px",
                                        scrollbars="vertical",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="2",
                                ),
                                width="360px",
                            ),
                        ),
                        # Active Selected Badges
                        rx.cond(
                            TransferAnalyzerState.selected_positive.length() > 0,
                            rx.hstack(
                                rx.foreach(
                                    TransferAnalyzerState.selected_pos_items,
                                    lambda item: rx.badge(
                                        rx.hstack(
                                            rx.text(item["label"]),
                                            rx.icon(
                                                "x",
                                                size=11,
                                                cursor="pointer",
                                                on_click=lambda: TransferAnalyzerState.remove_positive(item["id"]),
                                            ),
                                            align="center",
                                            spacing="1",
                                        ),
                                        variant="surface",
                                        color_scheme="blue",
                                        size="1",
                                    ),
                                ),
                                rx.button(
                                    "Clear",
                                    variant="ghost",
                                    size="1",
                                    color_scheme="gray",
                                    on_click=TransferAnalyzerState.clear_positive,
                                ),
                                wrap="wrap",
                                spacing="1",
                                margin_top="0.35rem",
                            ),
                            rx.box(),
                        ),
                        align="start",
                        spacing="1",
                        width="100%",
                    ),

                    # Forced Sales & Blacklist
                    rx.vstack(
                        rx.hstack(
                            rx.text("Forced Sales & Blacklist", font_size="0.8rem", font_weight="600", color="var(--text-main)"),
                            rx.tooltip(
                                rx.icon("circle-help", size=12, color="var(--text-muted)"),
                                content="Select squad players you must sell and market players you refuse to buy.",
                            ),
                            align="center",
                            spacing="1",
                        ),
                        rx.popover.root(
                            rx.popover.trigger(
                                rx.button(
                                    rx.hstack(
                                        rx.text(
                                            TransferAnalyzerState.neg_placeholder,
                                            font_size="0.85rem",
                                            color="var(--text-sub)",
                                        ),
                                        rx.spacer(),
                                        rx.icon("chevrons-up-down", size=14, color="var(--text-muted)"),
                                        width="100%",
                                        align="center",
                                    ),
                                    variant="surface",
                                    width="100%",
                                    size="2",
                                    cursor="pointer",
                                )
                            ),
                            rx.popover.content(
                                rx.vstack(
                                    rx.input(
                                        placeholder="Search players...",
                                        value=TransferAnalyzerState.neg_search,
                                        on_change=TransferAnalyzerState.set_neg_search,
                                        size="1",
                                        debounce_timeout=250,
                                        width="100%",
                                    ),
                                    rx.scroll_area(
                                        rx.cond(
                                            TransferAnalyzerState.has_neg_options,
                                            rx.vstack(
                                                rx.foreach(
                                                    TransferAnalyzerState.filtered_neg_options,
                                                    lambda opt: rx.hstack(
                                                        rx.checkbox(
                                                            checked=TransferAnalyzerState.selected_negative.contains(opt["id"]),
                                                            on_change=lambda _: TransferAnalyzerState.toggle_negative(opt["id"]),
                                                            size="1",
                                                        ),
                                                        rx.text(
                                                            opt["label"],
                                                            font_size="0.8rem",
                                                            cursor="pointer",
                                                            on_click=lambda: TransferAnalyzerState.toggle_negative(opt["id"]),
                                                        ),
                                                        spacing="2",
                                                        align="center",
                                                        width="100%",
                                                    ),
                                                ),
                                                spacing="1",
                                                align="start",
                                                width="100%",
                                            ),
                                            rx.box(
                                                rx.text("No matching players found", font_size="0.8rem", color="var(--text-muted)"),
                                                padding="0.75rem 0.5rem",
                                            ),
                                        ),
                                        max_height="220px",
                                        scrollbars="vertical",
                                        width="100%",
                                    ),
                                    width="100%",
                                    spacing="2",
                                ),
                                width="360px",
                            ),
                        ),
                        # Active Selected Badges
                        rx.cond(
                            TransferAnalyzerState.selected_negative.length() > 0,
                            rx.hstack(
                                rx.foreach(
                                    TransferAnalyzerState.selected_neg_items,
                                    lambda item: rx.badge(
                                        rx.hstack(
                                            rx.text(item["label"]),
                                            rx.icon(
                                                "x",
                                                size=11,
                                                cursor="pointer",
                                                on_click=lambda: TransferAnalyzerState.remove_negative(item["id"]),
                                            ),
                                            align="center",
                                            spacing="1",
                                        ),
                                        variant="surface",
                                        color_scheme="red",
                                        size="1",
                                    ),
                                ),
                                rx.button(
                                    "Clear",
                                    variant="ghost",
                                    size="1",
                                    color_scheme="gray",
                                    on_click=TransferAnalyzerState.clear_negative,
                                ),
                                wrap="wrap",
                                spacing="1",
                                margin_top="0.35rem",
                            ),
                            rx.box(),
                        ),
                        align="start",
                        spacing="1",
                        width="100%",
                    ),

                    columns=rx.breakpoints(initial="1", md="2"),
                    spacing="4",
                    width="100%",
                    margin_bottom="1.25rem",
                    id="tour-transfer-locks",
                    custom_attrs={"data-tour-id": "tour-transfer-locks"},
                ),

                # Row 4: Primary Solve Transfers Action
                rx.button(
                    rx.hstack(
                        rx.icon("rocket", size=16),
                        rx.text("Solve Transfers", font_weight="700"),
                        align="center",
                        spacing="2",
                    ),
                    variant="solid",
                    color_scheme="blue",
                    size="3",
                    width="100%",
                    cursor="pointer",
                    on_click=TransferAnalyzerState.solve_transfers,
                    loading=TransferAnalyzerState.is_solving,
                ),

                width="100%",
                spacing="2",
            ),
            padding="1.25rem",
            background="var(--surface-1, rgba(255, 255, 255, 0.035))",
            border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
            border_radius="10px",
            margin_bottom="1.25rem",
            width="100%",
        ),

        # Solved Strategy & Metric Cards
        transfer_solution_panel(),

        # Initial helper message if not solved yet
        rx.cond(
            ~TransferAnalyzerState.has_solved,
            rx.box(
                rx.hstack(
                    rx.icon("info", size=16, color="#60a5fa"),
                    rx.text(
                        "Adjust settings above and click 'Solve Transfers' to begin optimization.",
                        font_size="0.85rem",
                        color="var(--text-sub)",
                    ),
                    align="center",
                    spacing="2",
                ),
                padding="0.75rem 1rem",
                border_radius="8px",
                background="rgba(59, 130, 246, 0.05)",
                border="1px solid rgba(59, 130, 246, 0.15)",
                margin_bottom="1.25rem",
                width="100%",
            ),
            rx.box(),
        ),

        # Main Content: Loading vs Comparison Pitch
        rx.cond(
            TransferAnalyzerState.is_loading,
            loading_view(
                status_message=TransferAnalyzerState.status_message,
                title="Transfer Horizon Solver",
                badge_text="SOLVER ACTIVE",
            ),
            rx.cond(
                TransferAnalyzerState.has_data,
                    transfer_lineup_panel(),
                rx.center(
                    rx.vstack(
                        rx.icon("arrow-left-right", size=32, color="var(--text-muted)"),
                        rx.text(
                            "No transfer data loaded. Enter your FPL Team ID to start optimization.",
                            font_size="0.9rem",
                            color="var(--text-sub)",
                        ),
                        rx.button(
                            "Enter FPL Team ID",
                            on_click=TransferAnalyzerState.open_id_dialog,
                            variant="solid",
                            color_scheme="blue",
                            size="2",
                        ),
                        align="center",
                        spacing="3",
                    ),
                    padding="4rem",
                    width="100%",
                ),
            ),
        ),
        width="100%",
        on_mount=TransferAnalyzerState.load_planner_data,
    )

