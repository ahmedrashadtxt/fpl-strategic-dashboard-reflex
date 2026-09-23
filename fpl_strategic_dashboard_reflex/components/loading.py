"""Clean, modern, simple animated loading component for dashboard views."""

import reflex as rx


def loading_view(
    status_message: rx.Var | str = "Loading data...",
    title: str = "",
    badge_text: str = "",
) -> rx.Component:
    """Renders a clean, simple, and elegant animated loading spinner with status text."""
    return rx.center(
        rx.box(
            rx.vstack(
                rx.spinner(size="3"),
                rx.cond(
                    title != "",
                    rx.text(
                        title,
                        font_family="'Outfit', sans-serif",
                        font_size="1.05rem",
                        font_weight="700",
                        color="var(--text-main)",
                        letter_spacing="-0.01em",
                    ),
                ),
                rx.text(
                    status_message,
                    font_size="0.85rem",
                    color="var(--text-sub)",
                    font_weight="500",
                    text_align="center",
                ),
                align="center",
                spacing="3",
            ),
            class_name="simple-loading-card",
        ),
        padding_y="3rem",
        width="100%",
    )
