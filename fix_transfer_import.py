
import re

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    "from backend.transfer_logic import (\n    fetch_manager_entry, fetch_manager_history, fetch_manager_picks,\n",
    "from backend.squad_logic import fetch_manager_entry, fetch_manager_history, fetch_manager_picks\nfrom backend.transfer_logic import (\n"
)

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

