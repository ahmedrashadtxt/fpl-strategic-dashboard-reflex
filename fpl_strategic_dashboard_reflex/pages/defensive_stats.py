import asyncio
import reflex as rx
from typing import List, Dict, Any

from fpl_strategic_dashboard_reflex.state import AppState
from backend.data import get_connection
from backend.defensive_logic import run_defensive_analysis

class DefensiveStatsState(AppState):
    is_loading: bool = False
    @rx.var
    def columns(self) -> list[str]:
        return ["Player", "Team", "Pos", "Price", "Avg_Mins_GW", "Total_Points", "Clean_Sheets", "Goals_Conceded", "xGC", "def_xp", "DC_per_90", "Saves"]
    
    search_query: str = ""
    min_avg_mins: int = 0
    position_filter: str = "All"
    sort_by: str = "Projected Defensive xP"
    max_price: float = 9.0
    only_my_squad: bool = False
    show_career_baseline: bool = False
    
    top_cards: List[Dict[str, Any]] = []
    table_data: List[Dict[str, Any]] = []
    
    @rx.var
    def has_data(self) -> bool:
        return len(self.table_data) > 0
        
    def set_search(self, val: str):
        self.search_query = val
        return DefensiveStatsState.load_data
    def set_min_mins(self, val: list[int]):
        self.min_avg_mins = val[0]
        return DefensiveStatsState.load_data
    def set_pos(self, val: str):
        self.position_filter = val
        return DefensiveStatsState.load_data
    def set_sort(self, val: str):
        self.sort_by = val
        return DefensiveStatsState.load_data
    def set_price(self, val: list[int]):
        self.max_price = val[0] / 10.0
        return DefensiveStatsState.load_data
    def set_only_squad(self, val: bool):
        self.only_my_squad = val
        return DefensiveStatsState.load_data
    def set_career(self, val: bool):
        self.show_career_baseline = val
        return DefensiveStatsState.load_data
        
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
            _run_def_backend,
            c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb
        )
        
        async with self:
            if result:
                self.top_cards = result['top_cards']
                self.table_data = result['table']
            self.is_loading = False
            
def _run_def_backend(c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb):
    try:
        conn = get_connection()
        return run_defensive_analysis(conn, c_gw, manager_id, sq, mm, pf, sb, mp, oms, scb)
    except Exception as e:
        print(e)
        return None

def render_top_card(card: Dict[str, Any]):
    return rx.box(
        rx.hstack(
            rx.image(src=card["img_url"], width="40px", height="40px", border_radius="50%"),
            rx.vstack(
                rx.text(card["player"], weight="bold"),
                rx.text(f"{card['team']} - {card['pos']}", size="1", color="gray"),
                spacing="0"
            ),
        ),
        rx.divider(margin_y="2"),
        rx.hstack(
            rx.text("Price: ", size="1", color="gray"), rx.text(f"£{card['price']:.1f}m", size="1"),
            rx.text(" | xGC: ", size="1", color="gray"), rx.text(f"{card['xgc']:.2f}", size="1"),
            rx.text(" | Def xP: ", size="1", color="gray"), rx.text(f"{card['def_xp']:.2f}", weight="bold", color="blue"),
        ),
        padding="4",
        border="1px solid rgba(255,255,255,0.1)",
        border_radius="8px",
        background="rgba(15, 23, 42, 0.6)",
        width="100%"
    )

def defensive_stats_page():
    return rx.box(
        rx.cond(
            DefensiveStatsState.is_loading,
            rx.center(rx.spinner(), padding="8")
        ),
        rx.vstack(
            rx.text("Defensive Resilience & Projected Defensive xP", font_size="2xl", weight="bold"),
            rx.text("Evaluate clean sheet probability, defensive actions, and goalkeeper save points", color="gray"),
            
            rx.grid(
                rx.input(placeholder="Search Player / Club...", value=DefensiveStatsState.search_query, on_change=DefensiveStatsState.set_search),
                rx.select(["All", "DEF", "GKP", "MID"], value=DefensiveStatsState.position_filter, on_change=DefensiveStatsState.set_pos),
                rx.select(["Projected Defensive xP", "DC per 90", "Total DC", "Expected Goals Conceded (Lowest xGC)", "Clean Sheets", "Total Points", "Goalkeeper Saves"], value=DefensiveStatsState.sort_by, on_change=DefensiveStatsState.set_sort),
                columns="3",
                spacing="4",
                width="100%"
            ),
            
            rx.grid(
                rx.box(rx.text("Min Avg Mins/GW"), rx.slider(default_value=[0], min=0, max=90, step=5, on_value_commit=DefensiveStatsState.set_min_mins)),
                rx.box(rx.text("Max Price (£M)"), rx.slider(default_value=[90], min=40, max=90, step=5, on_value_commit=DefensiveStatsState.set_price)),
                rx.checkbox("Only My Squad", checked=DefensiveStatsState.only_my_squad, on_change=DefensiveStatsState.set_only_squad),
                rx.checkbox("Show Career Baselines", checked=DefensiveStatsState.show_career_baseline, on_change=DefensiveStatsState.set_career),
                columns="4",
                spacing="4",
                width="100%"
            ),
            
            rx.divider(),
            
            rx.grid(
                rx.foreach(DefensiveStatsState.top_cards, render_top_card),
                columns="4",
                spacing="4",
                width="100%"
            ),
            
            rx.data_table(
                data=DefensiveStatsState.table_data,
                columns=DefensiveStatsState.columns,
                pagination=True,
                search=True,
                sort=True,
                width="100%"
            ),
            
            spacing="4",
            width="100%"
        ),
        width="100%",
        on_mount=DefensiveStatsState.load_data
    )

