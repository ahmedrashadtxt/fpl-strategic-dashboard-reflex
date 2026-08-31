# tabs/__init__.py
from .defensive_stats import render_defensive_stats_tab
from .expected_stats import render_expected_stats_tab
from .fixture_ticker import render_fixture_ticker_tab
from .rolling_form import render_rolling_form_tab
from .squad_analyzer import render_squad_analyzer_tab
from .transfer_analyzer import render_transfer_analyzer_tab
from .transfer_market import render_transfer_market_tab

__all__ = [
    "render_defensive_stats_tab",
    "render_expected_stats_tab",
    "render_fixture_ticker_tab",
    "render_rolling_form_tab",
    "render_squad_analyzer_tab",
    "render_transfer_analyzer_tab",
    "render_transfer_market_tab",
]