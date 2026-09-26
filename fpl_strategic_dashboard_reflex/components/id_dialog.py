"""Dialog component for entering and updating FPL Team ID."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState


def id_dialog(on_save_handler=None) -> rx.Component:
    """Pure presentation modal dialog for setting user's FPL manager ID."""
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title(
                "Enter FPL Team ID",
                font_family="'Outfit', sans-serif",
                font_size="1.25rem",
                font_weight="700",
                color="var(--text-main)",
            ),
            rx.dialog.description(
                "Sync your live squad, bank balance, and free transfers directly from the official FPL API.",
                size="2",
                color="var(--text-sub)",
                margin_bottom="1rem",
                style={"textWrap": "pretty"},
            ),
            rx.vstack(
                rx.text(
                    "FPL Team ID",
                    font_weight="600",
                    font_size="0.82rem",
                    color="var(--text-sub)",
                ),
                rx.input(
                    value=AppState.temp_manager_id,
                    on_change=AppState.set_temp_id,
                    placeholder="e.g. 1234567",
                    size="3",
                    debounce_timeout=200,
                    width="100%",
                ),
                # Explanatory guide box
                rx.box(
                    rx.vstack(
                        rx.hstack(
                            rx.icon("info", size=14, color="var(--color-interactive, #38bdf8)"),
                            rx.text(
                                "How to find your Team ID:",
                                font_weight="600",
                                color="var(--color-interactive, #38bdf8)",
                                font_size="0.82rem",
                            ),
                            align="center",
                            spacing="2",
                        ),
                        # Step 1 — wrapped cleanly with text-wrap: pretty and no orphan
                        rx.hstack(
                            rx.text(
                                "1.",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                flex_shrink="0",
                                font_weight="600",
                            ),
                            rx.text(
                                "Log into fantasy.premierleague.com and click Points or Pick\u00a0Team.",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                white_space="normal",
                                style={"textWrap": "pretty"},
                            ),
                            align="start",
                            spacing="2",
                            width="100%",
                        ),
                        # Step 2
                        rx.hstack(
                            rx.text(
                                "2.",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                flex_shrink="0",
                                font_weight="600",
                            ),
                            rx.text(
                                "Check the URL in your browser's address bar:",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                style={"textWrap": "pretty"},
                            ),
                            align="center",
                            spacing="2",
                            width="100%",
                        ),
                        # URL example box — Level-1 filled surface with interactive blue accent
                        rx.box(
                            rx.text(
                                "fantasy.premierleague.com/entry/",
                                rx.el.span(
                                    "1234567",
                                    style={"color": "var(--color-interactive, #38bdf8)", "font_weight": "700"},
                                ),
                                "/event/",
                                rx.el.span(
                                    AppState.example_url_gw,
                                    style={"color": "var(--color-interactive, #38bdf8)", "font_weight": "700"},
                                ),
                                font_family="monospace",
                                font_size="0.74rem",
                                color="var(--text-sub)",
                                word_break="break-all",
                                white_space="normal",
                                line_height="1.6",
                            ),
                            padding="7px 12px",
                            border_radius="6px",
                            background="var(--surface-1, rgba(255, 255, 255, 0.035))",
                            border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
                            width="100%",
                        ),
                        # Live / Completed GW badge
                        rx.hstack(
                            rx.icon("calendar", size=12, color="var(--text-muted)"),
                            rx.text(
                                AppState.example_url_gw_label,
                                font_size="0.72rem",
                                color="var(--text-muted)",
                                font_weight="500",
                            ),
                            align="center",
                            spacing="1",
                        ),
                        rx.hstack(
                            rx.icon("arrow-right", size=12, color="var(--text-muted)"),
                            rx.text(
                                "The number right after /entry/ is your Team ID.",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                style={"textWrap": "pretty"},
                            ),
                            align="center",
                            spacing="2",
                        ),
                        spacing="2",
                        align="start",
                        width="100%",
                    ),
                    padding="12px 14px",
                    border_radius="8px",
                    background="rgba(255, 255, 255, 0.02)",
                    border="1px solid var(--border-overlay, rgba(255, 255, 255, 0.12))",
                    width="100%",
                    margin_y="0.75rem",
                ),
                rx.hstack(
                    rx.button(
                        "Cancel",
                        variant="soft",
                        color_scheme="gray",
                        on_click=AppState.close_id_dialog,
                        flex="1",
                    ),
                    rx.button(
                        "Save",
                        variant="solid",
                        color_scheme="blue",
                        on_click=AppState.save_manager_id,
                        flex="1",
                    ),
                    width="100%",
                    spacing="3",
                    justify="end",
                ),
                spacing="3",
                width="100%",
            ),
            max_width="480px",
            background="var(--surface-overlay, rgba(18, 18, 22, 0.90))",
            backdrop_filter="blur(16px)",
            border="1px solid var(--border-overlay, rgba(255, 255, 255, 0.12))",
            border_radius="12px",
            box_shadow="var(--shadow-modal)",
            padding="1.5rem",
        ),
        open=AppState.is_id_dialog_open,
        on_open_change=lambda is_open: AppState.close_id_dialog(),
    )
