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

_audit_versions_cache: Dict[int, List[Dict[str, Any]]] = {}
_audit_snapshot_cache: Dict[str, Dict[str, Any]] = {}


class AuditJournalState(AppState):
    """Sub-state managing pre-gameweek model locks and post-gameweek prediction audits."""

    is_loading: bool = False
    status_message: str = ""

    selected_audit_gw: str = "1"
    versions: List[Dict[str, Any]] = []
    selected_version: str = ""

    snapshot_data: Dict[str, Any] = {}

    # Cache tracking fields
    last_loaded_gw: int = 0
    last_loaded_ver: str = ""

    @rx.var
    def gw_options(self) -> list[str]:
        return [str(i) for i in range(1, 39)]

    @rx.var
    def version_options(self) -> list[str]:
        return [f"v{v['version']} - {v['created_at'][:16]}" for v in self.versions]

    @rx.var
    def has_versions(self) -> bool:
        return len(self.versions) > 0

    @rx.var
    def has_snapshot(self) -> bool:
        return bool(self.snapshot_data and len(self.snapshot_data.get("players", [])) > 0)

    @rx.var
    def snapshot_players(self) -> list[Dict[str, Any]]:
        return self.snapshot_data.get("players", [])

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
        return AuditJournalState.load_data(False)

    def set_version(self, val: str):
        self.selected_version = val
        return AuditJournalState.load_snapshot(False)

    @rx.event
    def refresh_data(self):
        """Explicitly re-fetches audit data bypassing caches."""
        _audit_versions_cache.clear()
        _audit_snapshot_cache.clear()
        return AuditJournalState.load_data(True)

    @rx.event(background=True)
    async def load_data(self, force_refresh: bool = False):
        async with self:
            try:
                c_gw = int(self.selected_audit_gw)
            except Exception:
                c_gw = self.current_gw
            if c_gw == 1 and self.current_gw > 1:
                c_gw = self.current_gw - 1
                self.selected_audit_gw = str(c_gw)

            if not force_refresh and c_gw in _audit_versions_cache:
                result = _audit_versions_cache[c_gw]
                self.versions = result
                self.selected_version = str(result[0]["version"]) if result else ""
                self.last_loaded_gw = c_gw
                self.is_loading = False
                if self.selected_version:
                    return AuditJournalState.load_snapshot(False)
                return

            self.is_loading = True

        def _fetch(gw):
            conn = get_connection()
            try:
                return load_audit_data(conn, gw)
            finally:
                conn.close()

        result = await asyncio.to_thread(_fetch, c_gw)

        async with self:
            if result:
                _audit_versions_cache[c_gw] = result
                self.versions = result
                self.selected_version = str(result[0]["version"])
            else:
                self.versions = []
                self.selected_version = ""
            self.last_loaded_gw = c_gw
            self.is_loading = False

        if self.selected_version:
            return AuditJournalState.load_snapshot(force_refresh)

    @rx.event(background=True)
    async def load_snapshot(self, force_refresh: bool = False):
        async with self:
            try:
                c_gw = int(self.selected_audit_gw)
                c_ver = int(self.selected_version) if self.selected_version else None
            except Exception:
                c_gw, c_ver = 1, None

            snap_key = f"{c_gw}_{c_ver}"

            if not force_refresh and snap_key in _audit_snapshot_cache:
                self.snapshot_data = _audit_snapshot_cache[snap_key]
                self.last_loaded_ver = str(c_ver) if c_ver else ""
                self.is_loading = False
                return

            self.is_loading = True

        if not c_ver:
            async with self:
                self.snapshot_data = {}
                self.last_loaded_ver = ""
                self.is_loading = False
            return

        def _fetch(gw, ver):
            conn = get_connection()
            try:
                return get_audit_snapshot(conn, gw, ver)
            finally:
                conn.close()

        result = await asyncio.to_thread(_fetch, c_gw, c_ver)

        async with self:
            if result:
                _audit_snapshot_cache[snap_key] = result
                self.snapshot_data = result
            else:
                self.snapshot_data = {}
            self.last_loaded_ver = str(c_ver) if c_ver else ""
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
            try:
                return lock_audit_version(conn, manager_id, selected_gw, current_gw)
            finally:
                conn.close()

        success, msg = await asyncio.to_thread(_lock, mgr_id, c_gw, curr_gw)

        async with self:
            self.is_loading = False
            self.status_message = f"Version {msg} locked successfully" if success else f"Error: {msg}"

        _audit_versions_cache.clear()
        _audit_snapshot_cache.clear()
        return AuditJournalState.load_data(True)

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
            try:
                return settle_audit_version(conn, selected_gw, selected_version)
            finally:
                conn.close()

        success, err = await asyncio.to_thread(_settle, c_gw, c_ver)

        async with self:
            self.is_loading = False
            self.status_message = "Settled successfully" if success else f"Error: {err}"

        _audit_snapshot_cache.clear()
        return AuditJournalState.load_snapshot(True)
