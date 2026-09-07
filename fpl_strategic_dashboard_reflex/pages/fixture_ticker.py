"""
Fixture Ticker page — Reflex migration of tabs/fixture_ticker.py.

Data flow:
  - On load / when filters change, FixtureTickerState fetches:
      1. fixtures table: event, Home_Team, Away_Team, Home_Diff, Away_Diff
      2. teams table: id, code, short_name, name
      3. player-team lookup (for fuzzy search & squad-only filter)
      4. (optional) manager squad IDs via FPL API
  - RapidFuzz powers the player/club search entirely on the Python side.
  - The processed list[dict] is stored in State and rendered
    via rx.foreach over a styled rx.table.
"""

import reflex as rx

from backend.fixture_logic import _build_ticker_rows
from fpl_strategic_dashboard_reflex.state import AppState


# ── Data helpers ─────────────────────────────────────────────────────────────

def _fdr_badge_style(diff: int, is_blank: bool) -> dict:
    """Returns an inline-style dict for the FDR badge based on difficulty."""
    base = {
        "display": "block",
        "text_align": "center",
        "padding": "0.3rem 0.5rem",
        "border_radius": "6px",
        "font_size": "0.78rem",
        "font_weight": "600",
        "white_space": "nowrap",
        "min_width": "80px",
    }
    if is_blank:
        return {**base, "background": "rgba(15,23,42,0.5)", "color": "#64748b", "font_style": "italic"}
    palette = {
        2: {"background": "rgba(34,197,94,0.22)", "color": "#4ade80"},
        3: {"background": "rgba(100,116,139,0.16)", "color": "#cbd5e1"},
        4: {"background": "rgba(249,115,22,0.24)", "color": "#fb923c", "font_weight": "700"},
        5: {"background": "rgba(239,68,68,0.28)", "color": "#f87171", "font_weight": "800"},
    }
    return {**base, **palette.get(diff, palette[5])}


def _total_color(total: int) -> str:
    if total <= 11:
        return "#22c55e"
    if total <= 14:
        return "#eab308"
    return "#ef4444"



class FixtureTickerState(AppState):
    """State for the Fixture Ticker tab."""

    # Filter controls
    search_query: str = ""
    only_my_squad: bool = False

    # Processed data — flat list[dict] (no nested lists)
    ticker_rows: list[dict] = []
    is_loading: bool = False

    @rx.var
    def gw_columns(self) -> list[int]:
        return list(range(self.current_gw, self.current_gw + 5))

    @rx.var
    def gw_column_labels(self) -> list[str]:
        return [f"GW {gw}" for gw in range(self.current_gw, self.current_gw + 5)]

    @rx.var
    def section_title(self) -> str:
        end = self.current_gw + 4
        return f"Fixture Difficulty · GW{self.current_gw}–{end}"

    @rx.var
    def has_rows(self) -> bool:
        return len(self.ticker_rows) > 0

    @rx.var
    def show_no_id_warning(self) -> bool:
        return self.only_my_squad and not self.manager_id

    # ── Event handlers ──────────────────────────────────────────────────

    def load_ticker(self):
        """Re-compute ticker rows from the DB with current filters."""
        self.is_loading = True
        yield
        try:
            rows = _build_ticker_rows(
                current_gw=self.current_gw,
                search_query=self.search_query,
                only_my_squad=self.only_my_squad,
                manager_id=self.manager_id,
            )
            self.ticker_rows = rows
        except Exception as ex:
            print(f"FixtureTickerState.load_ticker error: {ex}")
            self.ticker_rows = []
        finally:
            self.is_loading = False

    def set_search(self, value: str):
        self.search_query = value
        return FixtureTickerState.load_ticker

    def toggle_only_my_squad(self, value: bool):
        self.only_my_squad = value
        return FixtureTickerState.load_ticker

    def on_tab_visible(self):
        """Called when user navigates to this tab — ensures data is loaded."""
        if not self.ticker_rows and not self.is_loading:
            return FixtureTickerState.load_ticker


# ── Helper UI components ──────────────────────────────────────────────────────

def _fdr_badge(diff: int | rx.Var, label: str | rx.Var, is_blank: bool | rx.Var) -> rx.Component:
    """Renders a single FDR colour-coded badge using rx.cond for runtime styling."""
    bg_color = rx.cond(
        is_blank, "rgba(15,23,42,0.5)",
        rx.cond(diff == 2, "rgba(34,197,94,0.22)",
            rx.cond(diff == 3, "rgba(100,116,139,0.16)",
                rx.cond(diff == 4, "rgba(249,115,22,0.24)", "rgba(239,68,68,0.28)"))),
    )
    txt_color = rx.cond(
        is_blank, "#64748b",
        rx.cond(diff == 2, "#4ade80",
            rx.cond(diff == 3, "#cbd5e1",
                rx.cond(diff == 4, "#fb923c", "#f87171"))),
    )
    fw = rx.cond(is_blank, "500", rx.cond((diff == 4) | (diff == 5), "700", "600"))
    return rx.table.cell(
        rx.box(
            rx.text(label, font_size="0.78rem", font_weight=fw),
            background=bg_color,
            color=txt_color,
            border_radius="6px",
            padding="0.3rem 0.5rem",
            text_align="center",
            white_space="nowrap",
            min_width="80px",
            font_style=rx.cond(is_blank, "italic", "normal"),
        ),
        padding="0.4rem 0.5rem",
        text_align="center",
    )


def _total_cell(row: dict) -> rx.Component:
    total = row["difficulty_rating"]
    # Use explicit equality chains — ObjectItemOperation doesn't support <= with int literals
    color = rx.cond(
        (total == 10) | (total == 11) | (total == 9) | (total == 8) | (total == 7) | (total == 6) | (total == 5),
        "#22c55e",
        rx.cond(
            (total == 12) | (total == 13) | (total == 14),
            "#eab308",
            "#ef4444",
        ),
    )
    return rx.table.cell(
        rx.text(total.to_string(), font_weight="800", font_size="0.92rem", color=color),
        text_align="center",
        padding="0.4rem 0.6rem",
    )


def _club_cell(row: dict) -> rx.Component:
    return rx.table.row_header_cell(
        rx.hstack(
            rx.box(
                rx.el.img(
                    src="https://resources.premierleague.com/premierleague/badges/50/t"
                        + row["code"].to_string() + ".png",
                    style={"width": "22px", "height": "22px", "objectFit": "contain", "flexShrink": "0"},
                ),
                width="22px",
                height="22px",
                flex_shrink="0",
            ),
            rx.text(
                row["full_name"], " (", row["short_name"], ")",
                font_weight="600",
                font_size="0.85rem",
                white_space="nowrap",
                color="var(--text-main)",
            ),
            align="center",
            spacing="2",
        ),
        padding="0.5rem 0.75rem",
        min_width="200px",
    )


def _ticker_table_row(row: dict) -> rx.Component:
    return rx.table.row(
        _club_cell(row),
        rx.cond(
            FixtureTickerState.only_my_squad,
            rx.table.cell(
                rx.text(
                    row["my_players"],
                    font_size="0.82rem",
                    font_weight="600",
                    color="#9BBEED",
                    white_space="nowrap",
                ),
                padding="0.5rem 0.6rem",
            ),
            rx.fragment(),
        ),
        # Directly render 5 GW slots from flat fields (avoids nested foreach type error)
        _fdr_badge(row["gw0_diff"], row["gw0_label"], row["gw0_blank"]),
        _fdr_badge(row["gw1_diff"], row["gw1_label"], row["gw1_blank"]),
        _fdr_badge(row["gw2_diff"], row["gw2_label"], row["gw2_blank"]),
        _fdr_badge(row["gw3_diff"], row["gw3_label"], row["gw3_blank"]),
        _fdr_badge(row["gw4_diff"], row["gw4_label"], row["gw4_blank"]),
        _total_cell(row),
        _hover_style={"background": "rgba(255,255,255,0.02)"},
    )


def _guide_popover() -> rx.Component:
    return rx.popover.root(
        rx.popover.trigger(
            rx.button(
                "📖 Guide",
                variant="surface",
                color_scheme="gray",
                size="2",
                cursor="pointer",
            )
        ),
        rx.popover.content(
            rx.vstack(
                rx.text("Fixture Ticker Guide", font_weight="700", font_size="1rem", font_family="'Outfit', sans-serif"),
                rx.separator(width="100%"),
                rx.text("Difficulty Rating: Sum of official FDR scores across the next 5 gameweeks.", font_size="0.85rem"),
                rx.text("(H) vs. (A): Designates Home or Away fixtures.", font_size="0.85rem"),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="rgba(34,197,94,0.22)", border_radius="3px", flex_shrink="0"),
                    rx.text("FDR 2 — Easy (prime targets)", font_size="0.82rem", color="#4ade80"),
                    align="center", spacing="2",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="rgba(100,116,139,0.16)", border_radius="3px", flex_shrink="0"),
                    rx.text("FDR 3 — Neutral", font_size="0.82rem", color="#94a3b8"),
                    align="center", spacing="2",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="rgba(249,115,22,0.24)", border_radius="3px", flex_shrink="0"),
                    rx.text("FDR 4 — Tough", font_size="0.82rem", color="#fb923c"),
                    align="center", spacing="2",
                ),
                rx.hstack(
                    rx.box(width="12px", height="12px", background="rgba(239,68,68,0.28)", border_radius="3px", flex_shrink="0"),
                    rx.text("FDR 5 — Very Tough (avoid buying)", font_size="0.82rem", color="#f87171"),
                    align="center", spacing="2",
                ),
                rx.separator(width="100%"),
                rx.text("🟢 Green Run (≤10 pts): Prime fixture swings.", font_size="0.82rem"),
                rx.text("🔴 Tough Run (≥15 pts): Hold off buying assets.", font_size="0.82rem"),
                spacing="3",
                width="300px",
            ),
            background="var(--card-bg)",
            border="1px solid var(--border-color)",
        ),
    )


def fixture_ticker_page() -> rx.Component:
    """Main Fixture Ticker tab component."""
    return rx.vstack(
        # ── Header row ────────────────────────────────────────────────────
        rx.hstack(
            rx.vstack(
                rx.hstack(
                    rx.box(
                        width="3px",
                        height="100%",
                        background="#2563eb",
                        border_radius="2px",
                        align_self="stretch",
                    ),
                    rx.vstack(
                        rx.text(
                            FixtureTickerState.section_title,
                            font_family="'Outfit', sans-serif",
                            font_weight="700",
                            font_size="1.2rem",
                            color="var(--text-main)",
                        ),
                        rx.text(
                            "Upcoming schedule ranked by difficulty",
                            font_size="0.8rem",
                            color="var(--text-sub)",
                            font_weight="500",
                        ),
                        spacing="1",
                        align="start",
                    ),
                    align="center",
                    spacing="3",
                ),
                align="start",
            ),
            rx.spacer(),
            _guide_popover(),
            width="100%",
            align="center",
            margin_bottom="1.25rem",
        ),

        # ── Filter controls ───────────────────────────────────────────────
        rx.hstack(
            rx.box(
                rx.input(
                    placeholder="🔍  Search player or club… e.g. Saka, Arsenal, MCI",
                    value=FixtureTickerState.search_query,
                    on_change=FixtureTickerState.set_search,
                    size="3",
                    variant="surface",
                    width="100%",
                ),
                flex="2",
            ),
            rx.hstack(
                rx.switch(
                    checked=FixtureTickerState.only_my_squad,
                    on_change=FixtureTickerState.toggle_only_my_squad,
                    color_scheme="blue",
                ),
                rx.text(
                    "🎯 My Squad Clubs Only",
                    font_size="0.85rem",
                    font_weight="600",
                    color="var(--text-main)",
                    cursor="pointer",
                    on_click=FixtureTickerState.toggle_only_my_squad(
                        ~FixtureTickerState.only_my_squad
                    ),
                ),
                align="center",
                spacing="2",
            ),
            width="100%",
            align="center",
            spacing="4",
            margin_bottom="1rem",
        ),

        # ── No-ID warning banner ─────────────────────────────────────────
        rx.cond(
            FixtureTickerState.show_no_id_warning,
            rx.callout.root(
                rx.callout.icon(rx.icon("info", size=16)),
                rx.callout.text(
                    "Enter your FPL Team ID using the ",
                    rx.text.strong("➕ Enter FPL ID"),
                    " button in the top bar to filter by your squad.",
                    font_size="0.85rem",
                ),
                color_scheme="blue",
                variant="surface",
                width="100%",
                margin_bottom="0.75rem",
            ),
            rx.fragment(),
        ),

        # ── Loading spinner ───────────────────────────────────────────────
        rx.cond(
            FixtureTickerState.is_loading,
            rx.hstack(
                rx.spinner(size="3", color_scheme="blue"),
                rx.text("Loading fixtures…", color="var(--text-sub)", font_size="0.88rem"),
                align="center",
                spacing="3",
                padding="2rem",
                justify="center",
                width="100%",
            ),
            rx.fragment(),
        ),

        # ── Empty state ───────────────────────────────────────────────────
        rx.cond(
            ~FixtureTickerState.is_loading & ~FixtureTickerState.has_rows & ~FixtureTickerState.show_no_id_warning,
            rx.vstack(
                rx.icon("search_x", size=36, color="#64748b"),
                rx.text(
                    "No clubs found matching your search.",
                    font_size="0.9rem",
                    color="var(--text-sub)",
                ),
                align="center",
                spacing="3",
                padding="3rem",
                width="100%",
            ),
            rx.fragment(),
        ),

        # ── FDR Table ─────────────────────────────────────────────────────
        rx.cond(
            ~FixtureTickerState.is_loading & FixtureTickerState.has_rows,
            rx.box(
                rx.table.root(
                    rx.table.header(
                        rx.table.row(
                            rx.table.column_header_cell(
                                "Club",
                                padding_left="0.75rem",
                                text_align="left",
                                font_family="'Outfit', sans-serif",
                                font_weight="600",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                letter_spacing="0.04em",
                                white_space="nowrap",
                            ),
                            rx.cond(
                                FixtureTickerState.only_my_squad,
                                rx.table.column_header_cell(
                                    "My Players",
                                    text_align="left",
                                    font_family="'Outfit', sans-serif",
                                    font_weight="600",
                                    font_size="0.78rem",
                                    color="var(--text-sub)",
                                    letter_spacing="0.04em",
                                ),
                                rx.fragment(),
                            ),
                            rx.foreach(
                                FixtureTickerState.gw_columns,
                                lambda gw: rx.table.column_header_cell(
                                    "GW " + gw.to_string(),
                                    text_align="center",
                                    font_family="'Outfit', sans-serif",
                                    font_weight="600",
                                    font_size="0.78rem",
                                    color="var(--text-sub)",
                                    letter_spacing="0.04em",
                                    white_space="nowrap",
                                    min_width="95px",
                                ),
                            ),
                            rx.table.column_header_cell(
                                "Total FDR",
                                text_align="center",
                                font_family="'Outfit', sans-serif",
                                font_weight="600",
                                font_size="0.78rem",
                                color="var(--text-sub)",
                                letter_spacing="0.04em",
                                white_space="nowrap",
                                min_width="80px",
                            ),
                        ),
                    ),
                    rx.table.body(
                        rx.foreach(
                            FixtureTickerState.ticker_rows,
                            _ticker_table_row,
                        ),
                    ),
                    variant="surface",
                    size="2",
                    width="100%",
                ),
                width="100%",
                overflow_x="auto",
                border="1px solid var(--border-color)",
                border_radius="10px",
                background="var(--card-bg)",
                box_shadow="0 1px 4px rgba(0,0,0,0.08)",
            ),
            rx.fragment(),
        ),

        # Footer hint
        rx.cond(
            FixtureTickerState.has_rows,
            rx.hstack(
                rx.icon("info", size=12, color="#64748b"),
                rx.text(
                    "Showing 5-GW FDR window · Sorted by total difficulty (easiest first)",
                    font_size="0.74rem",
                    color="#64748b",
                    font_style="italic",
                ),
                align="center",
                spacing="1",
                margin_top="0.5rem",
            ),
            rx.fragment(),
        ),

        on_mount=FixtureTickerState.on_tab_visible,
        width="100%",
        spacing="0",
        align="start",
    )
