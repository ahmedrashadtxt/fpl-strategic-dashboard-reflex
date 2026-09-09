import asyncio
"""Rolling Form Page - Pure presentation view for multi-gameweek form analytics."""

import reflex as rx
from typing import List, Dict, Any
from fpl_strategic_dashboard_reflex.states.rolling import RollingFormState
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
from backend.rolling_logic import run_rolling_analysis
import plotly.graph_objects as go

class RollingFormState(AppState):
    is_loading: bool = False
    @rx.var
    def columns(self) -> list[str]:
        return ["Player", "Team", "Pos", "Price", "Avg_Mins_GW", "Total_Points", "Form", "Upcoming_FDR", "form_xp", "xGI"]
    
    search_query: str = ""
    min_avg_mins: int = 0
    position_filter: str = "All"
    sort_by: str = "Blended Form xP"
    max_price: float = 15.0
    only_my_squad: bool = False
    lookback_window: str = "4"
    
    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []
    fig: go.Figure = go.Figure()
    
    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0
        
    def set_search(self, val: str):
        self.search_query = val
        return RollingFormState.load_data
    def set_min_mins(self, val: list[int]):
        self.min_avg_mins = val[0]
        return RollingFormState.load_data
    def set_pos(self, val: str):
        self.position_filter = val
        return RollingFormState.load_data
    def set_sort(self, val: str):
        self.sort_by = val
        return RollingFormState.load_data
    def set_price(self, val: list[int]):
        self.max_price = val[0] / 10.0
        return RollingFormState.load_data
    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return RollingFormState.load_data
    def set_lookback(self, val: str):
        self.lookback_window = str(val)
        return RollingFormState.load_data
        
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
            lw = int(self.lookback_window)
            
        result = await asyncio.to_thread(
            _run_roll_backend,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, lw
        )
        
        async with self:
            if result:
                self.top_cards = result['top_cards']
                self.table_data = result['table']
                self.fig = result['fig']
            self.is_loading = False
            
def _run_roll_backend(c_gw, manager_id, sq, mm, pf, sb, mp, oms, lw):
    try:
        conn = get_connection()
        return run_rolling_analysis(conn, c_gw, manager_id, sq, mm, pf, sb, mp, oms, lw)
    except Exception as e:
        print(e)
        return None

def render_top_card_roll(card: Dict[str, Any]):
def rolling_form_page() -> rx.Component:
    """Renders the Rolling Form tab view."""
    return rx.box(
        # Page Title & Guide
        rx.hstack(
            rx.image(src=card["img_url"], width="40px", height="40px", border_radius="50%"),
            rx.vstack(
                rx.text(card["player"], weight="bold"),
                rx.text(f"{card['team']} - {card['pos']}", size="1", color="gray"),
                spacing="0"
                rx.text("Rolling Form & Value Dynamics", class_name="section-header-title"),
                rx.text("Analyze moving window averages (3, 5, or 8 GWs) to separate genuine hot streaks from single-game anomalies.", class_name="section-header-sub"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            guide_popover(
                title="Rolling Form Guide",
                subtitle="Smooth statistical volatility over customizable windows",
                items=[
                    {"badge": "Window", "title": "Rolling Windows", "desc": "Evaluate 3, 5, or 8 gameweeks to capture short-term form and long-term trends."},
                    {"badge": "Value Ratio", "title": "Points per Million", "desc": "Calculates form points divided by player cost to identify budget enablers."},
                ],
                tip="Players with rising form and low upcoming FDR (green) offer the highest immediate transfer upside.",
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
            rx.text(" | FDR: ", size="1", color="gray"), rx.text(f"{card['fdr']:.2f}", size="1"),
            rx.text(" | Form xP: ", size="1", color="gray"), rx.text(f"{card['form_xp']:.2f}", weight="bold", color="green"),
        ),
        padding="4",
        border="1px solid rgba(255,255,255,0.1)",
        border_radius="8px",
        background="rgba(15, 23, 42, 0.6)",
        width="100%"
    )

def rolling_form_page():
    return rx.box(
        # Top Metric Cards
        rx.cond(
            RollingFormState.is_loading,
            rx.center(rx.spinner(), padding="8")
            RollingFormState.has_data,
            rx.hstack(
                rx.foreach(
                    RollingFormState.top_cards,
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
            rx.text("Rolling Form & Fixture Matrix", font_size="2xl", weight="bold"),
            rx.text("Compare recent performance trends against upcoming fixture difficulty.", color="gray"),
            
            rx.grid(
                rx.input(placeholder="Search Player / Club...", value=RollingFormState.search_query, on_change=RollingFormState.set_search),
                rx.select(["All", "DEF", "GKP", "MID", "FWD"], value=RollingFormState.position_filter, on_change=RollingFormState.set_pos),
                rx.select([
                    "Blended Form xP",
                    "Expected Goal Involvement (xGI)",
                    "Base FPL Form",
                    "Upcoming Fixture Difficulty (Lowest FDR)",
                    "Recent Points (Total)"
                ], value=RollingFormState.sort_by, on_change=RollingFormState.set_sort),
                rx.select(["2", "3", "4", "5", "6"], value=RollingFormState.lookback_window, on_change=RollingFormState.set_lookback),
                columns="4",
                spacing="4",
                width="100%"

        # Filter Bar
        filter_bar(
            rx.box(
                search_input(
                    value=RollingFormState.search_query,
                    on_change=RollingFormState.set_search,
                    placeholder="Search player or club...",
                ),
                width="240px",
            ),
            
            rx.grid(
                rx.box(rx.text("Min Avg Mins/GW"), rx.slider(default_value=[0], min=0, max=90, step=5, on_value_commit=RollingFormState.set_min_mins)),
                rx.box(rx.text("Max Price (£M)"), rx.slider(default_value=[150], min=40, max=150, step=5, on_value_commit=RollingFormState.set_price)),
                rx.checkbox("Only My Squad", checked=RollingFormState.only_my_squad, on_change=RollingFormState.set_only_squad),
                columns="3",
                spacing="4",
                width="100%"
            filter_select(
                "Window Size:",
                ["3", "5", "8"],
                RollingFormState.window_size.to_string(),
                RollingFormState.set_window,
            ),
            
            rx.cond(
                RollingFormState.has_data,
                rx.plotly(data=RollingFormState.fig, layout={"height": "500px", "width": "100%"}),
            filter_select(
                "Position:",
                ["All", "GKP", "DEF", "MID", "FWD"],
                RollingFormState.position_filter,
                RollingFormState.set_pos,
            ),
            
            rx.divider(),
            
            rx.grid(
                rx.foreach(RollingFormState.top_cards, render_top_card_roll),
                columns="4",
                spacing="4",
                width="100%"
            filter_select(
                "Sort by:",
                [
                    "Form vs Price Ratio",
                    "Rolling Points / GW",
                    "Rolling Minutes / GW",
                    "Rolling xGI / 90",
                    "Total Points",
                ],
                RollingFormState.sort_by,
                RollingFormState.set_sort,
            ),
            
            rx.data_table(
                data=RollingFormState.table_data,
                columns=RollingFormState.columns,
                pagination=True,
                search=True,
                sort=True,
                width="100%"
            rx.hstack(
                rx.switch(
                    checked=RollingFormState.only_my_squad,
                    on_change=RollingFormState.set_only_squad,
                    size="1",
                ),
                rx.text("My Squad Only", font_size="0.8rem", color="var(--text-sub)"),
                align="center",
                spacing="2",
            ),
            
            spacing="4",
            width="100%"
        ),

        # Data Table
        data_table(
            headers=RollingFormState.columns,
            rows=RollingFormState.table_data,
            row_render_func=lambda row: rx.table.row(
                rx.table.cell(rx.text(row["Player"], font_weight="600")),
                rx.table.cell(rx.badge(row["Team"], variant="surface", color_scheme="gray", size="1")),
                rx.table.cell(rx.text(row["Pos"], font_size="0.8rem")),
                rx.table.cell(rx.text(rx.concat("£", row["Price"], "m"))),
                rx.table.cell(rx.text(row["Roll_Mins_GW"])),
                rx.table.cell(rx.text(row["Roll_Points_GW"], font_weight="700", color="#4ade80")),
                rx.table.cell(rx.badge(row["Form_Price_Ratio"], variant="soft", color_scheme="purple", size="1")),
                rx.table.cell(rx.text(row["Roll_xGI_90"], color="#60a5fa")),
                rx.table.cell(rx.text(row["Roll_ICT_GW"])),
                rx.table.cell(rx.text(row["FDR_Next_5"])),
                rx.table.cell(
                    rx.cond(
                        row["FDR_Difficulty"] == "Easy Run",
                        rx.badge(row["FDR_Difficulty"], variant="soft", color_scheme="green", size="1"),
                        rx.cond(
                            row["FDR_Difficulty"] == "Tough Run",
                            rx.badge(row["FDR_Difficulty"], variant="soft", color_scheme="red", size="1"),
                            rx.badge(row["FDR_Difficulty"], variant="surface", color_scheme="gray", size="1"),
                        ),
                    )
                ),
                rx.table.cell(rx.text(row["BPS"])),
            ),
            is_loading=RollingFormState.is_loading,
        ),
        width="100%",
        on_mount=RollingFormState.load_data
    )

