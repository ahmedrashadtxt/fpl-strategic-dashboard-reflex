"""Guide popover component displaying strategy instructions and tips."""

import reflex as rx


def guide_popover(title: str, subtitle: str, items: list[dict], tip: str = None) -> rx.Component:
    """Renders a strategy guide popover with badge items and an actionable tip."""
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                rx.icon("circle-help", size=16),
                "Strategy Guide",
                variant="surface",
                color_scheme="gray",
                size="2",
                radius="full",
                cursor="pointer",
            ),
        ),
        rx.popover.content(
            rx.vstack(
                rx.vstack(
                    rx.text(title, font_family="'Outfit', sans-serif", font_weight="700", font_size="1rem"),
                    rx.text(subtitle, font_size="0.8rem", color="var(--text-sub)"),
                    align="start",
                    spacing="1",
                    border_bottom="1px solid var(--border-color)",
                    padding_bottom="0.5rem",
                    width="100%",
                ),
                rx.vstack(
                    *[
                        rx.box(
                            rx.hstack(
                                rx.badge(
                                    item.get("badge", "Tip"),
                                    variant="soft",
                                    color_scheme="blue",
                                    size="1",
                                ),
                                rx.text(item.get("title", ""), font_weight="600", font_size="0.82rem"),
                                align="center",
                                spacing="2",
                            ),
                            rx.text(item.get("desc", ""), font_size="0.75rem", color="var(--text-sub)", margin_top="2px"),
                            width="100%",
                            padding_y="4px",
                        )
                        for item in items
                    ],
                    width="100%",
                    spacing="2",
                    align="start",
                ),
                rx.cond(
                    tip is not None and tip != "",
                    rx.box(
                        rx.hstack(
                            rx.icon("info", size=14, color="var(--accent-blue)"),
                            rx.text.strong("Pro-Tip:", font_size="0.75rem"),
                            rx.text(tip or "", font_size="0.75rem", color="var(--text-sub)"),
                            align="start",
                            spacing="2",
                        ),
                        padding="8px 10px",
                        border_radius="6px",
                        background="rgba(59, 130, 246, 0.08)",
                        border="1px solid rgba(59, 130, 246, 0.2)",
                        width="100%",
                        margin_top="0.5rem",
                    ),
                    rx.box(),
                ),
                width="100%",
                max_width="400px",
                spacing="3",
            ),
            style={"max_width": "420px", "padding": "1rem", "background": "var(--card-bg)"},
        ),
    )
