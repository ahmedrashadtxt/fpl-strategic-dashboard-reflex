"""Declarative, styled data table component with loading and empty states."""

import reflex as rx
from fpl_strategic_dashboard_reflex.styles.theme import TABLE_CONTAINER_STYLE


def data_table(
    headers: list[str],
    rows: rx.Var,
    row_render_func,
    is_loading: rx.Var | bool = False,
    empty_msg: str = "No records found matching current criteria.",
) -> rx.Component:
    """Renders a declarative table with loading overlay and empty fallback."""
    return rx.box(
        rx.cond(
            is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Loading records...", font_size="0.85rem", color="var(--text-sub)"),
                    align="center",
                    spacing="2",
                ),
                padding="3rem",
                width="100%",
            ),
            rx.cond(
                rows.length() > 0,
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.foreach(
                                headers,
                                lambda h: rx.table.column_header_cell(
                                    h,
                                    font_family="'Outfit', sans-serif",
                                    font_weight="700",
                                    font_size="0.8rem",
                                    color="var(--text-sub)",
                                ),
                            )
                        )
                    ),
                    rx.table.body(
                        rx.foreach(rows, row_render_func)
                    ),
                    variant="surface",
                    size="2",
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("info", size=24, color="var(--text-muted)"),
                        rx.text(empty_msg, font_size="0.85rem", color="var(--text-sub)"),
                        align="center",
                        spacing="2",
                    ),
                    padding="3rem",
                    width="100%",
                ),
            ),
        ),
        style=TABLE_CONTAINER_STYLE,
    )
