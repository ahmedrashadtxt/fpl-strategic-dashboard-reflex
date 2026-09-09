"""Domain State for Transfer Market, Price Predictions, and Target Scout."""

import asyncio
from typing import Any, Dict, List
import pandas as pd
import reflex as rx
from rapidfuzz import fuzz, process

from fpl_strategic_dashboard_reflex.states.base import AppState
from fpl_strategic_dashboard_reflex.services.db import (
    get_connection,
    get_manager_squad_ids,
    calculate_price_change_predictions,
)
from fpl_strategic_dashboard_reflex.services.market import fetch_transfer_targets_base_data


class TransferMarketState(AppState):
    """Sub-state managing transfer targets, nightly price predictions, and ownership momentum."""

    is_loading: bool = False

    search_query: str = ""
    pos_filter: str = "All"
    sort_by: str = "Projected Points (xP)"
    max_price: str = "15.5"
    exclude_my_squad: bool = True
    enable_betting: bool = True

    raw_targets: List[Dict[str, Any]] = []
    filtered_targets: List[Dict[str, Any]] = []
    price_predictions: List[Dict[str, Any]] = []

    @rx.var
    def top_cards(self) -> List[Dict[str, Any]]:
        return self.filtered_targets[:4]

    @rx.var
    def table_data(self) -> List[Dict[str, Any]]:
        return self.filtered_targets

    @rx.var
    def columns(self) -> List[str]:
        return [
            "Player", "Team", "Pos", "Price", "Fixture",
            "FDR", "Proj_xP", "xP_per_Mil", "Form", "Total_Points"
        ]

    def set_search(self, value: str):
        self.search_query = value
        return TransferMarketState.apply_filters

    def set_pos_filter(self, value: str):
        self.pos_filter = value
        return TransferMarketState.apply_filters

    def set_sort_by(self, value: str):
        self.sort_by = value
        return TransferMarketState.apply_filters

    def set_max_price(self, value: list[int]):
        self.max_price = str(value[0])
        return TransferMarketState.apply_filters

    def toggle_exclude(self, value: bool):
        self.exclude_my_squad = value
        return TransferMarketState.apply_filters

    def toggle_betting(self, value: bool):
        self.enable_betting = value
        return TransferMarketState.load_data

    @rx.event(background=True)
    async def load_data(self):
        async with self:
            self.is_loading = True
            c_gw = self.current_gw
            betting = self.enable_betting

        def _fetch():
            conn = get_connection()
            cgw_df = pd.read_sql("SELECT id FROM events WHERE is_current = 1 LIMIT 1", conn)
            current_gw = int(cgw_df.iloc[0]["id"]) if not cgw_df.empty else c_gw
            ngw_df = pd.read_sql("SELECT id FROM events WHERE is_next = 1 LIMIT 1", conn)
            target_gw = int(ngw_df.iloc[0]["id"]) if not ngw_df.empty else current_gw

            raw_df = fetch_transfer_targets_base_data(conn, current_gw, target_gw, betting, "")
            if not raw_df.empty:
                for col in ["Proj_xP", "xP_per_Mil", "Cost", "Price", "Form", "Total_Points", "Season_Points", "FDR"]:
                    if col in raw_df.columns:
                        raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce").fillna(0)

            try:
                price_df = calculate_price_change_predictions(conn)
                price_records = price_df.head(20).to_dict(orient="records") if not price_df.empty else []
            except Exception:
                price_records = []

            return raw_df, current_gw, price_records

        raw_df, current_gw, price_records = await asyncio.to_thread(_fetch)

        async with self:
            self.raw_targets = raw_df.fillna("").to_dict("records")
            self.price_predictions = price_records
            self._apply_filters_internal(raw_df, current_gw)
            self.is_loading = False

    @rx.event(background=True)
    async def apply_filters(self):
        async with self:
            self.is_loading = True
            if not self.raw_targets:
                self.is_loading = False
                return

            c_gw = self.current_gw
            mgr_id = self.manager_id
            pos = self.pos_filter
            search = self.search_query
            sort = self.sort_by
            price_limit = float(self.max_price)
            exclude = self.exclude_my_squad
            targets = list(self.raw_targets)

        def _filter():
            df = pd.DataFrame(targets)
            if df.empty:
                return []
            if pos != "All":
                df = df[df["Pos"] == pos]
            df = df[df["Price"] <= price_limit]

            if exclude and mgr_id:
                conn = get_connection()
                squad_ids = get_manager_squad_ids(mgr_id, c_gw)
                if squad_ids and "element_id" in df.columns:
                    df = df[~df["element_id"].isin(squad_ids)]

            if search and search.strip():
                query = search.strip().lower()
                choices = df["_search_target"].tolist() if "_search_target" in df.columns else df["Player"].tolist()
                matches = process.extract(query, choices, scorer=fuzz.partial_ratio, score_cutoff=60, limit=50)
                if matches:
                    matched_indices = [m[2] for m in matches]
                    df = df.iloc[matched_indices]
                else:
                    return []

            if sort == "Projected Points (xP)":
                df = df.sort_values(by="Proj_xP", ascending=False)
            elif sort == "Value for Money (xP/£m)":
                df = df.sort_values(by="xP_per_Mil", ascending=False)
            elif sort == "Form":
                df = df.sort_values(by="Form", ascending=False)
            elif sort == "Easiest Fixture":
                df = df.sort_values(by="FDR", ascending=True)

            return df.head(100).fillna("").to_dict("records")

        filtered = await asyncio.to_thread(_filter)

        async with self:
            self.filtered_targets = filtered
            self.is_loading = False

    def _apply_filters_internal(self, raw_df: pd.DataFrame, current_gw: int):
        if raw_df.empty:
            self.filtered_targets = []
            return
        df = raw_df.copy()
        if self.pos_filter != "All":
            df = df[df["Pos"] == self.pos_filter]
        df = df[df["Price"] <= float(self.max_price)]
        if self.exclude_my_squad and self.manager_id:
            conn = get_connection()
            squad_ids = get_manager_squad_ids(self.manager_id, current_gw)
            if squad_ids and "element_id" in df.columns:
                df = df[~df["element_id"].isin(squad_ids)]
        self.filtered_targets = df.sort_values(by="Proj_xP", ascending=False).head(100).fillna("").to_dict("records")

