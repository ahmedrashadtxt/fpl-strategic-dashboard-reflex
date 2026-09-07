
import re

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("defensive_stats_tab()", "defensive_stats_page()")
text = text.replace("expected_stats_tab()", "expected_stats_page()")
text = text.replace("rolling_form_tab()", "rolling_form_page()")
text = text.replace("audit_journal_tab()", "audit_journal_page()")

text = text.replace("from fpl_strategic_dashboard_reflex.pages import fixture_ticker_page, FixtureTickerState, squad_analyzer_page, SquadAnalyzerState, transfer_analyzer_page, TransferAnalyzerState", "from fpl_strategic_dashboard_reflex.pages import fixture_ticker_page, FixtureTickerState, squad_analyzer_page, SquadAnalyzerState, transfer_analyzer_page, TransferAnalyzerState, defensive_stats_page, DefensiveStatsState, expected_stats_page, ExpectedStatsState, rolling_form_page, RollingFormState, audit_journal_page, AuditJournalState")

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(text)

