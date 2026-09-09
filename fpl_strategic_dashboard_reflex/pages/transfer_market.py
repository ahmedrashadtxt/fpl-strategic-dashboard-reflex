"""Transfer Market Page - Pure presentation view for price changes and scout targets."""

import reflex as rx
import pandas as pd
from typing import List, Dict, Any
from fpl_strategic_dashboard_reflex.state import AppState
import asyncio
from rapidfuzz import fuzz, process
from fpl_strategic_dashboard_reflex.states.market import TransferMarketState
from fpl_strategic_dashboard_reflex.components import (
    guide_popover,
    metric_card,
    data_table,
    search_input,
    filter_select,
    filter_bar,
)

from backend.data import get_connection, get_manager_squad_ids
from backend.market_logic import fetch_transfer_targets_base_data

class TransferMarketState(AppState):
    is_loading: bool = False
    
    # Filters
    search_query: str = ""
    pos_filter: str = "All"
    sort_by: str = "Projected Points (xP)"
    max_price: str = "15.5"
    exclude_my_squad: bool = True
    enable_betting: bool = True
    
    raw_targets: List[Dict[str, Any]] = []
    filtered_targets: List[Dict[str, Any]] = []
    
    @rx.var
    def top_cards(self) -> List[Dict[str, Any]]:
        return self.filtered_targets[:4]
        
    @rx.var
    def table_data(self) -> List[Dict[str, Any]]:
        return self.filtered_targets
        
    @rx.var
    def columns(self) -> List[str]:
        return ["Player", "Team", "Pos", "Price", "Fixture", "FDR", "Proj_xP", "xP_per_Mil", "Form", "Total_Points"]

    def set_search(self, value: str):
        self.search_query = value
        
    def set_pos_filter(self, value: str):
        self.pos_filter = value
        
    def set_sort_by(self, value: str):
        self.sort_by = value
        
    def set_max_price(self, value: list[int]):
        self.max_price = str(value[0])
        
    def toggle_exclude(self, value: bool):
        self.exclude_my_squad = value
        
    def toggle_betting(self, value: bool):
        self.enable_betting = value

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            if not self.manager_id:
                return
            self.is_loading = True
            
        def _fetch():
            conn = get_connection()
            # Find current gw
            cgw_df = pd.read_sql("SELECT id FROM events WHERE is_current = 1 LIMIT 1", conn)
            current_gw = int(cgw_df.iloc[0]["id"]) if not cgw_df.empty else 1
            
            ngw_df = pd.read_sql("SELECT id FROM events WHERE is_next = 1 LIMIT 1", conn)
            target_gw = int(ngw_df.iloc[0]["id"]) if not ngw_df.empty else current_gw
            
            raw_df = fetch_transfer_targets_base_data(conn, current_gw, target_gw, self.enable_betting, "")
            
            # fillna
            if not raw_df.empty:
                for col in ["Proj_xP", "xP_per_Mil", "Cost", "Price", "Form", "Total_Points", "Season_Points", "FDR"]:
                    if col in raw_df.columns:
                        raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce").fillna(0)
                        
            return raw_df, current_gw
            
        raw_df, current_gw = await asyncio.to_thread(_fetch)
        
        async with self:
            self.raw_targets = raw_df.fillna("").to_dict("records")
            self._apply_filters_internal(raw_df, current_gw)
            self.is_loading = False
            
    @rx.event(background=True)
    async def apply_filters(self):
        async with self:
            self.is_loading = True
        
        def _filter():
            if not self.raw_targets:
                return []
            
            df = pd.DataFrame(self.raw_targets)
            if self.pos_filter != "All":
                df = df[df["Pos"] == self.pos_filter]
                
            df = df[df["Cost"] <= float(self.max_price)]
            
            if self.exclude_my_squad and self.manager_id:
                squad_ids = get_manager_squad_ids(self.manager_id, 1) # Note: we just need some squad_ids. 1 is placeholder.
                df = df[~df["id"].isin(squad_ids)]
                
            has_search = bool(self.search_query and self.search_query.strip())
            
            if has_search and not df.empty:
                q = self.search_query.strip()
                search_targets = df["_search_target"].to_dict()
                matches = process.extract(
                    query=q,
                    choices=search_targets,
                    scorer=fuzz.WRatio,
                    score_cutoff=60,
                    limit=40,
                )
                if matches:
                    matched_indices = [m[2] for m in matches]
                    df = df.loc[matched_indices]
                else:
                    df = df.iloc[0:0]
            elif not df.empty:
                sort_options = {
                    "Projected Points (xP)": ("Proj_xP", False),
                    "Value Efficiency (xP / £M)": ("xP_per_Mil", False),
                    "Current Form": ("Form", False),
                    "Total Season Points": ("Total_Points", False),
                    "Price (Low to High)": ("Cost", True),
                }
                sort_col, sort_asc = sort_options.get(self.sort_by, ("Proj_xP", False))
                df = df.sort_values(by=sort_col, ascending=sort_asc)
                
            return df.fillna("").to_dict("records")
            
        res = await asyncio.to_thread(_filter)
        
        async with self:
            self.filtered_targets = res
            self.is_loading = False
            
    def _apply_filters_internal(self, df, current_gw):
        if df.empty:
            self.filtered_targets = []
            return
            
        if self.pos_filter != "All":
            df = df[df["Pos"] == self.pos_filter]
            
        df = df[df["Cost"] <= float(self.max_price)]
        
        if self.exclude_my_squad and self.manager_id:
            squad_ids = get_manager_squad_ids(self.manager_id, current_gw)
            df = df[~df["id"].isin(squad_ids)]
            
        has_search = bool(self.search_query and self.search_query.strip())
        
        if has_search and not df.empty:
            q = self.search_query.strip()
            search_targets = df["_search_target"].to_dict()
            matches = process.extract(
                query=q,
                choices=search_targets,
                scorer=fuzz.WRatio,
                score_cutoff=60,
                limit=40,
            )
            if matches:
                matched_indices = [m[2] for m in matches]
                df = df.loc[matched_indices]
            else:
                df = df.iloc[0:0]
        elif not df.empty:
            sort_options = {
                "Projected Points (xP)": ("Proj_xP", False),
                "Value Efficiency (xP / £M)": ("xP_per_Mil", False),
                "Current Form": ("Form", False),
                "Total Season Points": ("Total_Points", False),
                "Price (Low to High)": ("Cost", True),
            }
            sort_col, sort_asc = sort_options.get(self.sort_by, ("Proj_xP", False))
            df = df.sort_values(by=sort_col, ascending=sort_asc)
            
        self.filtered_targets = df.fillna("").to_dict("records")

def render_target_card(row: Dict[str, Any]) -> rx.Component:
def transfer_market_page() -> rx.Component:
    """Renders the Transfer Market tab view."""
    return rx.box(
        rx.vstack(
            rx.text(row["Player"], weight="bold"),
            rx.text(f"{row['Team']} - {row['Pos']}", color="gray", size="2"),
            rx.text(f"Price: £{row['Price']}", size="2"),
            rx.text(f"xP: {row['Proj_xP']}", color="green", weight="bold"),
        # Page Title & Guide
        rx.hstack(
            rx.vstack(
                rx.text("Transfer Market & Price Rise Predictor", class_name="section-header-title"),
                rx.text("Monitor nightly price rise/fall thresholds, transfer volume momentum, and scout top targets.", class_name="section-header-sub"),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            guide_popover(
                title="Transfer Market Guide",
                subtitle="Price changes and transfer trends",
                items=[
                    {"badge": "Thresholds", "title": "Nightly Price Changes", "desc": "Players reaching ~100% net transfer threshold are predicted to change price at 01:30 UK time."},
                    {"badge": "Value Scout", "title": "Scout Targets", "desc": "Sort by points per million to identify budget enablers before price rises."},
                ],
                tip="Make planned transfers before price deadline to capture team value gains.",
            ),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
            wrap="wrap",
            gap="1rem",
        ),
        padding="4",
        border="1px solid #e2e8f0",
        border_radius="md",
        background_color="white",
        box_shadow="sm"
    )

def transfer_market_page() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.heading("Transfer Target Finder", size="6"),
            rx.text("Identify high-EV incoming transfer targets ranked by projected points and value efficiency", color="gray", margin_bottom="4"),
            
        # Top Targets Cards
        rx.cond(
            TransferMarketState.top_cards.length() > 0,
            rx.hstack(
                rx.input(placeholder="Search Player / Club...", on_change=TransferMarketState.set_search, width="300px"),
                rx.select(["All", "GKP", "DEF", "MID", "FWD"], value=TransferMarketState.pos_filter, on_change=TransferMarketState.set_pos_filter),
                rx.select(["Projected Points (xP)", "Value Efficiency (xP / £M)", "Current Form", "Total Season Points", "Price (Low to High)"], value=TransferMarketState.sort_by, on_change=TransferMarketState.set_sort_by),
                spacing="4"
                rx.foreach(
                    TransferMarketState.top_cards,
                    lambda c: metric_card(c["Player"], rx.concat("£", c["Price"], "m"), c["Team"], "blue", rx.concat(c["Proj_xP"], " xP · ", c["Fixture"])),
                ),
                width="100%",
                spacing="3",
                wrap="wrap",
                margin_bottom="1.25rem",
            ),
            
            rx.box(),
        ),

        # Filter Bar
        filter_bar(
            rx.box(
                search_input(
                    value=TransferMarketState.search_query,
                    on_change=TransferMarketState.set_search,
                    placeholder="Search market target...",
                ),
                width="240px",
            ),
            filter_select(
                "Position:",
                ["All", "GKP", "DEF", "MID", "FWD"],
                TransferMarketState.pos_filter,
                TransferMarketState.set_pos_filter,
            ),
            filter_select(
                "Sort by:",
                [
                    "Projected Points (xP)",
                    "Value for Money (xP/£m)",
                    "Form",
                    "Easiest Fixture",
                ],
                TransferMarketState.sort_by,
                TransferMarketState.set_sort_by,
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Target Max Price (£M)", size="2"),
                    rx.slider(default_value=[15], min=4, max=15, on_value_commit=TransferMarketState.set_max_price, width="200px"),
                rx.switch(
                    checked=TransferMarketState.exclude_my_squad,
                    on_change=TransferMarketState.toggle_exclude,
                    size="1",
                ),
                rx.checkbox("Exclude My Squad", checked=TransferMarketState.exclude_my_squad, on_change=TransferMarketState.toggle_exclude),
                rx.checkbox("Apply Betting Odds", checked=TransferMarketState.enable_betting, on_change=TransferMarketState.toggle_betting),
                rx.button("Apply Filters", on_click=TransferMarketState.apply_filters),
                spacing="4",
                align_items="center"
                rx.text("Exclude My Squad", font_size="0.8rem", color="var(--text-sub)"),
                align="center",
                spacing="2",
            ),
            
            rx.cond(
                TransferMarketState.is_loading,
                rx.spinner(),
                rx.vstack(
                    rx.grid(
                        rx.foreach(TransferMarketState.top_cards, render_target_card),
                        columns="4",
                        spacing="4",
                        width="100%",
                        margin_top="4"
                    ),
                    rx.box(
                        rx.data_table(
                            data=TransferMarketState.table_data,
                            columns=TransferMarketState.columns,
                            pagination=True,
                            search=True,
                            sort=True,
            rx.hstack(
                rx.switch(
                    checked=TransferMarketState.enable_betting,
                    on_change=TransferMarketState.toggle_betting,
                    size="1",
                ),
                rx.text("Betting Odds Blending", font_size="0.8rem", color="var(--text-sub)"),
                align="center",
                spacing="2",
            ),
        ),

        # Data Table
        data_table(
            headers=TransferMarketState.columns,
            rows=TransferMarketState.table_data,
            row_render_func=lambda row: rx.table.row(
                rx.table.cell(rx.text(row["Player"], font_weight="600")),
                rx.table.cell(rx.badge(row["Team"], variant="surface", color_scheme="gray", size="1")),
                rx.table.cell(rx.text(row["Pos"], font_size="0.8rem")),
                rx.table.cell(rx.text(rx.concat("£", row["Price"], "m"))),
                rx.table.cell(rx.text(row["Fixture"])),
                rx.table.cell(
                    rx.cond(
                        row["FDR"].to(int) <= 2,
                        rx.badge(row["FDR"].to_string(), variant="soft", color_scheme="green", size="1"),
                        rx.cond(
                            row["FDR"].to(int) == 3,
                            rx.badge(row["FDR"].to_string(), variant="surface", color_scheme="gray", size="1"),
                            rx.badge(row["FDR"].to_string(), variant="soft", color_scheme="red", size="1"),
                        ),
                        margin_top="6",
                        width="100%"
                    ),
                    width="100%"
                )
            )
                    )
                ),
                rx.table.cell(rx.text(row["Proj_xP"], font_weight="700", color="#60a5fa")),
                rx.table.cell(rx.badge(row["xP_per_Mil"], variant="soft", color_scheme="purple", size="1")),
                rx.table.cell(rx.text(row["Form"])),
                rx.table.cell(rx.text(row["Total_Points"], font_weight="600")),
            ),
            is_loading=TransferMarketState.is_loading,
        ),
        padding="6",
        on_mount=TransferMarketState.load_data
        width="100%",
    )

