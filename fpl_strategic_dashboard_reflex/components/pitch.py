"""Pitch presentation component rendering the soccer pitch and bench dugout."""

import reflex as rx


def pitch_view(pitch_html: rx.Var | str, title: str = "", header_text: rx.Var | str = "") -> rx.Component:
    """Renders a responsive soccer pitch board."""
    return rx.box(
        rx.cond(
            header_text != "",
            rx.hstack(
                rx.text(header_text, font_family="'Outfit', sans-serif", font_weight="700", font_size="1rem"),
                width="100%",
                padding_y="0.5rem",
            ),
            rx.box(),
        ),
        rx.box(
            rx.html(pitch_html),
            width="100%",
            overflow_x="auto",
        ),
        width="100%",
        display="flex",
        flex_direction="column",
        align_items="center",
    )


def squad_list_view(starters: rx.Var, bench: rx.Var) -> rx.Component:
    """Renders an accessible alternative list view of starters and bench."""
    return rx.vstack(
        rx.text("Starting XI", font_weight="700", font_size="0.95rem", color="var(--text-main)"),
        rx.foreach(
            starters,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="8px 12px",
                border="1px solid rgba(255,255,255,0.08)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.6)",
                margin_bottom="4px",
            ),
        ),
        rx.text("Bench", font_weight="700", font_size="0.95rem", color="var(--text-sub)", margin_top="1rem"),
        rx.foreach(
            bench,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="8px 12px",
                border="1px solid rgba(255,255,255,0.08)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.4)",
                margin_bottom="4px",
            ),
        ),
        width="100%",
        spacing="2",
    )

