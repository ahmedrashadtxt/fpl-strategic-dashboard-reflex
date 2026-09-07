
import re

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("transfer_market_tab(),", "transfer_market_page(),")
text = text.replace("from fpl_strategic_dashboard_reflex.pages import ", "from fpl_strategic_dashboard_reflex.pages import transfer_market_page, TransferMarketState, ")
text = text.replace("def transfer_market_tab() -> rx.Component:\n    return rx.center(rx.text(\"Transfer Market (Placeholder)\"))\n", "")

# We need to trigger load_data for transfer market when switching tab
load_hook = "elif value == \"transfer_market\":\n            return TransferMarketState.load_data\n"
if "return TransferMarketState.load_data" not in text:
    text = text.replace("elif value == \"audit_journal\":", load_hook + "        elif value == \"audit_journal\":")

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(text)

