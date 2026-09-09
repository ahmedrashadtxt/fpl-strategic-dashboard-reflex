"""Top navigation header for FPL Strategic Dashboard."""

import reflex as rx
from fpl_strategic_dashboard_reflex.state import AppState
from fpl_strategic_dashboard_reflex.states.base import AppState


def header() -> rx.Component:
    """Pure presentation top navbar."""
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
            # Actions: Gameweek Filter, Manager ID Button, Theme Toggle
            rx.hstack(
                # Gameweek Select
                rx.hstack(
                    rx.text("GW:", font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
                    rx.select(
                        [str(gw) for gw in range(1, 39)],
                        AppState.available_gameweeks,
                        value=AppState.selected_gw.to_string(),
                        on_change=AppState.set_selected_gw,
                        size="2",
                        variant="surface",
                    ),
                    align="center",
                    spacing="2",
                ),
                # Manager ID Action Button
                rx.button(
                    AppState.badge_label,
                    on_click=AppState.open_id_dialog,
                    variant="surface",
                    color_scheme="blue",
                    class_name="manager-badge-btn",
                ),
                # Theme Toggle
                rx.color_mode.button(
                    variant="surface",
                    size="2",
                    radius="large",
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
        padding_y="1rem",
        border_bottom="1px solid var(--border-color)",
        margin_bottom="1.25rem",
        width="100%",
    )

