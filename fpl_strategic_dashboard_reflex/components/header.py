"""Top navigation header for FPL Strategic Dashboard — brand row only."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.components.motion import MotionDiv


def header() -> rx.Component:
    """Pure presentation top navbar — title, GW badge, manager button, theme toggle.

    Phase 0 motion demo: slides down from y=-8 + opacity 0 on first mount.
    Spring stiffness=350, damping=28 → tight, non-bouncy settle in ~220ms.
    """
    return MotionDiv.create(
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
        # Phase 0 demo: entrance animation — slides down from -8px + fades in
        initial={"opacity": 0, "y": -8},
        animate={"opacity": 1, "y": 0},
        transition={
            "type": "spring",
            "stiffness": 350,
            "damping": 28,
        },
        padding_y="1.25rem",
        margin_bottom="0",
        width="100%",
    )

