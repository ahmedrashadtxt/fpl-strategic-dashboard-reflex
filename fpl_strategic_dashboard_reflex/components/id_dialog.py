"""Dialog component for entering and updating FPL Team ID."""

import reflex as rx
from fpl_strategic_dashboard_reflex.state import AppState


def id_dialog(on_save_handler=None) -> rx.Component:
    return rx.dialog.root(
        rx.dialog.content(
            rx.dialog.title("Enter FPL Team ID", font_family="'Outfit', sans-serif"),
            rx.dialog.description(
                "Sync your live squad, bank balance, and free transfers directly from the official FPL API.",
                size="2",
                color_scheme="gray",
                margin_bottom="1rem",
            ),
            rx.vstack(
                rx.text("FPL Team ID", font_weight="600", font_size="0.85rem"),
                rx.input(
                    value=AppState.temp_manager_id,
                    on_change=AppState.set_temp_id,
                    placeholder="e.g. 7716321",
                    size="3",
                    width="100%",
                ),
                # Explanatory guide box matching Streamlit modal
                rx.box(
                    rx.vstack(
                        rx.text(
                            "💡 How to find your Team ID:",
                            font_weight="700",
                            color="var(--text-main)",
                            font_size="0.82rem",
                        ),
                        rx.text(
                            "1. Log into fantasy.premierleague.com and click Points or Pick Team.",
                            font_size="0.78rem",
                            color="var(--text-sub)",
                        ),
                        rx.text(
                            "2. Check the URL in your browser's address bar:",
                            font_size="0.78rem",
                            color="var(--text-sub)",
                        ),
                        rx.box(
                            rx.code(
                                "https://fantasy.premierleague.com/entry/",
                                rx.text.strong("7716321", color="var(--accent-green)"),
                                "/event/2",
                                font_family="monospace",
                                font_size="0.75rem",
                            ),
                            padding="6px 10px",
                            border_radius="6px",
                            background="rgba(0, 0, 0, 0.4)",
                            width="100%",
                            overflow_x="auto",
                        ),
                        rx.text(
                            "👉 The number right after /entry/ is your Team ID.",
                            font_size="0.78rem",
                            color="var(--text-sub)",
                        ),
                        spacing="2",
                        align="start",
                    ),
                    padding="12px 14px",
                    border_radius="8px",
                    background="rgba(255, 255, 255, 0.03)",
                    border="1px solid var(--border-color)",
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
                        on_click=([AppState.save_manager_id] + on_save_handler(AppState.selected_tab)) if on_save_handler else AppState.save_manager_id,
                        flex="1",
                    ),
                    width="100%",
                    spacing="3",
                    justify="end",
                ),
                spacing="3",
                width="100%",
            ),
            max_width="450px",
            background="var(--card-bg)",
            border="1px solid var(--border-color)",
            border_radius="12px",
            padding="1.5rem",
        ),
        open=AppState.is_id_dialog_open,
        on_open_change=lambda is_open: AppState.close_id_dialog(),
    )

