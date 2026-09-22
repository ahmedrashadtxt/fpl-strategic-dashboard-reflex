"""Domain State for Transfer Analyzer / Solver."""

import asyncio
from typing import Any, Dict, List
import reflex as rx

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.transfer import (
    fetch_transfer_planner_data,
    analyze_transfers,
)


class TransferAnalyzerState(AppState):
    """Sub-state managing multi-gameweek transfer optimization, budget, and swaps."""

    is_loading: bool = False
    is_solving: bool = False
    status_message: str = "Loading transfer planner..."
    has_solved: bool = False

    # Strategy Mode: "Regular Transfers", "Wildcard", "Free Hit"
    strategy_mode: str = "Regular Transfers"

    next_gw: int = 5
    horizon_len: int = 5
    selected_horizon_label: str = "Next 5 Gameweeks (GW5–GW9)"

    ft_count: int = 1
    max_hits: int = 0

    pitch_view: bool = True
    enable_betting: bool = True
    market_weight: float = 0.35
    min_mins: int = 45

    bank_balance: float = 0.0
    squad_sell: float = 100.0
    team_value: float = 100.0

    pos_options: List[Dict[str, str]] = []
    neg_options: List[Dict[str, str]] = []
    selected_positive: List[str] = []
    selected_negative: List[str] = []

    pos_search: str = ""
    neg_search: str = ""

    swaps: List[Dict[str, Any]] = []

    base_starters: List[Dict[str, Any]] = []
    base_bench: List[Dict[str, Any]] = []
    trans_starters: List[Dict[str, Any]] = []
    trans_bench: List[Dict[str, Any]] = []

    base_pitch_html: str = ""
    comp_pitch_html: str = ""
    last_loaded_manager_id: str = ""
    last_loaded_horizon: int = 0

    metrics: Dict[str, Any] = {
        "bank_after": 0.0,
        "team_value": 0.0,
        "squad_sell": 0.0,
        "old_xp": 0.0,
        "new_xp": 0.0,
        "xp_diff": 0.0,
        "net_gain": 0.0,
        "hit_cost": 0,
        "moves_count": 0,
        "allowed_moves": 1,
    }

    # ── Computed Vars ──────────────────────────────────────────────────────────

    @rx.var
    def has_data(self) -> bool:
        return len(self.base_starters) > 0

    @rx.var
    def is_regular(self) -> bool:
        return self.strategy_mode == "Regular Transfers"

    @rx.var
    def is_wildcard(self) -> bool:
        return self.strategy_mode == "Wildcard"

    @rx.var
    def is_free_hit(self) -> bool:
        return self.strategy_mode == "Free Hit"

    @rx.var
    def horizon_options(self) -> List[str]:
        gw = self.next_gw
        if self.strategy_mode == "Wildcard":
            return [
                f"Next {x} Gameweeks (GW{gw}–GW{gw + x - 1})"
                for x in [3, 5, 8]
            ]
        elif self.strategy_mode == "Free Hit":
            return [f"Next 1 Gameweek (GW{gw}–GW{gw})"]
        else:
            return [
                f"Next {x} Gameweek{'s' if x > 1 else ''} (GW{gw}–GW{gw + x - 1})"
                for x in [1, 2, 3, 5]
            ]

    @rx.var
    def total_allowed_transfers(self) -> int:
        if self.strategy_mode in ["Wildcard", "Free Hit"]:
            return 15
        return int(self.ft_count) + int(self.max_hits)

    @rx.var
    def planned_moves_text(self) -> str:
        if self.strategy_mode in ["Wildcard", "Free Hit"]:
            return "15 Transfers"
        return f"{self.total_allowed_transfers} Transfers"

    @rx.var
    def hits_penalty_text(self) -> str:
        if self.strategy_mode == "Regular Transfers" and self.max_hits > 0:
            return f"(-{self.max_hits * 4} pts)"
        return ""

    @rx.var
    def has_hit_penalty(self) -> bool:
        return self.strategy_mode == "Regular Transfers" and self.max_hits > 0

    @rx.var
    def team_val_display(self) -> str:
        return f"£{self.team_value:.1f}m"

    @rx.var
    def squad_sell_display(self) -> str:
        return f"£{self.squad_sell:.1f}m"

    @rx.var
    def bank_display(self) -> str:
        return f"£{self.bank_balance:.1f}m"

    @rx.var
    def has_swaps(self) -> bool:
        return len(self.swaps) > 0

    @rx.var
    def metric_starting_xp(self) -> str:
        new_xp = self.metrics.get("new_xp", 0.0) if isinstance(self.metrics, dict) else 0.0
        return f"{float(new_xp):.1f} xP"

    @rx.var
    def metric_starting_delta(self) -> str:
        diff = self.metrics.get("xp_diff", 0.0) if isinstance(self.metrics, dict) else 0.0
        return f"{float(diff):+.1f} Raw xP"

    @rx.var
    def metric_net_gain(self) -> str:
        gain = self.metrics.get("net_gain", 0.0) if isinstance(self.metrics, dict) else 0.0
        return f"{float(gain):+.1f} xP"

    @rx.var
    def metric_net_delta(self) -> str:
        hit = self.metrics.get("hit_cost", 0) if isinstance(self.metrics, dict) else 0
        if hit > 0:
            return f"-{hit} Hit Penalty"
        return "Free Transfers"

    @rx.var
    def metric_bank_after(self) -> str:
        bank = self.metrics.get("bank_after", 0.0) if isinstance(self.metrics, dict) else 0.0
        return f"£{float(bank):.1f}m"

    @rx.var
    def metric_moves_executed(self) -> str:
        moves = self.metrics.get("moves_count", 0) if isinstance(self.metrics, dict) else 0
        allowed = self.metrics.get("allowed_moves", 1) if isinstance(self.metrics, dict) else 1
        return f"{moves} of {allowed}"

    @rx.var
    def solved_route_title(self) -> str:
        if self.strategy_mode == "Wildcard":
            return "Optimal Wildcard Squad (Permanent Overhaul, 0 Hits)"
        elif self.strategy_mode == "Free Hit":
            return "Optimal Free Hit Squad (1-Week Maximum Ceiling, 0 Hits)"
        else:
            hit = self.metrics.get("hit_cost", 0) if isinstance(self.metrics, dict) else 0
            hit_str = f"-{hit} pts" if hit > 0 else "0 pts"
            moves = self.metrics.get("moves_count", 0) if isinstance(self.metrics, dict) else len(self.swaps)
            return f"Optimal Transfer Route ({moves} moves, {hit_str})"

    @rx.var
    def solved_starting_title(self) -> str:
        return f"Starting XI {self.horizon_len}-GW xP"

    @rx.var
    def market_weight_pct(self) -> list[int]:
        return [int(round(self.market_weight * 100))]

    @rx.var
    def market_weight_display(self) -> str:
        return f"{self.market_weight:.2f}"

    @rx.var
    def filtered_pos_options(self) -> List[Dict[str, str]]:
        if not self.pos_search:
            return self.pos_options[:45]
        term = self.pos_search.lower().strip()
        return [
            opt for opt in self.pos_options
            if term in opt.get("search_text", "").lower()
            or term in opt.get("name", "").lower()
            or term in opt.get("label", "").lower()
        ][:50]

    @rx.var
    def filtered_neg_options(self) -> List[Dict[str, str]]:
        if not self.neg_search:
            return self.neg_options[:45]
        term = self.neg_search.lower().strip()
        return [
            opt for opt in self.neg_options
            if term in opt.get("search_text", "").lower()
            or term in opt.get("name", "").lower()
            or term in opt.get("label", "").lower()
        ][:50]

    @rx.var
    def has_pos_options(self) -> bool:
        return len(self.filtered_pos_options) > 0

    @rx.var
    def has_neg_options(self) -> bool:
        return len(self.filtered_neg_options) > 0

    @rx.var
    def selected_pos_items(self) -> List[Dict[str, str]]:
        selected_set = set(self.selected_positive)
        return [opt for opt in self.pos_options if opt.get("id") in selected_set]

    @rx.var
    def selected_neg_items(self) -> List[Dict[str, str]]:
        selected_set = set(self.selected_negative)
        return [opt for opt in self.neg_options if opt.get("id") in selected_set]

    @rx.var
    def pos_placeholder(self) -> str:
        cnt = len(self.selected_positive)
        if cnt == 0:
            return "Choose options"
        return f"{cnt} selected"

    @rx.var
    def neg_placeholder(self) -> str:
        cnt = len(self.selected_negative)
        if cnt == 0:
            return "Choose options"
        return f"{cnt} selected"

    # ── Actions & Event Handlers ───────────────────────────────────────────────

    def set_strategy_mode(self, mode: str):
        self.strategy_mode = mode
        gw = self.next_gw
        if mode == "Wildcard":
            self.horizon_len = 5
            self.selected_horizon_label = f"Next 5 Gameweeks (GW{gw}–GW{gw + 4})"
        elif mode == "Free Hit":
            self.horizon_len = 1
            self.selected_horizon_label = f"Next 1 Gameweek (GW{gw}–GW{gw})"
        else:
            self.horizon_len = 5
            self.selected_horizon_label = f"Next 5 Gameweeks (GW{gw}–GW{gw + 4})"
        return TransferAnalyzerState.load_planner_data(True)

    def set_horizon_label(self, label: str):
        self.selected_horizon_label = label
        parts = label.split()
        if len(parts) >= 2:
            try:
                self.horizon_len = int(parts[1])
            except ValueError:
                self.horizon_len = 1
        return TransferAnalyzerState.load_planner_data(True)

    def increment_fts(self):
        if self.ft_count < 5:
            self.ft_count += 1

    def decrement_fts(self):
        if self.ft_count > 1:
            self.ft_count -= 1

    def increment_max_hits(self):
        if self.max_hits < 5:
            self.max_hits += 1

    def decrement_max_hits(self):
        if self.max_hits > 0:
            self.max_hits -= 1

    def set_pitch_view(self, val: bool):
        self.pitch_view = bool(val)

    def set_enable_betting(self, val: bool):
        self.enable_betting = val

    def set_market_weight_drag(self, val: list[float]):
        if val:
            self.market_weight = round(float(val[0]) / 100.0, 2)

    def set_market_weight(self, val: list[float]):
        if val:
            self.market_weight = round(float(val[0]) / 100.0, 2)

    def set_min_mins(self, val: list[float] | list[int]):
        if val:
            self.min_mins = int(val[0])

    def set_pos_search(self, val: str):
        self.pos_search = val

    def set_neg_search(self, val: str):
        self.neg_search = val

    def toggle_positive(self, opt_id: str):
        if opt_id in self.selected_positive:
            self.selected_positive = [x for x in self.selected_positive if x != opt_id]
        else:
            self.selected_positive = self.selected_positive + [opt_id]

    def remove_positive(self, opt_id: str):
        self.selected_positive = [x for x in self.selected_positive if x != opt_id]

    def clear_positive(self):
        self.selected_positive = []

    def toggle_negative(self, opt_id: str):
        if opt_id in self.selected_negative:
            self.selected_negative = [x for x in self.selected_negative if x != opt_id]
        else:
            self.selected_negative = self.selected_negative + [opt_id]

    def remove_negative(self, opt_id: str):
        self.selected_negative = [x for x in self.selected_negative if x != opt_id]

    def clear_negative(self):
        self.selected_negative = []

    # ── Background Data Load & Solve ──────────────────────────────────────────

    @rx.event
    def refresh_planner(self):
        """Explicitly re-fetches planner data bypassing caches."""
        return TransferAnalyzerState.load_planner_data(True)

    @rx.event(background=True)
    async def load_planner_data(self, force_refresh: bool = False):
        async with self:
            if not self.manager_id:
                return
            has_valid_display = (
                self.has_data
                and len(self.base_starters) > 0
                and "Opponent_Display" in self.base_starters[0]
                and "Cost_Display" in self.base_starters[0]
                and "photo_url" in self.base_starters[0]
            )
            if (
                has_valid_display
                and not force_refresh
                and self.manager_id == self.last_loaded_manager_id
                and self.horizon_len == self.last_loaded_horizon
            ):
                return
            self.is_loading = True
            self.status_message = "Loading transfer planner & market options..."
            manager_id = self.manager_id
            current_gw = self.current_gw
            horizon = self.horizon_len
            betting = self.enable_betting
            weight = self.market_weight
            mins = self.min_mins

        if (force_refresh or not has_valid_display) and hasattr(fetch_transfer_planner_data, "clear_cache"):
            fetch_transfer_planner_data.clear_cache()

        result = await asyncio.to_thread(
            fetch_transfer_planner_data,
            manager_id, current_gw, horizon, betting, weight, mins
        )

        async with self:
            if result:
                self.last_loaded_manager_id = manager_id
                self.last_loaded_horizon = horizon
                self.next_gw = result.get("next_gw", self.next_gw)
                self.pos_options = result.get("pos_options", [])
                self.neg_options = result.get("neg_options", [])
                self.bank_balance = result.get("bank_balance", 0.0)
                self.squad_sell = result.get("squad_sell", 100.0)
                self.team_value = result.get("team_val", 100.0)
                self.base_starters = result.get("base_starters", [])
                self.base_bench = result.get("base_bench", [])
                self.base_pitch_html = result.get("base_pitch_html", "")

                gw = self.next_gw
                if self.strategy_mode == "Wildcard":
                    valid_lens = [3, 5, 8]
                elif self.strategy_mode == "Free Hit":
                    valid_lens = [1]
                else:
                    valid_lens = [1, 2, 3, 5]

                if self.horizon_len not in valid_lens:
                    self.horizon_len = 5 if 5 in valid_lens else valid_lens[-1]

                self.selected_horizon_label = (
                    f"Next {self.horizon_len} Gameweek{'s' if self.horizon_len > 1 else ''} (GW{gw}–GW{gw + self.horizon_len - 1})"
                )

                calc_ft = result.get("calc_ft", 1)
                if self.ft_count == 1 and calc_ft > 1:
                    self.ft_count = calc_ft

            self.is_loading = False

    @rx.event(background=True)
    async def solve_transfers(self):
        async with self:
            if not self.manager_id:
                return
            self.is_solving = True
            self.status_message = "Solving optimal transfer path..."

            manager_id = self.manager_id
            current_gw = self.current_gw
            horizon = self.horizon_len
            ft = self.ft_count
            hits = self.max_hits
            betting = self.enable_betting
            weight = self.market_weight
            mins = self.min_mins
            pos_sel = self.selected_positive
            neg_sel = self.selected_negative
            chip_mode = self.strategy_mode

        result = await asyncio.to_thread(
            analyze_transfers,
            manager_id, current_gw, horizon, ft, hits, betting, weight, mins, pos_sel, neg_sel, chip_mode
        )

        async with self:
            if result:
                self.swaps = result.get("swaps", [])
                self.base_starters = result.get("base_starters", self.base_starters)
                self.base_bench = result.get("base_bench", self.base_bench)
                self.trans_starters = result.get("trans_starters", [])
                self.trans_bench = result.get("trans_bench", [])
                self.base_pitch_html = result.get("base_pitch_html", self.base_pitch_html)
                self.comp_pitch_html = result.get("comp_pitch_html", "")
                self.metrics = result.get("metrics", self.metrics)
                self.has_solved = True
                # Populate shared squad so SimulatorState can load Post-Transfer Plan
                # without needing cross-state get_state() in a background task
                self.shared_trans_squad = (
                    [dict(p) for p in self.trans_starters]
                    + [dict(p) for p in self.trans_bench]
                )
            self.is_solving = False

    @rx.event(background=True)
    async def analyze(self):
        """Backward-compatible alias for load_planner_data."""
        yield TransferAnalyzerState.load_planner_data


