"""Domain State for Monte Carlo Match Simulator."""

import asyncio
import random
from typing import Any, Dict, List
import pandas as pd
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    get_teams_fdr_map,
    get_historical_player_baselines,
    get_fixture_for_team,
)
from fpl_strategic_dashboard_reflex.services.simulator import (
    build_odds_map,
    run_gameweek_simulation,
    run_head_to_head_simulation,
    load_active_squad,
    load_post_transfer_squad,
    evaluate_squad_for_gw,
    generate_random_15,
)
from fpl_strategic_dashboard_reflex.services.squad import (
    get_cached_league_dream_15,
    get_cached_league_eval_df,
)


_simulation_results_cache: Dict[str, Any] = {}


class SimulatorState(AppState):
    """Sub-state managing Monte Carlo simulations, flexible squad sources, and Head-to-Head stress-testing."""

    is_loading: bool = False
    status_message: str = "Running Monte Carlo iterations..."

    target_sim_gw: str = ""
    # Squad Modes: "active", "transfer_plan", "dream15", "sandbox"
    squad_mode: str = "active"
    iterations: int = 5000

    # Simulation Statistics
    sim_mean: float = 0.0
    sim_median: float = 0.0
    sim_p10: float = 0.0
    sim_p90: float = 0.0
    sim_std: float = 0.0
    exec_time_ms: float = 0.0

    player_stats: List[Dict[str, Any]] = []
    starting_xi: List[Dict[str, Any]] = []
    hist_data: List[Dict[str, Any]] = []
    captain_id: int = 0
    vc_id: int = 0

    # Head-to-Head comparison metrics
    h2h_enabled: bool = False
    h2h_win_pct_a: float = 0.0
    h2h_win_pct_b: float = 0.0
    h2h_draw_pct: float = 0.0
    h2h_median_a: float = 0.0
    h2h_median_b: float = 0.0
    h2h_benchmark_name: str = "Benchmark"

    # Transfer Plan Status
    has_transfer_plan: bool = True

    # Custom Sandbox State
    sandbox_selected_ids: List[int] = []
    sandbox_search: str = ""
    sandbox_pos_filter: str = "ALL"
    sandbox_pool: List[Dict[str, Any]] = []
    sandbox_is_loading_pool: bool = False

    # Cache tracking fields
    last_sim_mgr: str = ""
    last_sim_gw: int = 0
    last_sim_mode: str = ""
    last_sim_iters: int = 0
    last_sim_h2h: bool = False
    last_sim_sandbox_ids: List[int] = []

    # ── Computed Variables ─────────────────────────────────────────────────────

    @rx.var
    def sim_p10_str(self) -> str:
        return str(int(round(self.sim_p10)))

    @rx.var
    def sim_median_str(self) -> str:
        return str(int(round(self.sim_median)))

    @rx.var
    def sim_p90_str(self) -> str:
        return str(int(round(self.sim_p90)))

    @rx.var
    def median_label(self) -> str:
        return f"{self.sim_median:.1f} pts"

    @rx.var
    def floor_label(self) -> str:
        return f"{self.sim_p10:.1f} pts"

    @rx.var
    def ceiling_label(self) -> str:
        return f"{self.sim_p90:.1f} pts"

    @rx.var
    def volatility_label(self) -> str:
        return f"{self.sim_std:.1f}"

    @rx.var
    def exec_time_label(self) -> str:
        return f"(Executed in {self.exec_time_ms:.0f}ms)"

    @rx.var
    def has_results(self) -> bool:
        return len(self.player_stats) > 0

    @rx.var
    def available_sim_gws(self) -> List[str]:
        cur = max(1, self.current_gw)
        return [str(gw) for gw in range(cur, 39)]

    @rx.var
    def is_active_mode(self) -> bool:
        return self.squad_mode == "active"

    @rx.var
    def is_transfer_plan_mode(self) -> bool:
        return self.squad_mode == "transfer_plan"

    @rx.var
    def is_dream15_mode(self) -> bool:
        return self.squad_mode == "dream15"

    @rx.var
    def is_sandbox_mode(self) -> bool:
        return self.squad_mode == "sandbox"

    @rx.var
    def sandbox_selected_count(self) -> int:
        return len(self.sandbox_selected_ids)

    @rx.var
    def sandbox_selected_players(self) -> List[Dict[str, Any]]:
        id_set = set(self.sandbox_selected_ids)
        return [p for p in self.sandbox_pool if p.get("id") in id_set]

    @rx.var
    def sandbox_total_cost(self) -> float:
        total = sum(float(p.get("Cost", 0.0)) for p in self.sandbox_selected_players)
        return round(total, 1)

    @rx.var
    def sandbox_budget_remaining(self) -> float:
        return round(100.0 - self.sandbox_total_cost, 1)

    @rx.var
    def sandbox_gkp_count(self) -> int:
        return sum(1 for p in self.sandbox_selected_players if p.get("Pos") == "GKP")

    @rx.var
    def sandbox_def_count(self) -> int:
        return sum(1 for p in self.sandbox_selected_players if p.get("Pos") == "DEF")

    @rx.var
    def sandbox_mid_count(self) -> int:
        return sum(1 for p in self.sandbox_selected_players if p.get("Pos") == "MID")

    @rx.var
    def sandbox_fwd_count(self) -> int:
        return sum(1 for p in self.sandbox_selected_players if p.get("Pos") == "FWD")

    @rx.var
    def sandbox_team_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self.sandbox_selected_players:
            club = str(p.get("Team", ""))
            counts[club] = counts.get(club, 0) + 1
        return counts

    @rx.var
    def sandbox_max_team_count(self) -> int:
        counts = self.sandbox_team_counts
        return max(counts.values()) if counts else 0

    @rx.var
    def sandbox_violations(self) -> List[str]:
        v: List[str] = []
        cnt = self.sandbox_selected_count
        if cnt != 15:
            v.append(f"Requires exactly 15 players (currently {cnt}).")
        if self.sandbox_total_cost > 100.05:
            v.append(f"Squad cost (£{self.sandbox_total_cost:.1f}m) exceeds £100.0m budget.")
        if self.sandbox_gkp_count != 2:
            v.append(f"Requires exactly 2 GKP (currently {self.sandbox_gkp_count}).")
        if self.sandbox_def_count != 5:
            v.append(f"Requires exactly 5 DEF (currently {self.sandbox_def_count}).")
        if self.sandbox_mid_count != 5:
            v.append(f"Requires exactly 5 MID (currently {self.sandbox_mid_count}).")
        if self.sandbox_fwd_count != 3:
            v.append(f"Requires exactly 3 FWD (currently {self.sandbox_fwd_count}).")
        exceeded = [f"{t} ({c})" for t, c in self.sandbox_team_counts.items() if c > 3]
        if exceeded:
            v.append(f"Max 3 per club exceeded: {', '.join(exceeded)}.")
        return v

    @rx.var
    def sandbox_is_valid(self) -> bool:
        return len(self.sandbox_violations) == 0

    @rx.var
    def filtered_sandbox_pool(self) -> List[Dict[str, Any]]:
        pool = self.sandbox_pool
        if self.sandbox_pos_filter != "ALL":
            pool = [p for p in pool if p.get("Pos") == self.sandbox_pos_filter]

        search = self.sandbox_search.strip().lower()
        if search:
            pool = [
                p for p in pool
                if search in str(p.get("Player", "")).lower()
                or search in str(p.get("Team", "")).lower()
            ]

        selected_set = set(self.sandbox_selected_ids)

        # 1. All selected players matching current filter (never truncate selected players)
        selected_players = [p for p in pool if p.get("id") in selected_set]
        selected_players.sort(
            key=lambda x: float(x.get("Proj_Pts", 0.0)),
            reverse=True,
        )

        # 2. Unselected players matching current filter, sorted by projected points
        unselected_players = [p for p in pool if p.get("id") not in selected_set]
        unselected_players.sort(
            key=lambda x: float(x.get("Proj_Pts", 0.0)),
            reverse=True,
        )

        # All selected players appear at top, followed by top unselected candidates
        return selected_players + unselected_players[:150]

    # ── Action Methods ─────────────────────────────────────────────────────────

    @rx.event
    def refresh_simulation(self):
        """Explicitly re-runs Monte Carlo simulation bypassing caches."""
        _simulation_results_cache.clear()
        return SimulatorState.run_simulation(True)

    def set_target_gw(self, gw: str):
        self.target_sim_gw = str(gw)
        if self.squad_mode == "sandbox":
            return SimulatorState.load_sandbox_pool
        return SimulatorState.run_simulation(False)

    def set_squad_mode(self, mode: str):
        self.squad_mode = mode
        if mode == "sandbox" and len(self.sandbox_pool) == 0:
            return SimulatorState.load_sandbox_pool
        return SimulatorState.run_simulation(False)

    def set_iterations(self, iters: int):
        self.iterations = iters
        return SimulatorState.run_simulation(False)

    def toggle_h2h(self):
        self.h2h_enabled = not self.h2h_enabled
        if self.h2h_enabled:
            return SimulatorState.run_simulation(False)

    def go_to_transfer_solver(self):
        self.selected_tab = "transfer_analyzer"

    def set_sandbox_search(self, val: str):
        self.sandbox_search = val

    def set_sandbox_pos_filter(self, pos: str):
        self.sandbox_pos_filter = pos

    def toggle_sandbox_player(self, player_id: int):
        cur_ids = set(self.sandbox_selected_ids)
        if player_id in cur_ids:
            cur_ids.remove(player_id)
            self.sandbox_selected_ids = list(cur_ids)
            return

        # Check limits before adding
        if len(cur_ids) >= 15:
            return rx.toast.warning("Cannot select more than 15 players.")

        # Find player info
        p_info = next((p for p in self.sandbox_pool if p.get("id") == player_id), None)
        if not p_info:
            return

        pos = p_info.get("Pos")
        team = p_info.get("Team")
        cost = float(p_info.get("Cost", 0.0))

        if self.sandbox_total_cost + cost > 100.05:
            return rx.toast.warning(f"Budget exceeded: adding {p_info.get('Player')} would exceed £100.0m.")

        if pos == "GKP" and self.sandbox_gkp_count >= 2:
            return rx.toast.warning("Position limit reached: Max 2 Goalkeepers.")
        if pos == "DEF" and self.sandbox_def_count >= 5:
            return rx.toast.warning("Position limit reached: Max 5 Defenders.")
        if pos == "MID" and self.sandbox_mid_count >= 5:
            return rx.toast.warning("Position limit reached: Max 5 Midfielders.")
        if pos == "FWD" and self.sandbox_fwd_count >= 3:
            return rx.toast.warning("Position limit reached: Max 3 Forwards.")

        if self.sandbox_team_counts.get(team, 0) >= 3:
            return rx.toast.warning(f"Club limit reached: Max 3 players from {team}.")

        cur_ids.add(player_id)
        self.sandbox_selected_ids = list(cur_ids)

    def clear_sandbox(self):
        self.sandbox_selected_ids = []

    @rx.event(background=True)
    async def load_sandbox_random_15(self):
        async with self:
            if not self.sandbox_pool:
                return
            pool_data = self.sandbox_pool

        def _gen():
            df = pd.DataFrame(pool_data)
            return generate_random_15(df)

        random_ids = await asyncio.to_thread(_gen)
        async with self:
            if random_ids:
                self.sandbox_selected_ids = random_ids

        if random_ids:
            return rx.toast.success("Loaded random 15-player squad within £100m budget!")
        else:
            return rx.toast.warning("Could not generate valid random squad. Try again.")

    @rx.event(background=True)
    async def load_sandbox_budget_15(self):
        async with self:
            self.is_loading = True
            self.status_message = "Solving Budget Dream 15 squad..."
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw)
            except Exception:
                t_gw = c_gw

        def _solve():
            conn = get_connection()
            try:
                d_xi, d_bench, _ = get_cached_league_dream_15(conn, c_gw, t_gw, total_budget=100.0)
                if not d_xi.empty:
                    return pd.concat([d_xi, d_bench], ignore_index=True)["id"].tolist()
            finally:
                conn.close()
            return []

        ids = await asyncio.to_thread(_solve)
        async with self:
            if ids:
                self.sandbox_selected_ids = ids
            self.is_loading = False

        if ids:
            return rx.toast.success("Loaded optimal Budget Dream 15 into Sandbox!")
        else:
            return rx.toast.warning("Could not solve Budget Dream 15 squad.")

    @rx.event(background=True)
    async def load_sandbox_post_transfer_15(self):
        async with self:
            self.is_loading = True
            self.status_message = "Loading Post-Transfer squad into Sandbox..."
            mgr_id = self.manager_id
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw) if self.target_sim_gw and int(self.target_sim_gw) > 0 else c_gw
            except Exception:
                t_gw = c_gw
            if not self.target_sim_gw:
                self.target_sim_gw = str(t_gw)
            state_trans_squad = [dict(p) for p in (self.shared_trans_squad or [])]

        def _fetch():
            conn = get_connection()
            try:
                df = load_post_transfer_squad(conn, mgr_id, t_gw, state_trans_squad)
                if df.empty or "id" not in df.columns:
                    return [], []

                fixtures_df = pd.read_sql(
                    """
                    SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                           th.short_name AS Home_Team, ta.short_name AS Away_Team,
                           f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
                    FROM fixtures f
                    INNER JOIN teams th ON f.team_h = th.id
                    INNER JOIN teams ta ON f.team_a = ta.id
                    WHERE f.event >= 1 AND f.event <= 38
                    """,
                    conn,
                )
                eval_df = get_cached_league_eval_df(
                    conn, c_gw, t_gw, enable_betting=True, market_weight=0.35, factor_movement=True, only_available=False
                )
                eval_map = {int(r["id"]): r for _, r in eval_df.iterrows()} if not eval_df.empty else {}

                ids = [int(x) for x in df["id"].tolist()]
                records = []
                for _, r in df.iterrows():
                    photo_val = r.get("photo")
                    if photo_val and str(photo_val).strip() != "" and "Photo-Missing" not in str(photo_val):
                        photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(photo_val).replace('.jpg', '.png')}"
                    else:
                        photo_url = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"

                    p_id = int(r["id"])
                    if p_id in eval_map:
                        ev = eval_map[p_id]
                        opp = str(ev.get("Opponent", "Blank"))
                        fdr = int(ev.get("FDR", 3))
                        proj = round(float(ev.get("Proj_Pts", 0.0)), 1)
                    else:
                        t_id = int(r.get("team_id", 1))
                        fix = get_fixture_for_team(fixtures_df, t_id, t_gw)
                        opp = str(fix.get("opponent", "Blank"))
                        fdr = int(fix.get("fdr", 3))
                        proj = round(float(r.get("Form", 0.0) or 0.0), 1)

                    records.append({
                        "id": p_id,
                        "Player": str(r.get("Player", "")),
                        "Team": str(r.get("Club", r.get("Team", ""))),
                        "Pos": str(r.get("Pos", "MID")),
                        "Cost": float(r.get("Cost", 5.0)),
                        "Proj_Pts": proj,
                        "Opponent": opp,
                        "FDR": fdr,
                        "photo": photo_url,
                        "minutes": int(r.get("minutes", 0) if pd.notna(r.get("minutes")) else 0),
                        "xGI_per_90": float(r.get("xGI_per_90", 0.0) or 0.0),
                    })
                return ids, records
            finally:
                conn.close()

        ids, records = await asyncio.to_thread(_fetch)
        async with self:
            if ids:
                self.sandbox_selected_ids = ids
                pool_id_to_idx = {p.get("id"): idx for idx, p in enumerate(self.sandbox_pool)}
                for rec in records:
                    if rec["id"] in pool_id_to_idx:
                        self.sandbox_pool[pool_id_to_idx[rec["id"]]] = rec
                    else:
                        self.sandbox_pool.append(rec)
            self.is_loading = False

        if ids:
            return rx.toast.success(f"Loaded Post-Transfer squad ({len(ids)} players) into Custom Sandbox!")
        else:
            return rx.toast.warning("No Post-Transfer Plan found. Solve transfers in the Transfer Solver tab first.")

    @rx.event(background=True)
    async def load_sandbox_my_squad(self):
        async with self:
            self.is_loading = True
            self.status_message = "Loading Active Squad into Sandbox..."
            mgr_id = self.manager_id
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw) if self.target_sim_gw and int(self.target_sim_gw) > 0 else c_gw
            except Exception:
                t_gw = c_gw
            if not self.target_sim_gw:
                self.target_sim_gw = str(t_gw)

        def _fetch():
            conn = get_connection()
            try:
                df = load_active_squad(conn, mgr_id, t_gw)
                if df.empty or "id" not in df.columns:
                    return [], []

                fixtures_df = pd.read_sql(
                    """
                    SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                           th.short_name AS Home_Team, ta.short_name AS Away_Team,
                           f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
                    FROM fixtures f
                    INNER JOIN teams th ON f.team_h = th.id
                    INNER JOIN teams ta ON f.team_a = ta.id
                    WHERE f.event >= 1 AND f.event <= 38
                    """,
                    conn,
                )
                eval_df = get_cached_league_eval_df(
                    conn, c_gw, t_gw, enable_betting=True, market_weight=0.35, factor_movement=True, only_available=False
                )
                eval_map = {int(r["id"]): r for _, r in eval_df.iterrows()} if not eval_df.empty else {}

                ids = [int(x) for x in df["id"].tolist()]
                records = []
                for _, r in df.iterrows():
                    photo_val = r.get("photo")
                    if photo_val and str(photo_val).strip() != "" and "Photo-Missing" not in str(photo_val):
                        photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(photo_val).replace('.jpg', '.png')}"
                    else:
                        photo_url = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"

                    p_id = int(r["id"])
                    if p_id in eval_map:
                        ev = eval_map[p_id]
                        opp = str(ev.get("Opponent", "Blank"))
                        fdr = int(ev.get("FDR", 3))
                        proj = round(float(ev.get("Proj_Pts", 0.0)), 1)
                    else:
                        t_id = int(r.get("team_id", 1))
                        fix = get_fixture_for_team(fixtures_df, t_id, t_gw)
                        opp = str(fix.get("opponent", "Blank"))
                        fdr = int(fix.get("fdr", 3))
                        proj = round(float(r.get("Form", 0.0) or 0.0), 1)

                    records.append({
                        "id": p_id,
                        "Player": str(r.get("Player", "")),
                        "Team": str(r.get("Club", r.get("Team", ""))),
                        "Pos": str(r.get("Pos", "MID")),
                        "Cost": float(r.get("Cost", 5.0)),
                        "Proj_Pts": proj,
                        "Opponent": opp,
                        "FDR": fdr,
                        "photo": photo_url,
                        "minutes": int(r.get("minutes", 0) if pd.notna(r.get("minutes")) else 0),
                        "xGI_per_90": float(r.get("xGI_per_90", 0.0) or 0.0),
                    })
                return ids, records
            finally:
                conn.close()

        ids, records = await asyncio.to_thread(_fetch)
        async with self:
            if ids:
                self.sandbox_selected_ids = ids
                pool_id_to_idx = {p.get("id"): idx for idx, p in enumerate(self.sandbox_pool)}
                for rec in records:
                    if rec["id"] in pool_id_to_idx:
                        self.sandbox_pool[pool_id_to_idx[rec["id"]]] = rec
                    else:
                        self.sandbox_pool.append(rec)
            self.is_loading = False

        if ids:
            return rx.toast.success(f"Loaded Active Squad ({len(ids)} players) into Custom Sandbox!")
        else:
            return rx.toast.warning("Could not load Active Squad. Make sure your Manager ID is entered.")

    @rx.event(background=True)
    async def load_sandbox_pool(self):
        async with self:
            self.sandbox_is_loading_pool = True
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw) if self.target_sim_gw and int(self.target_sim_gw) > 0 else c_gw
            except Exception:
                t_gw = c_gw
            if not self.target_sim_gw:
                self.target_sim_gw = str(t_gw)
            cur_selected_ids = list(self.sandbox_selected_ids)

        def _fetch():
            conn = get_connection()
            try:
                fixtures_df = pd.read_sql(
                    """
                    SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                           th.short_name AS Home_Team, ta.short_name AS Away_Team,
                           f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
                    FROM fixtures f
                    INNER JOIN teams th ON f.team_h = th.id
                    INNER JOIN teams ta ON f.team_a = ta.id
                    WHERE f.event >= 1 AND f.event <= 38
                    """,
                    conn,
                )
                eval_df = get_cached_league_eval_df(
                    conn, c_gw, t_gw, enable_betting=True, market_weight=0.35, factor_movement=True, only_available=False
                )
                if eval_df.empty:
                    eval_df = pd.DataFrame()

                # Format photo URLs and opponent
                records = []
                for _, r in eval_df.iterrows():
                    photo_val = r.get("photo")
                    if pd.notna(photo_val) and str(photo_val).strip() != "" and "Photo-Missing" not in str(photo_val):
                        photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(photo_val).replace('.jpg', '.png')}"
                    else:
                        photo_url = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"

                    records.append({
                        "id": int(r["id"]),
                        "Player": str(r.get("Player", "")),
                        "Team": str(r.get("Team", "")),
                        "Pos": str(r.get("Pos", "MID")),
                        "Cost": float(r.get("Cost", 5.0)),
                        "Proj_Pts": round(float(r.get("Proj_Pts", 0.0)), 1),
                        "Opponent": str(r.get("Opponent", "")),
                        "FDR": int(r.get("FDR", 3)),
                        "photo": photo_url,
                        "minutes": int(r.get("minutes", 0)),
                        "xGI_per_90": float(r.get("xGI_per_90", 0.0) or 0.0),
                    })

                # Check if any selected player IDs are missing from records
                existing_ids = {rec["id"] for rec in records}
                missing_ids = [pid for pid in cur_selected_ids if pid not in existing_ids]
                if missing_ids:
                    placeholders = ",".join(["?"] * len(missing_ids))
                    missing_df = pd.read_sql_query(
                        f"""
                        SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
                               t.short_name AS Team,
                               CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
                               p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
                               p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
                               p.expected_goal_involvements_per_90 AS xGI_per_90
                        FROM players p
                        INNER JOIN teams t ON p.team = t.id
                        WHERE p.id IN ({placeholders})
                        """,
                        conn,
                        params=missing_ids,
                    )
                    for _, r in missing_df.iterrows():
                        photo_val = r.get("photo")
                        if pd.notna(photo_val) and str(photo_val).strip() != "" and "Photo-Missing" not in str(photo_val):
                            photo_url = f"https://resources.premierleague.com/premierleague/photos/players/110x140/p{str(photo_val).replace('.jpg', '.png')}"
                        else:
                            photo_url = "https://fantasy.premierleague.com/dist/img/shirts/standard/shirt_0-66.webp"
                        fix = get_fixture_for_team(fixtures_df, int(r.get("team_id", 1)), t_gw)
                        records.append({
                            "id": int(r["id"]),
                            "Player": str(r.get("Player", "")),
                            "Team": str(r.get("Team", "")),
                            "Pos": str(r.get("Pos", "MID")),
                            "Cost": float(r.get("Cost", 5.0)),
                            "Proj_Pts": round(float(r.get("Form", 0.0) or 0.0), 1),
                            "Opponent": str(fix.get("opponent", "Blank")),
                            "FDR": int(fix.get("fdr", 3)),
                            "photo": photo_url,
                            "minutes": int(r.get("minutes", 0)),
                            "xGI_per_90": float(r.get("xGI_per_90", 0.0) or 0.0),
                        })

                return records
            finally:
                conn.close()

        pool_res = await asyncio.to_thread(_fetch)
        async with self:
            self.sandbox_pool = pool_res
            self.sandbox_is_loading_pool = False

    # ── Simulation Runner ──────────────────────────────────────────────────────

    def _apply_simulation_result(self, res, mgr_id, t_gw, mode, n_sims, do_h2h, sandbox_ids):
        if res and res[0] is not None:
            stats, xi_list, h2h, cap_id, vc_id, has_tp = res
            self.sim_mean = float(stats.get("mean", 0.0))
            self.sim_median = float(stats.get("median", 0.0))
            self.sim_p10 = float(stats.get("p10_floor", 0.0))
            self.sim_p90 = float(stats.get("p90_ceiling", 0.0))
            self.sim_std = float(stats.get("std_dev", 0.0))
            self.exec_time_ms = float(stats.get("exec_time_ms", 0.0))
            self.player_stats = stats.get("player_stats", [])
            self.hist_data = stats.get("hist_data", [])
            self.starting_xi = xi_list or []
            self.captain_id = int(cap_id) if cap_id is not None else 0
            self.vc_id = int(vc_id) if vc_id is not None else 0
            self.has_transfer_plan = bool(has_tp)
            self.last_sim_mgr = str(mgr_id)
            self.last_sim_gw = int(t_gw)
            self.last_sim_mode = str(mode)
            self.last_sim_iters = int(n_sims)
            self.last_sim_h2h = bool(do_h2h)
            self.last_sim_sandbox_ids = [int(x) for x in sandbox_ids]

            if h2h:
                self.h2h_win_pct_a = float(h2h.get("win_pct_a", 0.0))
                self.h2h_win_pct_b = float(h2h.get("win_pct_b", 0.0))
                self.h2h_draw_pct = float(h2h.get("draw_pct", 0.0))
                self.h2h_median_a = float(h2h.get("median_a", 0.0))
                self.h2h_median_b = float(h2h.get("median_b", 0.0))
                self.h2h_benchmark_name = str(h2h.get("benchmark_name", "Benchmark"))
            else:
                self.h2h_benchmark_name = ""
        else:
            has_tp = res[5] if (res and len(res) >= 6) else False
            self.has_transfer_plan = has_tp
            self.player_stats = []
            self.starting_xi = []
            self.hist_data = []
            self.sim_mean = 0.0
            self.sim_median = 0.0
            self.sim_p10 = 0.0
            self.sim_p90 = 0.0
            self.sim_std = 0.0

    @rx.event(background=True)
    async def run_simulation(self, force_refresh: bool = False):
        state_trans_squad = []
        async with self:
            mgr_id = self.manager_id
            c_gw = self.current_gw
            try:
                t_gw = int(self.target_sim_gw) if self.target_sim_gw and int(self.target_sim_gw) > 0 else c_gw
            except Exception:
                t_gw = c_gw
            if not self.target_sim_gw:
                self.target_sim_gw = str(t_gw)
            mode = self.squad_mode
            n_sims = self.iterations
            do_h2h = self.h2h_enabled
            sandbox_ids = list(self.sandbox_selected_ids)

            cache_key = f"{mgr_id}_{c_gw}_{t_gw}_{mode}_{n_sims}_{do_h2h}_{','.join(str(x) for x in sorted(sandbox_ids)) if mode == 'sandbox' else ''}"

            if not force_refresh and cache_key in _simulation_results_cache:
                self._apply_simulation_result(_simulation_results_cache[cache_key], mgr_id, t_gw, mode, n_sims, do_h2h, sandbox_ids)
                self.is_loading = False
                return

            self.is_loading = True
            self.status_message = "Modeling probabilistic match outcomes..."
            # Read post-transfer squad from shared AppState field (no cross-state get_state needed)
            state_trans_squad = [dict(p) for p in (self.shared_trans_squad or [])]

        def _execute():
            conn = get_connection()
            try:
                fdr_map = get_teams_fdr_map(conn, c_gw)
                fixtures_df = pd.read_sql(
                    """
                    SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
                           th.short_name AS Home_Team, ta.short_name AS Away_Team,
                           f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
                    FROM fixtures f
                    INNER JOIN teams th ON f.team_h = th.id
                    INNER JOIN teams ta ON f.team_a = ta.id
                    WHERE f.event = ?
                    """,
                    conn,
                    params=[t_gw],
                )
                odds_map = build_odds_map(conn, t_gw, fixtures_df, fdr_map)

                # 1. Load Primary Squad
                squad_df = pd.DataFrame()
                has_tp = True

                if mode == "active":
                    squad_df = load_active_squad(conn, mgr_id, t_gw)
                elif mode == "transfer_plan":
                    squad_df = load_post_transfer_squad(conn, mgr_id, t_gw, state_trans_squad)
                    if squad_df.empty:
                        has_tp = False
                elif mode == "dream15":
                    d_xi, d_bench, _ = get_cached_league_dream_15(conn, c_gw, t_gw, total_budget=100.0)
                    if not d_xi.empty:
                        squad_df = pd.concat([d_xi, d_bench], ignore_index=True)
                elif mode == "sandbox":
                    if len(sandbox_ids) == 15:
                        placeholders = ",".join(["?"] * len(sandbox_ids))
                        squad_df = pd.read_sql(
                            f"""
                            SELECT p.id, p.code, p.photo, p.web_name AS Player, p.team AS team_id,
                                   t.short_name AS Club,
                                   CASE p.element_type WHEN 1 THEN 'GKP' WHEN 2 THEN 'DEF' WHEN 3 THEN 'MID' WHEN 4 THEN 'FWD' END AS Pos,
                                   p.now_cost / 10.0 AS Cost, p.minutes AS minutes,
                                   p.total_points AS Season_Points, p.form AS Form, p.points_per_game AS PPG,
                                   p.status AS Status, p.chance_of_playing_next_round AS Chance,
                                   p.expected_goal_involvements_per_90 AS xGI_per_90
                            FROM players p
                            INNER JOIN teams t ON p.team = t.id
                            WHERE p.id IN ({placeholders})
                            """,
                            conn,
                            params=sandbox_ids,
                        )

                if squad_df.empty:
                    return None, None, None, None, None, has_tp

                # 2. Evaluate squad & solve optimal XI
                opt_xi, opt_bench, cap_id, vc_id = evaluate_squad_for_gw(
                    conn, squad_df, t_gw, fixtures_df, odds_map
                )
                cap_id = int(cap_id) if cap_id is not None else 0
                vc_id = int(vc_id) if vc_id is not None else 0

                # Format starting XI for UI preview
                starting_xi_records = []
                for _, r in opt_xi.iterrows():
                    starting_xi_records.append({
                        "id": int(r["id"]),
                        "Player": str(r.get("Player", "")),
                        "Club": str(r.get("Club", "")),
                        "Pos": str(r.get("Pos", "")),
                        "Proj_Pts": f"{float(r.get('Proj_Pts', 0.0)):.2f}",
                        "is_captain": bool(int(r["id"]) == cap_id),
                        "is_vc": bool(int(r["id"]) == vc_id),
                        "photo": str(r.get("photo", "")),
                    })

                # 3. Execute Monte Carlo simulation for Starting XI
                totals, _, stats = run_gameweek_simulation(
                    opt_xi, odds_map, n_sims=n_sims, captain_id=cap_id, vc_id=vc_id
                )

                # 4. Head-to-Head Benchmark Simulation (if enabled)
                h2h_res = None
                benchmark_name = "Budget Dream 15"

                if do_h2h:
                    benchmark_df = pd.DataFrame()
                    # If simulating active squad and post-transfer plan is available, compare vs transfer plan
                    if mode == "active":
                        tp_df = load_post_transfer_squad(conn, mgr_id, t_gw, state_trans_squad)
                        if not tp_df.empty:
                            benchmark_df = tp_df
                            benchmark_name = "Post-Transfer Plan"

                    # Otherwise benchmark against Budget Dream 15
                    if benchmark_df.empty:
                        b_xi, b_bench, _ = get_cached_league_dream_15(conn, c_gw, t_gw, total_budget=100.0)
                        if not b_xi.empty:
                            benchmark_df = pd.concat([b_xi, b_bench], ignore_index=True)
                            benchmark_name = "Budget Dream 15"

                    if not benchmark_df.empty:
                        opt_b_xi, _, cap_b, vc_b = evaluate_squad_for_gw(
                            conn, benchmark_df, t_gw, fixtures_df, odds_map
                        )
                        h2h_res = run_head_to_head_simulation(
                            opt_xi, opt_b_xi, odds_map, n_sims=n_sims,
                            cap_a=cap_id, vc_a=vc_id,
                            cap_b=int(cap_b) if cap_b is not None else None,
                            vc_b=int(vc_b) if vc_b is not None else None
                        )
                        h2h_res["benchmark_name"] = benchmark_name

                return stats, starting_xi_records, h2h_res, cap_id, vc_id, has_tp
            finally:
                conn.close()

        res = await asyncio.to_thread(_execute)

        async with self:
            if res and res[0] is not None:
                _simulation_results_cache[cache_key] = res
            self._apply_simulation_result(res, mgr_id, t_gw, mode, n_sims, do_h2h, sandbox_ids)
            self.is_loading = False
