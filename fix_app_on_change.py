
import re

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

on_change_new = """def _on_tab_change(tab: str):
    return [
        AppState.set_tab(tab),
        rx.cond(
            tab == "fixture_ticker",
            FixtureTickerState.on_tab_visible(),
            rx.cond(
                tab == "squad_analyzer",
                SquadAnalyzerState.load_squad(),
                rx.cond(
                    tab == "transfer_solver",
                    TransferAnalyzerState.analyze(),
                    rx.cond(
                        tab == "defensive_stats",
                        DefensiveStatsState.load_data(),
                        rx.cond(
                            tab == "expected_stats",
                            ExpectedStatsState.load_data(),
                            rx.cond(
                                tab == "rolling_form",
                                RollingFormState.load_data(),
                                rx.cond(
                                    tab == "audit_journal",
                                    AuditJournalState.load_data(),
                                    rx.noop()
                                )
                            )
                        )
                    )
                )
            )
        ),
    ]"""

text = re.sub(r"def _on_tab_change\(tab: str\):.*?\]", on_change_new, text, flags=re.DOTALL)

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(text)

