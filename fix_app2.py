
import re

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    "from fpl_strategic_dashboard_reflex.pages import fixture_ticker_page, FixtureTickerState, squad_analyzer_page, SquadAnalyzerState",
    "from fpl_strategic_dashboard_reflex.pages import fixture_ticker_page, FixtureTickerState, squad_analyzer_page, SquadAnalyzerState, transfer_analyzer_page, TransferAnalyzerState"
)

text = text.replace(
    "    transfer_solver_tab,\n",
    ""
)

# update _on_tab_change
on_tab_change_new = """def _on_tab_change(tab: str):
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
                    rx.noop()
                )
            )
        ),
    ]"""

text = re.sub(r"def _on_tab_change\(tab: str\):.*?\]", on_tab_change_new, text, flags=re.DOTALL)

# update tabs.content for transfer analyzer
content_repl = """        rx.tabs.content(
            transfer_analyzer_page(),
            value="transfer_solver",
            class_name="tab-content-container",
        ),"""

text = re.sub(
    r"        rx\.tabs\.content\(\s*transfer_solver_tab\(\),\s*value=\"transfer_solver\",\s*class_name=\"tab-content-container\",\s*\),",
    content_repl,
    text,
    flags=re.DOTALL
)

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(text)

