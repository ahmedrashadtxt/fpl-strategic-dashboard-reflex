"""Global state for the FPL Strategic Dashboard Reflex application."""
"""Compatibility module re-exporting AppState from states.base."""

import os
import requests
import reflex as rx
from backend.data import (
    ensure_database_ready,
    get_connection,
    get_global_gameweek_info,
)
from fpl_strategic_dashboard_reflex.states.base import AppState


class AppState(rx.State):
    """Global application state containing filters, manager preferences, and metadata."""

    # ── Manager & Session Filters ──────────────────────────────────────
    manager_id: str = ""
    manager_name: str = ""
    prompted_for_id: bool = False
    is_id_dialog_open: bool = False
    temp_manager_id: str = ""

    # ── Gameweek & Timing ──────────────────────────────────────────────
    current_gw: int = 1
    selected_gw: int = 1
    gw_name: str = "Gameweek 1"
    is_live: bool = False


    # ── Navigation & Views ─────────────────────────────────────────────
    selected_tab: str = "squad_analyzer"
    theme_mode: str = "dark"

    # ── Computed / Derived Properties ──────────────────────────────────
    @rx.var
    def display_title(self) -> str:
        if self.manager_name:
            return self.manager_name
        return "My Team"

    @rx.var
    def badge_label(self) -> str:
        if self.manager_id:
            return f"👤 {self.display_title} · #{self.manager_id} ✏️"
        return "➕ Enter FPL ID"

    @rx.var
    def gw_badge_text(self) -> str:
        if self.is_live:
            return f"● {self.gw_name.upper()}"
        return f"NEXT · {self.gw_name.upper()}"

    @rx.var
    def available_gameweeks(self) -> list[int]:
        return list(range(1, 39))

    # ── Lifecycle & Loading ────────────────────────────────────────────
    def on_load(self):
        """Initializes database and loads global gameweek & summary stats."""
        try:
            ensure_database_ready()
            conn = get_connection()
            events_df, next_gw, name = get_global_gameweek_info(conn)
            self.current_gw = int(next_gw)
            self.selected_gw = int(next_gw)
            self.gw_name = str(name)
            self.is_live = "(Live)" in str(name)

            
        except Exception as ex:
            print(f"Error loading initial database state: {ex}")

        # Check URL query param if present (use router.page.params — deprecated in 0.9, kept for compat)
        try:
            query_team = self.router.page.params.get("team", "")
        except Exception:
            query_team = ""
        if query_team and isinstance(query_team, str) and query_team.strip():
            self.manager_id = query_team.strip()
            self._fetch_manager_name(self.manager_id)
        elif not self.manager_id and not self.prompted_for_id:
            self.prompted_for_id = True
            self.open_id_dialog()

    def _fetch_manager_name(self, mgr_id: str):
        if not mgr_id:
            self.manager_name = ""
            return
        try:
            url = f"https://fantasy.premierleague.com/api/entry/{mgr_id}/"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                self.manager_name = data.get("name", "My Team")
        except Exception:
            pass

    # ── Event Handlers ─────────────────────────────────────────────────
    def set_tab(self, tab: str):
        self.selected_tab = tab

    def set_selected_gw(self, gw: str | int):
        try:
            self.selected_gw = int(gw)
        except (ValueError, TypeError):
            pass

    def open_id_dialog(self):
        self.temp_manager_id = self.manager_id
        self.is_id_dialog_open = True

    def close_id_dialog(self):
        self.is_id_dialog_open = False

    def set_temp_id(self, val: str):
        self.temp_manager_id = val

    def save_manager_id(self):
        cleaned = self.temp_manager_id.strip()
        self.manager_id = cleaned
        self.is_id_dialog_open = False
        if cleaned:
            self._fetch_manager_name(cleaned)
        else:
            self.manager_name = ""

    def toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        return rx.toggle_color_mode


State = AppState

__all__ = ["AppState", "State"]
