"""Component exports for the Reflex shell."""
"""Components package for FPL Strategic Dashboard.
Pure presentation UI functions returning rx.Component.
Stateless and agnostic of backend database/logic.
"""

from .header import header
from .id_dialog import id_dialog
from .metric_card import metric_card
from .metrics_bar import metrics_bar
from .tab_placeholders import (
    squad_analyzer_tab,
    transfer_solver_tab,
    expected_stats_tab,
    defensive_stats_tab,
    rolling_form_tab,
    fixture_ticker_tab,
    transfer_market_tab,
    audit_journal_tab,
)
from .pitch import pitch_view, squad_list_view
from .guide_popover import guide_popover
from .filters import search_input, filter_select, filter_bar
from .data_table import data_table
from .utils import concat

__all__ = [
    "header",
    "id_dialog",
    "metric_card",
    "metrics_bar",
    "squad_analyzer_tab",
    "transfer_solver_tab",
    "expected_stats_tab",
    "defensive_stats_tab",
    "rolling_form_tab",
    "fixture_ticker_tab",
    "transfer_market_tab",
    "audit_journal_tab",
    "pitch_view",
    "squad_list_view",
    "guide_popover",
    "search_input",
    "filter_select",
    "filter_bar",
    "data_table",
    "concat",
]

