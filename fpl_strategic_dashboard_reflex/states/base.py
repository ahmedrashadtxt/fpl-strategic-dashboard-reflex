"""Global base application state containing session preferences, gameweek info, and modals."""

import reflex as rx
import requests

from fpl_strategic_dashboard_reflex.services.db import (
    ensure_database_ready,
    get_connection,
    get_global_gameweek_info,
)


class AppState(rx.State):
    """Global application state containing filters, manager preferences, and metadata."""

    # Manager & Session Info
    manager_id: str = ""
    manager_name: str = ""
    mgr_name: str = ""
    prompted_for_id: bool = False
    is_id_dialog_open: bool = False
    temp_manager_id: str = ""

    # Gameweek & Timing
    current_gw: int = 1
    selected_gw: int = 1
    gw_name: str = "Gameweek 1"
    is_live: bool = False

    # Navigation & Views
    selected_tab: str = "squad_analyzer"
    theme_mode: str = "dark"

    # Global Manager Stats (shared across tabs & global stats panel)
    has_manager_data: bool = False
    overall_rank: int = 0
    rank_delta: str = ""
    rank_delta_color: str = "green"
    total_points: int = 0
    active_gw_pts: int = 0
    active_gw_label: str = "Active GW"
    gw_avg_pts: int = 0
    gw_avg_label: str = "GW Average"
    gw_avg_diff_str: str = ""
    hero_perf_status: str = "green"
    squad_value: float = 0.0
    bank_balance: float = 0.0

    # Computed / Derived Properties
    # Shared field written by TransferAnalyzerState and read by SimulatorState
    # (avoids cross-state get_state() in background tasks)
    shared_trans_squad: list = []

    @rx.var
    def has_data(self) -> bool:
        return self.has_manager_data

    @rx.var
    def squad_value_display(self) -> str:
        return f"£{self.squad_value:.2f}m"

    @rx.var
    def bank_balance_display(self) -> str:
        return f"£{self.bank_balance:.1f}m"

    @rx.var
    def active_gw_display(self) -> str:
        return f"{self.active_gw_pts} pts"

    @rx.var
    def gw_avg_display(self) -> str:
        return f"{self.gw_avg_pts} pts" if self.gw_avg_pts else "—"

    @rx.var
    def overall_rank_display(self) -> str:
        return f"{self.overall_rank:,}" if self.overall_rank else "0"

    @rx.var
    def display_title(self) -> str:
        if self.mgr_name:
            return self.mgr_name
        if self.manager_name:
            return self.manager_name
        return "My Team"

    @rx.var
    def badge_label(self) -> str:
        if self.manager_id:
            return f"Team · #{self.manager_id} (Edit)"
        return "Enter FPL ID"

    @rx.var
    def gw_badge_text(self) -> str:
        if self.is_live:
            return f"LIVE · {self.gw_name.upper()}"
        return f"NEXT · {self.gw_name.upper()}"

    @rx.var
    def available_gameweeks(self) -> list[str]:
        return [str(gw) for gw in range(1, 39)]

    @rx.var
    def example_url_gw(self) -> str:
        """Dynamic GW number for the ID dialog URL example.
        current_gw is always next_gw from DB; when live subtract 1 to get the actual live GW.
        """
        if self.is_live:
            return str(self.current_gw - 1)
        return str(self.current_gw)

    @rx.var
    def example_url_gw_label(self) -> str:
        """Label indicating live or completed for the ID dialog."""
        if self.is_live:
            gw = self.current_gw - 1
            return f"GW{gw} · Live now"
        return f"GW{self.current_gw} · Next upcoming"

    # Lifecycle & Loading
    def on_load(self):
        """Initializes database and loads global gameweek info."""
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

        # Check URL query param if present
        try:
            if hasattr(self.router, "url") and hasattr(self.router.url, "query"):
                query_team = self.router.url.query.get("team", "")
            else:
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

    # Event Handlers
    def set_tab(self, tab: str):
        self.selected_tab = tab
        if tab == "squad_analyzer":
            from fpl_strategic_dashboard_reflex.states.squad import SquadAnalyzerState
            return SquadAnalyzerState.load_squad
        elif tab == "transfer_solver":
            from fpl_strategic_dashboard_reflex.states.transfer import TransferAnalyzerState
            return TransferAnalyzerState.load_planner_data
        elif tab == "fixture_ticker":
            from fpl_strategic_dashboard_reflex.states.fixtures import FixtureTickerState
            return FixtureTickerState.on_tab_visible
        elif tab == "match_simulator":
            from fpl_strategic_dashboard_reflex.states.simulator import SimulatorState
            return SimulatorState.run_simulation
        elif tab == "defensive_stats":
            from fpl_strategic_dashboard_reflex.states.defensive import DefensiveStatsState
            return DefensiveStatsState.load_data
        elif tab == "expected_stats":
            from fpl_strategic_dashboard_reflex.states.expected import ExpectedStatsState
            return ExpectedStatsState.load_data
        elif tab == "rolling_form":
            from fpl_strategic_dashboard_reflex.states.rolling import RollingFormState
            return RollingFormState.load_data
        elif tab == "transfer_market":
            from fpl_strategic_dashboard_reflex.states.market import TransferMarketState
            return TransferMarketState.load_data

    def set_selected_gw(self, gw: str):
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

        from fpl_strategic_dashboard_reflex.states.squad import SquadAnalyzerState
        from fpl_strategic_dashboard_reflex.states.transfer import TransferAnalyzerState
        yield SquadAnalyzerState.refresh_squad
        yield TransferAnalyzerState.refresh_planner

    def toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        return rx.toggle_color_mode

