"""Audit Journal Page - Pure presentation view for model calibration and prediction audit."""

import reflex as rx
from fpl_strategic_dashboard_reflex.states.audit import AuditJournalState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    filter_select,
    filter_bar,
)
from fpl_strategic_dashboard_reflex.styles.theme import TABLE_CONTAINER_STYLE


def audit_journal_page() -> rx.Component:
    """Renders the Audit Journal & Calibration tab view."""
    return rx.box(
        # Page Title & Guide
        rx.hstack(
            rx.hstack(
                rx.box(
                    width="4px",
                    height="32px",
                    background="var(--accent-9)",
                    border_radius="2px",
                    margin_right="0.5rem",
                ),
                rx.vstack(
                    rx.text("Audit Journal & Decision Logs", class_name="section-header-title"),
                    rx.text("Verify model accountability by comparing pre-deadline projected points against settled official scores.", class_name="section-header-sub"),
                    align="start",
                    spacing="1",
                ),
                align="center",
            ),
            rx.hstack(
                guide_popover(
                    title="Audit Journal Guide",
                    subtitle="Model tracking and decision accountability",
                    items=[
                        {"badge": "Lock", "title": "Pre-GW Snapshot", "desc": "Snapshot your lineup predictions before deadline to evaluate accuracy."},
                        {"badge": "Settle", "title": "Post-GW Evaluation", "desc": "Sync official match points once the gameweek is finished to compute variance."},
                    ],
                    tip="Check projection accuracy across position groups to detect systemic biases.",
                ),
                rx.button(
                    rx.hstack(
                        rx.icon("refresh-cw", size=14),
                        rx.text("Refresh"),
                        align="center",
                        spacing="1",
                    ),
                    on_click=AuditJournalState.refresh_data,
                    variant="outline",
                    size="2",
                    color_scheme="gray",
                ),
                align="center",
                spacing="2",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),

        # Filter & Action Bar
        filter_bar(
            filter_select(
                "Audit Gameweek:",
                [str(gw) for gw in range(1, 39)],
                AuditJournalState.selected_audit_gw,
                AuditJournalState.set_audit_gw,
            ),
            filter_select(
                "Version:",
                AuditJournalState.version_options,
                AuditJournalState.selected_version,
                AuditJournalState.set_version,
            ),
            rx.spacer(),
            rx.hstack(
                rx.button(
                    rx.icon("lock", size=16),
                    "Lock Pre-GW Lineup",
                    variant="solid",
                    color_scheme="blue",
                    size="2",
                    on_click=AuditJournalState.lock_version,
                ),
                rx.button(
                    rx.icon("check-check", size=16),
                    "Settle Official Points",
                    variant="surface",
                    color_scheme="green",
                    size="2",
                    on_click=AuditJournalState.settle_version,
                ),
                align="center",
                spacing="2",
            ),
        ),

        # Status Message Banner (if any)
        rx.cond(
            AuditJournalState.status_message != "",
            rx.box(
                rx.text(AuditJournalState.status_message, font_size="0.85rem", color="var(--accent-blue)"),
                padding="0.75rem 1rem",
                border_radius="8px",
                background="rgba(59, 130, 246, 0.08)",
                border="1px solid rgba(59, 130, 246, 0.2)",
                margin_bottom="1.25rem",
                width="100%",
            ),
            rx.box(),
        ),

        # KPI Summary Cards (if snapshot available)
        rx.cond(
            AuditJournalState.has_snapshot,
            rx.hstack(
                metric_card("Total Predicted xP", AuditJournalState.total_proj_str, "Pre-GW Model", "blue"),
                metric_card("Total Actual Scored", AuditJournalState.total_act_str, "Settled Points", "green"),
                metric_card("Variance Delta", AuditJournalState.variance_delta_str, "Deviation", "purple"),
                width="100%",
                spacing="3",
                wrap="wrap",
                margin_bottom="1.5rem",
            ),
            rx.box(),
        ),

        # Snapshot Player Table
        rx.cond(
            AuditJournalState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text("Loading audit snapshot...", font_size="0.85rem", color="var(--text-sub)"),
                    align="center",
                    spacing="2",
                ),
                padding="3rem",
                width="100%",
            ),
            rx.cond(
                AuditJournalState.has_snapshot,
                rx.vstack(
                    rx.text("Locked Starting XI Lineup", font_weight="700", font_size="0.95rem", margin_bottom="0.75rem"),
                    rx.box(
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Player", font_weight="700"),
                                    rx.table.column_header_cell("Club", font_weight="700"),
                                    rx.table.column_header_cell("Pos", font_weight="700"),
                                    rx.table.column_header_cell("Role", font_weight="700"),
                                    rx.table.column_header_cell("Predicted xP", font_weight="700"),
                                    rx.table.column_header_cell("Actual Points", font_weight="700"),
                                    rx.table.column_header_cell("Variance", font_weight="700"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    AuditJournalState.snapshot_starters,
                                    lambda row: rx.table.row(
                                        rx.table.cell(rx.text(row["web_name"], font_weight="600")),
                                        rx.table.cell(rx.badge(row["team"], variant="surface", color_scheme="gray", size="1")),
                                        rx.table.cell(rx.text(row["pos"], font_size="0.8rem")),
                                        rx.table.cell(
                                            rx.cond(
                                                row["is_captain"],
                                                rx.badge("Captain (C)", variant="solid", color_scheme="purple", size="1"),
                                                rx.cond(
                                                    row["is_vice"],
                                                    rx.badge("Vice (V)", variant="surface", color_scheme="blue", size="1"),
                                                    rx.badge("Starter", variant="surface", color_scheme="gray", size="1"),
                                                ),
                                            )
                                        ),
                                        rx.table.cell(rx.text(row["proj_pts"], font_weight="700", color="#60a5fa")),
                                        rx.table.cell(
                                            rx.cond(
                                                row["actual_pts"] != None,
                                                rx.text(row["actual_pts"], font_weight="700", color="#4ade80"),
                                                rx.text("Pending", font_style="italic", color="var(--text-muted)"),
                                            )
                                        ),
                                        rx.table.cell(
                                            rx.cond(
                                                row["actual_pts"] != None,
                                                rx.badge(row["diff_str"], variant="soft", size="1"),
                                                rx.text("-"),
                                            )
                                        ),
                                    ),
                                )
                            ),
                            variant="surface",
                            size="2",
                            width="100%",
                        ),
                        style=TABLE_CONTAINER_STYLE,
                    ),
                    width="100%",
                ),
                rx.center(
                    rx.vstack(
                        rx.icon("clipboard-list", size=32, color="var(--text-muted)"),
                        rx.text("No audit snapshot found for this gameweek. Click 'Lock Pre-GW Lineup' to record a snapshot.", font_size="0.9rem", color="var(--text-sub)"),
                        align="center",
                        spacing="2",
                    ),
                    padding="3rem",
                    width="100%",
                ),
            ),
        ),
        width="100%",
        on_mount=AuditJournalState.load_data,
    )
