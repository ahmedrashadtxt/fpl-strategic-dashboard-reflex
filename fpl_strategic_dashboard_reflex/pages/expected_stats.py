import asyncio
"""Expected Stats Page - Pure presentation view for xG, xA, and xGI analytics."""

import reflex as rx
from typing import List, Dict, Any
from fpl_strategic_dashboard_reflex.states.expected import ExpectedStatsState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    data_table,
    search_input,
    filter_select,
    filter_bar,
)

from fpl_strategic_dashboard_reflex.state import AppState
from backend.data import get_connection
from backend.expected_logic import run_expected_analysis

class ExpectedStatsState(AppState):
    is_loading: bool = False
    @rx.var
    def columns(self) -> list[str]:
        return ["Player", "Team", "Pos", "Price", "Avg_Mins_GW", "Total_Points", "xG", "xA", "xGI", "gw_xp", "Form", "Att_Ret_Prob", "BPS"]
    
    search_query: str = ""
    min_avg_mins: int = 0
    position_filter: str = "All"
    sort_by: str = "Projected Gameweek xP (Total)"
    max_price: float = 15.0
    only_my_squad: bool = False
    show_career_baseline: bool = False
    
    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []
    
    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0
        
    def set_search(self, val: str):
        self.search_query = val
        return ExpectedStatsState.load_data
    def set_min_mins(self, val: list[int]):
        self.min_avg_mins = val[0]
        return ExpectedStatsState.load_data
    def set_pos(self, val: str):
        self.position_filter = val
        return ExpectedStatsState.load_data
    def set_sort(self, val: str):
        self.sort_by = val
        return ExpectedStatsState.load_data
    def set_price(self, val: list[int]):
        self.max_price = val[0] / 10.0
        return ExpectedStatsState.load_data
    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return ExpectedStatsState.load_data
    def set_career(self, val: bool):
        self.show_career_baseline = val
        return ExpectedStatsState.load_data
        
    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
        
        async with self:
            manager_id = self.manager_id
            c_gw = self.current_gw
            sq = self.search_query
            mm = self.min_avg_mins
            pf = self.position_filter
            sb = self.sort_by
            mp = self.max_price
            oms = self.only_my_squad
            scb = self.show_career_baseline
            
        result = await asyncio.to_thread(
            _run_exp_backend,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb
        )
        
        async with self:
            if result:
                self.top_cards = result['top_cards']
                self.table_data = result['table']
            self.is_loading = False
            
def _run_exp_backend(c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb):
    try:
        conn = get_connection()
        return run_expected_analysis(conn, c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb)
    except Exception as e:
        print(e)
        return None

def render_top_card_exp(card: Dict[str, Any]):
def expected_stats_page() -> rx.Component:
    """Renders the Expected Stats tab view."""
    return rx.box(
        # Page Title & Guide
        rx.hstack(
            rx.image(src=card["img_url"], width="40px", height="40px", border_radius="50%"),
            rx.vstack(
                rx.text(card["player"], weight="bold"),
                rx.text(f"{card['team']} - {card['pos']}", size="1", color="gray"),
                spacing="0"
                rx.text("Expected Attacking Statistics (xG · xA · xGI)", class_name="section-header-title"),
                rx.text("Identify regression and value opportunities by filtering players by underlying expected goals and assists.", class_name="section-header-sub"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            guide_popover(
                title="Expected Stats Guide",
                subtitle="Underlying goal & assist expectations",
                items=[
                    {"badge": "xGI/90", "title": "Expected Goal Involvement", "desc": "Calculates the rate at which players generate quality chances per 90 minutes played."},
                    {"badge": "Regression", "title": "Buy/Sell Signals", "desc": "Players underperforming xG are primed for positive regression (buy targets)."},
                ],
                tip="Filter by minimum 60 minutes per match to exclude substitute cameos.",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),
        rx.divider(margin_y="2"),
        rx.hstack(
            rx.text("Price: ", size="1", color="gray"), rx.text(f"£{card['price']:.1f}m", size="1"),
            rx.text(" | xGI: ", size="1", color="gray"), rx.text(f"{card['xgi']:.2f}", size="1"),
            rx.text(" | Proj xP: ", size="1", color="gray"), rx.text(f"{card['gw_xp']:.2f}", weight="bold", color="green"),
        ),
        padding="4",
        border="1px solid rgba(255,255,255,0.1)",
        border_radius="8px",
        background="rgba(15, 23, 42, 0.6)",
        width="100%"
    )

def expected_stats_page():
    return rx.box(
        # Top Metric Cards
        rx.cond(
            ExpectedStatsState.is_loading,
            rx.center(rx.spinner(), padding="8")
            ExpectedStatsState.has_data,
            rx.hstack(
                rx.foreach(
                    ExpectedStatsState.top_cards,
                    lambda c: metric_card(c["label"], c["value"], c["badge"], c["color"], c["subtext"]),
                ),
                width="100%",
                spacing="3",
                wrap="wrap",
                margin_bottom="1.25rem",
            ),
            rx.box(),
        ),
        rx.vstack(
            rx.text("Expected Attacking Points & Gameweek Projections", font_size="2xl", weight="bold"),
            rx.text("Analyze attacking threat metrics (xG, xA, xGI) and blended gameweek point projections.", color="gray"),
            
            rx.grid(
                rx.input(placeholder="Search Player / Club...", value=ExpectedStatsState.search_query, on_change=ExpectedStatsState.set_search),
                rx.select(["All", "DEF", "GKP", "MID", "FWD"], value=ExpectedStatsState.position_filter, on_change=ExpectedStatsState.set_pos),
                rx.select([

        # Filter Bar
        filter_bar(
            rx.box(
                search_input(
                    value=ExpectedStatsState.search_query,
                    on_change=ExpectedStatsState.set_search,
                    placeholder="Search player or team...",
                ),
                width="240px",
            ),
            filter_select(
                "Position:",
                ["All", "GKP", "DEF", "MID", "FWD"],
                ExpectedStatsState.position_filter,
                ExpectedStatsState.set_pos,
            ),
            filter_select(
                "Sort by:",
                [
                    "Projected Gameweek xP (Total)",
                    "Expected Goal Involvement (xGI)",
                    "xGI per 90 (Rate)",
                    "Expected Goals (xG)",
                    "Expected Assists (xA)",
                    "Total Points",
                    "Form",
                    "Total Points",
                    "Attacking Return Probability (1+ G/A)",
                    "Bonus Points System (BPS)",
                    "Projected Points / 90"
                ], value=ExpectedStatsState.sort_by, on_change=ExpectedStatsState.set_sort),
                columns="3",
                spacing="4",
                width="100%"
                ],
                ExpectedStatsState.sort_by,
                ExpectedStatsState.set_sort,
            ),
            
            rx.grid(
                rx.box(rx.text("Min Avg Mins/GW"), rx.slider(default_value=[0], min=0, max=90, step=5, on_value_commit=ExpectedStatsState.set_min_mins)),
                rx.box(rx.text("Max Price (£M)"), rx.slider(default_value=[150], min=40, max=150, step=5, on_value_commit=ExpectedStatsState.set_price)),
                rx.checkbox("Only My Squad", checked=ExpectedStatsState.only_my_squad, on_change=ExpectedStatsState.set_only_squad),
                rx.checkbox("Show Career Baselines", checked=ExpectedStatsState.show_career_baseline, on_change=ExpectedStatsState.set_career),
                columns="4",
                spacing="4",
                width="100%"
            rx.hstack(
                rx.switch(
                    checked=ExpectedStatsState.only_my_squad,
                    on_change=ExpectedStatsState.set_only_squad,
                    size="1",
                ),
                rx.text("My Squad Only", font_size="0.8rem", color="var(--text-sub)"),
                align="center",
                spacing="2",
            ),
            
            rx.divider(),
            
            rx.grid(
                rx.foreach(ExpectedStatsState.top_cards, render_top_card_exp),
                columns="4",
                spacing="4",
                width="100%"
            rx.hstack(
                rx.switch(
                    checked=ExpectedStatsState.show_career_baseline,
                    on_change=ExpectedStatsState.set_career,
                    size="1",
                ),
                rx.text("Historical Baseline", font_size="0.8rem", color="var(--text-sub)"),
                align="center",
                spacing="2",
            ),
            
            rx.data_table(
                data=ExpectedStatsState.table_data,
                columns=ExpectedStatsState.columns,
                pagination=True,
                search=True,
                sort=True,
                width="100%"
        ),

        # Data Table
        data_table(
            headers=ExpectedStatsState.columns,
            rows=ExpectedStatsState.table_data,
            row_render_func=lambda row: rx.table.row(
                rx.table.cell(rx.text(row["Player"], font_weight="600")),
                rx.table.cell(rx.badge(row["Team"], variant="surface", color_scheme="gray", size="1")),
                rx.table.cell(rx.text(row["Pos"], font_size="0.8rem")),
                rx.table.cell(rx.text(rx.concat("£", row["Price"], "m"))),
                rx.table.cell(rx.text(row["Avg_Mins_GW"])),
                rx.table.cell(rx.text(row["Total_Points"], font_weight="700")),
                rx.table.cell(rx.text(row["xG"], color="#4ade80")),
                rx.table.cell(rx.text(row["xA"], color="#60a5fa")),
                rx.table.cell(rx.text(row["xGI"], font_weight="700", color="#38bdf8")),
                rx.table.cell(rx.text(row["gw_xp"], font_weight="700", color="#a855f7")),
                rx.table.cell(rx.text(row["Form"])),
                rx.table.cell(rx.badge(row["Att_Ret_Prob"], variant="soft", color_scheme="blue", size="1")),
                rx.table.cell(rx.text(row["BPS"])),
            ),
            
            spacing="4",
            width="100%"
            is_loading=ExpectedStatsState.is_loading,
        ),
        width="100%",
        on_mount=ExpectedStatsState.load_data
    )

