import asyncio
"""Audit Journal Page - Pure presentation view for model calibration and prediction audit."""

import reflex as rx
from typing import List, Dict, Any
from fpl_strategic_dashboard_reflex.states.audit import AuditJournalState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    filter_select,
    filter_bar,
)
from fpl_strategic_dashboard_reflex.styles.theme import TABLE_CONTAINER_STYLE

from fpl_strategic_dashboard_reflex.state import AppState
from backend.data import get_connection
from backend.audit_logic import load_audit_data, lock_audit_version, settle_audit_version, get_audit_snapshot

class AuditJournalState(AppState):
    is_loading: bool = False
    status_message: str = ""
    
    selected_gw: str = "1"
    versions: List[Dict[str, Any]] = []
    selected_version: str = ""
    
    @rx.var
    def version_options(self) -> list[str]:
        return [v["version_id"] for v in self.versions]
    
    snapshot_data: Dict[str, Any] = {}
    
    @rx.var
    def snapshot_starters(self) -> list[dict]:
        return self.snapshot_data.get("starters", []) if self.snapshot_data else []
        
    @rx.var
    def snapshot_bench(self) -> list[dict]:
        return self.snapshot_data.get("bench", []) if self.snapshot_data else []

    @rx.var
    def has_snapshot(self) -> bool:
        return bool(self.snapshot_data)
        
    def set_gw(self, val: str):
        self.selected_gw = str(val)
        return AuditJournalState.load_data
        
    def set_version(self, val: str):
        self.selected_version = val
        return AuditJournalState.load_snapshot
        
    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            
        async with self:
            c_gw = int(self.selected_gw)
            if c_gw == 1 and self.current_gw > 1:
                c_gw = self.current_gw - 1
                self.selected_gw = str(c_gw)
                
        result = await asyncio.to_thread(_load_audit_versions, c_gw)
        
        async with self:
            if result:
                self.versions = result
                self.selected_version = result[0]["version"]
            else:
                self.versions = []
                self.selected_version = ""
            self.is_loading = False
            
        if self.selected_version:
            return AuditJournalState.load_snapshot
            
    @rx.event(background=True)
    async def load_snapshot(self):
        async with self:
            self.is_loading = True
            
        async with self:
            c_gw = int(self.selected_gw)
            c_ver = self.selected_version
            
        if not c_ver:
            async with self:
                self.snapshot_data = {}
                self.is_loading = False
            return
            
        result = await asyncio.to_thread(_load_snapshot, c_gw, c_ver)
        
        async with self:
            self.snapshot_data = result if result else {}
            self.is_loading = False
            
    @rx.event(background=True)
    async def lock_version(self):
        async with self:
            self.is_loading = True
            self.status_message = "Locking new version..."
        
        async with self:
            c_gw = int(self.selected_gw)
            curr_gw = self.current_gw
            
        success, msg = await asyncio.to_thread(_lock_version, manager_id, c_gw, curr_gw)
        
        async with self:
            self.is_loading = False
            self.status_message = f"Success! Locked version {msg}" if success else f"Error: {msg}"
            
        if success:
            return AuditJournalState.load_data
            
    @rx.event(background=True)
    async def settle_version(self):
        async with self:
            self.is_loading = True
            self.status_message = "Settling match outcomes..."
            
        async with self:
            c_gw = int(self.selected_gw)
            c_ver = self.selected_version
            
        success, msg = await asyncio.to_thread(_settle_version, c_gw, c_ver)
        
        async with self:
            self.is_loading = False
            self.status_message = "Success! Settled." if success else f"Error: {msg}"
            
        if success:
            return AuditJournalState.load_snapshot
            

def _load_audit_versions(gw):
    try:
        return load_audit_data(get_connection(), gw)
    except Exception as e:
        print(e)
        return []

def _load_snapshot(gw, ver):
    try:
        return get_audit_snapshot(get_connection(), gw, ver)
    except Exception as e:
        print(e)
        return None

def _lock_version(mgr, gw, curr_gw):
    try:
        return lock_audit_version(get_connection(), mgr, gw, curr_gw)
    except Exception as e:
        print(e)
        return False, str(e)
        
def _settle_version(gw, ver):
    try:
        return settle_audit_version(get_connection(), gw, ver)
    except Exception as e:
        print(e)
        return False, str(e)
        
def render_audit_player(p: Dict[str, Any]):
def audit_journal_page() -> rx.Component:
    """Renders the Audit Journal & Calibration tab view."""
    return rx.box(
        # Page Title & Guide
        rx.hstack(
            rx.image(src=p["img_url"], width="30px", height="30px", border_radius="50%"),
            rx.text(p["player_name"], weight="bold"),
            rx.text(f"£{p.get('price', 0):.1f}m", size="1", color="gray"),
            rx.vstack(
                rx.text("Audit Journal & Decision Logs", class_name="section-header-title"),
                rx.text("Verify model accountability by comparing pre-deadline projected points against settled official scores.", class_name="section-header-sub"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.text(f"Proj: {p.get('proj_pts', 0):.1f}", color="blue"),
            rx.cond(
                p.get("actual_pts") != None,
                rx.text(f"Act: {p.get('actual_pts', 0)}", weight="bold", color="green"),
                rx.text("Act: -", color="gray")
            guide_popover(
                title="Audit Journal Guide",
                subtitle="Model tracking and decision accountability",
                items=[
                    {"badge": "Lock", "title": "Pre-GW Snapshot", "desc": "Snapshot your lineup predictions before deadline to evaluate accuracy."},
                    {"badge": "Settle", "title": "Post-GW Evaluation", "desc": "Sync official match points once the gameweek is finished to compute variance."},
                ],
                tip="Check projection accuracy across position groups to detect systemic biases.",
            ),
            width="100%",
            padding="2",
            border_bottom="1px solid rgba(255,255,255,0.1)"
        )
    )
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),

def audit_journal_page():
    return rx.box(
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
                    rx.spinner(),
                    rx.text(AuditJournalState.status_message, color="gray")
                ), 
                padding="8"
            )
        ),
        rx.vstack(
            rx.text("Model Audit & Performance Journal", font_size="2xl", weight="bold"),
            rx.text("Inspect locked solver versions, track pre-match line shifts, and audit prediction variance against final outcomes.", color="gray"),
            
            rx.cond(
                AuditJournalState.status_message != "",
                rx.callout(AuditJournalState.status_message, icon="info")
            ),
            
            rx.grid(
                rx.box(
                    rx.text("Gameweek"),
                    rx.select([str(i) for i in range(1, 39)], value=AuditJournalState.selected_gw, on_change=AuditJournalState.set_gw)
                    rx.spinner(size="3"),
                    rx.text("Loading audit snapshot...", font_size="0.85rem", color="var(--text-sub)"),
                    align="center",
                    spacing="2",
                ),
                rx.box(
                    rx.text("Snapshot Version"),
                    rx.cond(
                        AuditJournalState.version_options.length() > 0,
                        rx.select(
                            AuditJournalState.version_options,
                            value=AuditJournalState.selected_version,
                            on_change=AuditJournalState.set_version
                        ),
                        rx.select(["No locks recorded"], value="No locks recorded", disabled=True)
                    )
                ),
                rx.box(
                    rx.text("Actions"),
                    rx.hstack(
                        rx.button("Lock New Version", on_click=AuditJournalState.lock_version),
                        rx.button("Settle Outcomes", on_click=AuditJournalState.settle_version, disabled=~AuditJournalState.has_snapshot),
                    )
                ),
                columns="3",
                spacing="4",
                width="100%"
                padding="3rem",
                width="100%",
            ),
            
            rx.divider(),
            
            rx.cond(
                AuditJournalState.has_snapshot,
                rx.box(
                    rx.text(f"Locked at: {AuditJournalState.snapshot_data['created_at']}", color="gray", size="2", margin_bottom="4"),
                    
                    rx.grid(
                        rx.box(rx.text("Total Projected", color="gray"), rx.text(AuditJournalState.snapshot_data["total_proj"], weight="bold", size="6")),
                        rx.box(rx.text("Total Actual", color="gray"), rx.text(AuditJournalState.snapshot_data["total_act"], weight="bold", size="6", color="green")),
                        columns="2",
                        spacing="4",
                        margin_bottom="4"
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
                                                row["actual_pts"].is_not_none(),
                                                rx.text(row["actual_pts"], font_weight="700", color="#4ade80"),
                                                rx.text("Pending", font_style="italic", color="var(--text-muted)"),
                                            )
                                        ),
                                        rx.table.cell(
                                            rx.cond(
                                                row["actual_pts"].is_not_none(),
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
                    
                    rx.text("Starters", weight="bold", margin_top="4"),
                    rx.foreach(AuditJournalState.snapshot_starters, render_audit_player),
                    
                    rx.text("Bench", weight="bold", margin_top="4"),
                    rx.foreach(AuditJournalState.snapshot_bench, render_audit_player),
                    
                    width="100%"
                    width="100%",
                ),
                rx.center(rx.text("No snapshot selected.", color="gray"), padding="8")
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
            
            spacing="4",
            width="100%"
        ),
        width="100%",
        on_mount=AuditJournalState.load_data
    )

