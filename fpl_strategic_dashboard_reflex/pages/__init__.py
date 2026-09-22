"""Pages package for FPL Strategic Dashboard.
Pure presentation page-level layouts.
"""
from .squad_analyzer import squad_analyzer_page
from .transfer_analyzer import transfer_analyzer_page
from .simulator import simulator_page
from .expected_stats import expected_stats_page
from .defensive_stats import defensive_stats_page
from .rolling_form import rolling_form_page
from .fixture_ticker import fixture_ticker_page
from .transfer_market import transfer_market_page

__all__ = [
    "squad_analyzer_page",
    "transfer_analyzer_page",
    "simulator_page",
    "expected_stats_page",
    "defensive_stats_page",
    "rolling_form_page",
    "fixture_ticker_page",
    "transfer_market_page",
]
