
import re

with open("fpl_strategic_dashboard_reflex/pages/__init__.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("from .defensive_stats import defensive_stats_page, DefensiveStatsState\n", "from .defensive_stats import defensive_stats_page, DefensiveStatsState\nfrom .expected_stats import expected_stats_page, ExpectedStatsState\nfrom .rolling_form import rolling_form_page, RollingFormState\nfrom .audit_journal import audit_journal_page, AuditJournalState\n")
text = text.replace("__all__ = [\"fixture_ticker_page\", \"FixtureTickerState\", \"squad_analyzer_page\", \"SquadAnalyzerState\", \"transfer_analyzer_page\", \"TransferAnalyzerState\", \"defensive_stats_page\", \"DefensiveStatsState\"]", "__all__ = [\"fixture_ticker_page\", \"FixtureTickerState\", \"squad_analyzer_page\", \"SquadAnalyzerState\", \"transfer_analyzer_page\", \"TransferAnalyzerState\", \"defensive_stats_page\", \"DefensiveStatsState\", \"expected_stats_page\", \"ExpectedStatsState\", \"rolling_form_page\", \"RollingFormState\", \"audit_journal_page\", \"AuditJournalState\"]")

with open("fpl_strategic_dashboard_reflex/pages/__init__.py", "w", encoding="utf-8") as f:
    f.write(text)

