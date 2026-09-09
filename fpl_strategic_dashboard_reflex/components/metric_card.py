"""Reusable KPI Metric Card component."""

import reflex as rx
from fpl_strategic_dashboard_reflex.styles.theme import METRIC_CARD_STYLE


def metric_card(
    label: str,
    value: rx.Var | str,
    badge_text: str = "",
    color: str = "blue",
    subtext: str = "",
) -> rx.Component:
    """Pure presentation metric card."""
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(label, class_name="metric-card-label", font_size="0.75rem", color="var(--text-sub)"),
                rx.text(value, class_name="metric-card-value", font_size="1.25rem", font_weight="800"),
                rx.cond(
                    subtext != "",
                    rx.text(subtext, font_size="0.7rem", color="var(--text-muted)"),
                    rx.box(),
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.cond(
                badge_text != "",
                rx.badge(badge_text, variant="soft", color_scheme=color, radius="full", size="1"),
                rx.box(),
            ),
            align="center",
            width="100%",
        ),
        style=METRIC_CARD_STYLE,
    )

