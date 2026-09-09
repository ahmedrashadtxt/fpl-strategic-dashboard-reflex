"""Pages package."""
from .fixture_ticker import fixture_ticker_page, FixtureTickerState
from .squad_analyzer import squad_analyzer_page, SquadAnalyzerState
from .transfer_analyzer import transfer_analyzer_page, TransferAnalyzerState
from .transfer_market import transfer_market_page, TransferMarketState
from .defensive_stats import defensive_stats_page, DefensiveStatsState
from .expected_stats import expected_stats_page, ExpectedStatsState
from .rolling_form import rolling_form_page, RollingFormState
from .audit_journal import audit_journal_page, AuditJournalState
"""Pages package for FPL Strategic Dashboard.
Pure presentation page-level layouts.
"""

__all__ = ["fixture_ticker_page", "FixtureTickerState", "squad_analyzer_page", "SquadAnalyzerState", "transfer_analyzer_page", "TransferAnalyzerState", "defensive_stats_page", "DefensiveStatsState", "expected_stats_page", "ExpectedStatsState", "rolling_form_page", "RollingFormState", "audit_journal_page", "AuditJournalState"]
from .squad_analyzer import squad_analyzer_page
from .transfer_analyzer import transfer_analyzer_page
from .simulator import simulator_page
from .expected_stats import expected_stats_page
from .defensive_stats import defensive_stats_page
from .rolling_form import rolling_form_page
from .fixture_ticker import fixture_ticker_page
from .transfer_market import transfer_market_page
from .audit_journal import audit_journal_page

__all__ = [
    "squad_analyzer_page",
    "transfer_analyzer_page",
    "simulator_page",
    "expected_stats_page",
    "defensive_stats_page",
    "rolling_form_page",
    "fixture_ticker_page",
    "transfer_market_page",
    "audit_journal_page",
]
