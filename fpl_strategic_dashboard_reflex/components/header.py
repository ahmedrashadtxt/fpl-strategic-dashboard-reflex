"""Top navigation header for FPL Strategic Dashboard — brand row only."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState


def header() -> rx.Component:
    """Pure presentation top navbar — title, GW badge, manager button, theme toggle."""
    return rx.box(
        rx.hstack(
            # Brand & Subtitle
            rx.vstack(
                rx.hstack(
                    rx.text("FPL Optimizer", class_name="top-nav-title"),
                    rx.cond(
                        AppState.is_live,
                        rx.badge(
                            AppState.gw_badge_text,
                            variant="surface",
                            color_scheme="green",
                            radius="full",
                            size="2",
                        ),
                        rx.badge(
                            AppState.gw_badge_text,
                            variant="surface",
                            color_scheme="blue",
                            radius="full",
                            size="2",
                        ),
                    ),
                    align="center",
                    spacing="3",
                    wrap="wrap",
                ),
                rx.text(
                    "Strategic analytics & squad optimizer",
                    class_name="top-nav-sub",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            # Actions: Manager ID Button, Theme Toggle
            rx.hstack(
                rx.button(
                    AppState.badge_label,
                    on_click=AppState.open_id_dialog,
                    variant="surface",
                    color_scheme="blue",
                    class_name="manager-badge-btn",
                    cursor="pointer",
                ),
                rx.color_mode.button(
                    variant="surface",
                    size="2",
                    radius="large",
                    cursor="pointer",
                ),
                align="center",
                spacing="3",
                wrap="wrap",
            ),
            width="100%",
            align="center",
            justify="between",
            wrap="wrap",
            gap="1rem",
        ),
        padding_y="1.25rem",
        margin_bottom="0",
        width="100%",
    )
