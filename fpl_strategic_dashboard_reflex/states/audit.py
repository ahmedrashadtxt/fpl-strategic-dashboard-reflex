"""Domain State for Audit Journal."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.db import get_connection
from fpl_strategic_dashboard_reflex.services.audit import (
    load_audit_data,
    lock_audit_version,
    settle_audit_version,
    get_audit_snapshot,
)


class AuditJournalState(AppState):
    """Sub-state managing pre-gameweek model locks and post-gameweek prediction audits."""

    is_loading: bool = False
    status_message: str = ""

    selected_audit_gw: str = "1"
    versions: List[Dict[str, Any]] = []
    selected_version: str = ""

    snapshot_data: Dict[str, Any] = {}

    @rx.var
    def version_options(self) -> list[str]:
        return [str(v.get("version", "")) for v in self.versions]

    @rx.var
    def snapshot_starters(self) -> list[dict]:
        return self.snapshot_data.get("starters", []) if self.snapshot_data else []

    @rx.var
    def snapshot_bench(self) -> list[dict]:
        return self.snapshot_data.get("bench", []) if self.snapshot_data else []

    @rx.var
    def has_snapshot(self) -> bool:
        return bool(self.snapshot_data)

    @rx.var
    def total_proj_str(self) -> str:
        if not self.snapshot_data:
            return "0.0"
        return f"{float(self.snapshot_data.get('total_proj', 0.0)):.1f}"

    @rx.var
    def total_act_str(self) -> str:
        if not self.snapshot_data:
            return "0.0"
        return f"{float(self.snapshot_data.get('total_act', 0.0)):.1f}"

    @rx.var
    def variance_delta_str(self) -> str:
        if not self.snapshot_data:
            return "0.0 pts"
        tot_act = float(self.snapshot_data.get("total_act", 0.0))
        tot_proj = float(self.snapshot_data.get("total_proj", 0.0))
        diff = tot_act - tot_proj
        return f"{diff:+.1f} pts"

    def set_audit_gw(self, val: str):
        self.selected_audit_gw = str(val)
        return AuditJournalState.load_data

    def set_version(self, val: str):
        self.selected_version = val
        return AuditJournalState.load_snapshot

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            try:
                c_gw = int(self.selected_audit_gw)
            except Exception:
                c_gw = self.current_gw
            if c_gw == 1 and self.current_gw > 1:
                c_gw = self.current_gw - 1
                self.selected_audit_gw = str(c_gw)

        def _fetch(gw):
            conn = get_connection()
            return load_audit_data(conn, gw)

        result = await asyncio.to_thread(_fetch, c_gw)

        async with self:
            if result:
                self.versions = result
                self.selected_version = str(result[0]["version"])
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
            try:
                c_gw = int(self.selected_audit_gw)
                c_ver = int(self.selected_version) if self.selected_version else None
            except Exception:
                c_gw, c_ver = 1, None

        if not c_ver:
            async with self:
                self.snapshot_data = {}
                self.is_loading = False
            return

        def _fetch(gw, ver):
            conn = get_connection()
            return get_audit_snapshot(conn, gw, ver)

        result = await asyncio.to_thread(_fetch, c_gw, c_ver)

        async with self:
            self.snapshot_data = result if result else {}
            self.is_loading = False

    @rx.event(background=True)
    async def lock_version(self):
        async with self:
            self.is_loading = True
            self.status_message = "Locking new version..."
            mgr_id = self.manager_id
            try:
                c_gw = int(self.selected_audit_gw)
            except Exception:
                c_gw = self.current_gw
            curr_gw = self.current_gw

        def _lock(manager_id, selected_gw, current_gw):
            conn = get_connection()
            return lock_audit_version(conn, manager_id, selected_gw, current_gw)

        success, msg = await asyncio.to_thread(_lock, mgr_id, c_gw, curr_gw)

        async with self:
            self.is_loading = False
            self.status_message = f"Version {msg} locked successfully" if success else f"Error: {msg}"

        return AuditJournalState.load_data

    @rx.event(background=True)
    async def settle_version(self):
        async with self:
            self.is_loading = True
            self.status_message = "Settling with official points..."
            try:
                c_gw = int(self.selected_audit_gw)
                c_ver = int(self.selected_version) if self.selected_version else 1
            except Exception:
                c_gw, c_ver = 1, 1

        def _settle(selected_gw, selected_version):
            conn = get_connection()
            return settle_audit_version(conn, selected_gw, selected_version)

        success, err = await asyncio.to_thread(_settle, c_gw, c_ver)

        async with self:
            self.is_loading = False
            self.status_message = "Settled successfully" if success else f"Error: {err}"

        return AuditJournalState.load_snapshot
