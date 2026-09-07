
import re

with open("fpl_strategic_dashboard_reflex/pages/fixture_ticker.py", "r", encoding="utf-8") as f:
    text = f.read()

# Extract _build_ticker_rows
match = re.search(r"def _build_ticker_rows\(.*?\n\s+return list\(sorted_clubs\.values\(\)\)\n", text, re.DOTALL)
if match:
    func_text = match.group(0)
    with open("backend/fixture_logic.py", "w", encoding="utf-8") as out:
        out.write("import pandas as pd\nfrom rapidfuzz import fuzz, process\nfrom backend.data import get_connection, get_manager_squad_ids\n\n")
        out.write(func_text)
    
    # Remove from pages/fixture_ticker.py
    new_text = text.replace(func_text, "")
    # Update import
    new_text = new_text.replace("from backend.data import get_connection, get_manager_squad_ids", "from backend.fixture_logic import _build_ticker_rows")
    with open("fpl_strategic_dashboard_reflex/pages/fixture_ticker.py", "w", encoding="utf-8") as f:
        f.write(new_text)
else:
    print("Match not found.")

