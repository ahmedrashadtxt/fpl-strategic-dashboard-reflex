"""Domain State for Monte Carlo Match Simulator."""

import asyncio
from typing import Any, Dict, List
import pandas as pd
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    get_manager_squad_ids,
    get_teams_fdr_map,
)
from fpl_strategic_dashboard_reflex.services.simulator import (
    build_odds_map,
    run_gameweek_simulation,
    run_head_to_head_simulation,
)
from fpl_strategic_dashboard_reflex.services.squad import get_cached_league_dream_15


class SimulatorState(AppState):
    """Sub-state managing Monte Carlo simulations and Head-to-Head stress-testing."""

    is_loading: bool = False
    status_message: str = "Running Monte Carlo iterations..."

    target_sim_gw: str = "1"
    squad_mode: str = "active"  # "active" or "dream15"
    iterations: int = 5000

    sim_mean: float = 0.0
    sim_median: float = 0.0
    sim_p10: float = 0.0
    sim_p25: float = 0.0
    sim_p75: float = 0.0
    sim_p90: float = 0.0
    sim_std: float = 0.0
    exec_time_ms: float = 0.0

    player_stats: List[Dict[str, Any]] = []

    # Head-to-Head comparison metrics
    h2h_enabled: bool = False
    h2h_win_pct_a: float = 0.0
    h2h_win_pct_b: float = 0.0
    h2h_draw_pct: float = 0.0
    h2h_median_a: float = 0.0
    h2h_median_b: float = 0.0

    @rx.var
    def has_results(self) -> bool:
        return len(self.player_stats) > 0

    def set_target_gw(self, gw: str):
        self.target_sim_gw = str(gw)

    def set_squad_mode(self, mode: str):
        self.squad_mode = mode
        return SimulatorState.run_simulation

    def set_iterations(self, val: list[int]):
        self.iterations = val[0]

    def toggle_h2h(self):
        self.h2h_enabled = not self.h2h_enabled
        if self.h2h_enabled:
            return SimulatorState.run_simulation

    @rx.event(background=True)
    async def run_simulation(self):
        async with self:
            self.is_loading = True
            self.status_message = "Generating probabilistic match matrices..."
            mgr_id = self.manager_id
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw) if int(self.target_sim_gw) > 0 else c_gw
            except Exception:
                t_gw = c_gw
            mode = self.squad_mode
            n_sims = self.iterations
            do_h2h = self.h2h_enabled

        def _execute():
            conn = get_connection()
            fdr_map = get_teams_fdr_map(conn, c_gw)

            fixtures_df = pd.read_sql(
                """
                SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                       f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
                FROM fixtures f
                WHERE f.event = ?
                """,
                conn,
                params=[t_gw],
            )
            odds_map = build_odds_map(conn, t_gw, fixtures_df, fdr_map)

            # Load squad
            if mode == "dream15":
                squad_df, _, _ = get_cached_league_dream_15(conn, c_gw, t_gw, 100.0)
            else:
                squad_ids = get_manager_squad_ids(mgr_id, t_gw)
                if squad_ids:
                    placeholders = ",".join(["?"] * len(squad_ids))
                    squad_df = pd.read_sql(
                        f"""
                        SELECT id, web_name AS Player, team AS team_id,
                               CASE element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
                               minutes, expected_goal_involvements_per_90 AS xGI_per_90
                        FROM players WHERE id IN ({placeholders})
                        """,
                        conn,
                        params=squad_ids,
                    )
                else:
                    squad_df = pd.DataFrame()

            if squad_df.empty:
                return None

            # XI selection: top 11
            starters_df = squad_df.head(11).copy()
            _, _, stats = run_gameweek_simulation(starters_df, odds_map, n_sims=n_sims)

            h2h_res = None
            if do_h2h:
                dream_df, _, _ = get_cached_league_dream_15(conn, c_gw, t_gw, 100.0)
                if not dream_df.empty:
                    h2h_res = run_head_to_head_simulation(starters_df, dream_df.head(11), odds_map, n_sims=n_sims)

            return stats, h2h_res

        result = await asyncio.to_thread(_execute)

        async with self:
            if result:
                stats, h2h = result
                self.sim_mean = stats.get("mean", 0.0)
                self.sim_median = stats.get("median", 0.0)
                self.sim_p10 = stats.get("p10_floor", 0.0)
                self.sim_p25 = stats.get("p25", 0.0)
                self.sim_p75 = stats.get("p75", 0.0)
                self.sim_p90 = stats.get("p90_ceiling", 0.0)
                self.sim_std = stats.get("std_dev", 0.0)
                self.exec_time_ms = stats.get("exec_time_ms", 0.0)
                self.player_stats = stats.get("player_stats", [])

                if h2h:
                    self.h2h_win_pct_a = h2h.get("win_pct_a", 0.0)
                    self.h2h_win_pct_b = h2h.get("win_pct_b", 0.0)
                    self.h2h_draw_pct = h2h.get("draw_pct", 0.0)
                    self.h2h_median_a = h2h.get("median_a", 0.0)
                    self.h2h_median_b = h2h.get("median_b", 0.0)
            self.is_loading = False

