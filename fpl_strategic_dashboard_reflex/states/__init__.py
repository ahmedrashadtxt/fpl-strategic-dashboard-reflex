"""States package for FPL Strategic Dashboard.
Domain-partitioned rx.State classes.
"""

from .base import AppState
from .metrics import DashboardMetricsState
from .squad import SquadAnalyzerState
from .transfer import TransferAnalyzerState
from .simulator import SimulatorState
from .expected import ExpectedStatsState
from .defensive import DefensiveStatsState
from .rolling import RollingFormState
from .fixtures import FixtureTickerState
from .market import TransferMarketState
from .audit import AuditJournalState

__all__ = [
    "AppState",
    "DashboardMetricsState",
    "SquadAnalyzerState",
    "TransferAnalyzerState",
    "SimulatorState",
    "ExpectedStatsState",
    "DefensiveStatsState",
    "RollingFormState",
    "FixtureTickerState",
    "TransferMarketState",
    "AuditJournalState",
]

