"""Reusable UI controls and filter bars."""

import reflex as rx
from fpl_strategic_dashboard_reflex.styles.theme import FILTER_BAR_STYLE


def search_input(value: rx.Var, on_change, placeholder: str = "Search player or team...") -> rx.Component:
    """Standardized search input field."""
    return rx.input(
        rx.input.slot(rx.icon("search", size=16)),
        value=value,
        on_change=on_change,
        placeholder=placeholder,
        size="2",
        variant="surface",
        width="100%",
    )


def filter_select(label: str, options: list[str], value: rx.Var, on_change) -> rx.Component:
    """Standardized select dropdown with label."""
    return rx.hstack(
        rx.text(label, font_size="0.8rem", color="var(--text-sub)", font_weight="600"),
        rx.select(
            options,
            value=value,
            on_change=on_change,
            size="2",
            variant="surface",
        ),
        align="center",
        spacing="2",
    )


def filter_bar(*children) -> rx.Component:
    """Container wrapping multiple filter controls with responsive layout."""
    return rx.box(
        rx.hstack(
            *children,
            width="100%",
            align="center",
            spacing="4",
            wrap="wrap",
        ),
        style=FILTER_BAR_STYLE,
    )

