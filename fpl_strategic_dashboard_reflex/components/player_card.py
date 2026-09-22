"""Reusable Player Highlight Card component for analytic pages."""

import reflex as rx


def player_highlight_card(c: dict) -> rx.Component:
    """Renders a single player highlight card with avatar, name, position, team, projection badge, and summary subtext."""
    return rx.box(
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
                        rx.badge(c["badge_text"], variant="surface", color_scheme=c["badge_color"], size="1"),
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
        background="rgba(255, 255, 255, 0.03)",
        border="1px solid var(--border-color)",
        border_radius="10px",
        flex="1 1 230px",
        min_width="220px",
    )

