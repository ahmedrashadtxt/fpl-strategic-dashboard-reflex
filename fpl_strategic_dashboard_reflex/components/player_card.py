"""Reusable Player Highlight Card component for analytic pages."""

import reflex as rx
from .motion import MotionDiv, MotionSpan


def player_highlight_card(c: dict) -> rx.Component:
    """Renders a single player highlight card with avatar, name, position, team, projection badge, and summary subtext."""
    return MotionDiv.create(
        rx.hstack(
            rx.avatar(
                src=c["img_url"],
                fallback=c["pos"],
                size="3",
                radius="full",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(c["player"], font_weight="700", font_size="0.95rem", color="var(--text-main)"),
                    rx.cond(
                        (c["pos"] != "") & (c["pos"] != None),
                        rx.badge(c["pos"], variant="outline", color_scheme=c["pos_color"], size="1"),
                        rx.box(),
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.hstack(
                    rx.text(c["team_display"], font_size="0.85rem", color="var(--text-sub)", font_weight="600"),
                    rx.cond(
                        (c["badge_text"] != "") & (c["badge_text"] != None),
                        MotionSpan.create(
                            rx.badge(c["badge_text"], variant="surface", color_scheme=c["badge_color"], size="1"),
                            initial={"scale": 0, "opacity": 0},
                            animate={"scale": 1, "opacity": 1},
                            transition={"type": "spring", "stiffness": 400, "damping": 22},
                        ),
                        rx.box(),
                    ),
                    align="center",
                    spacing="2",
                ),
                rx.text(c["subtext"], font_size="0.72rem", color="var(--text-muted)"),
                align="start",
                spacing="1",
            ),
            align="center",
            spacing="3",
            width="100%",
        ),
        padding="0.75rem 1rem",
        background="var(--surface-1, rgba(255, 255, 255, 0.035))",
        border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
        border_radius="10px",
        width="100%",
        min_width="0",
        layout="position",
        while_hover={"y": -3, "boxShadow": "0 8px 24px rgba(0, 0, 0, 0.35)"},
        while_tap={"scale": 0.97},
        transition={"type": "spring", "stiffness": 400, "damping": 30},
    )

