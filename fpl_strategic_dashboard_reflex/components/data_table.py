"""Declarative, styled data table component with loading and empty states."""

import reflex as rx
from fpl_strategic_dashboard_reflex.styles.theme import TABLE_CONTAINER_STYLE


from typing import Any, Callable, Optional


def data_table(
    headers: list[str] | rx.Var[list[str]],
    rows: rx.Var,
    row_render_func,
    is_loading: rx.Var | bool = False,
    empty_msg: str = "No records found matching current criteria.",
    sort_col: rx.Var[str] | str = "",
    sort_dir: rx.Var[str] | str = "desc",
    on_sort: Optional[Any] = None,
) -> rx.Component:
    """Renders a declarative table with loading overlay, empty fallback, and sortable headers."""
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
                                lambda h: rx.cond(
                                    sort_col == h,
                                    rx.table.column_header_cell(
                                        rx.hstack(
                                            rx.text(h, white_space="nowrap"),
                                            rx.cond(
                                                sort_dir == "asc",
                                                rx.icon("arrow-up", size=13, color="var(--accent-9)"),
                                                rx.icon("arrow-down", size=13, color="var(--accent-9)"),
                                            ),
                                            align="center",
                                            spacing="1",
                                        ),
                                        font_family="'Outfit', sans-serif",
                                        font_weight="700",
                                        font_size="0.8rem",
                                        color="var(--text-main)",
                                        cursor="pointer",
                                        user_select="none",
                                        _hover={"color": "var(--accent-9)", "background": "rgba(255, 255, 255, 0.04)"},
                                        transition="all 0.15s ease",
                                        on_click=on_sort(h),
                                    ),
                                    rx.table.column_header_cell(
                                        rx.hstack(
                                            rx.text(h, white_space="nowrap"),
                                            rx.icon("chevrons-up-down", size=12, opacity=0.25),
                                            align="center",
                                            spacing="1",
                                        ),
                                        font_family="'Outfit', sans-serif",
                                        font_weight="700",
                                        font_size="0.8rem",
                                        color="var(--text-sub)",
                                        cursor="pointer",
                                        user_select="none",
                                        _hover={"color": "var(--text-main)", "background": "rgba(255, 255, 255, 0.04)"},
                                        transition="all 0.15s ease",
                                        on_click=on_sort(h),
                                    ),
                                )
                                if on_sort is not None
                                else rx.table.column_header_cell(
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
