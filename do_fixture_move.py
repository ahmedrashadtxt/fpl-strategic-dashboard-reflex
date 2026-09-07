
import re

with open("fpl_strategic_dashboard_reflex/pages/fixture_ticker.py", "r", encoding="utf-8") as f:
    text = f.read()

parts = text.split("class FixtureTickerState")
header = parts[0]
footer = "class FixtureTickerState" + parts[1]

# split header by "def _build_ticker_rows"
header_parts = header.split("def _build_ticker_rows(")
imports = header_parts[0]
func_body = "def _build_ticker_rows(" + header_parts[1]

with open("backend/fixture_logic.py", "w", encoding="utf-8") as out:
    out.write("import pandas as pd\nfrom rapidfuzz import fuzz, process\nfrom backend.data import get_connection, get_manager_squad_ids\n\n")
    # need to trim off any trailing whitespace before class
    out.write(func_body.strip() + "\n")

# remove pandas and rapidfuzz from pages/fixture_ticker.py
imports = imports.replace("import pandas as pd\n", "")
imports = imports.replace("from rapidfuzz import fuzz, process\n", "")
imports = imports.replace("from backend.data import get_connection, get_manager_squad_ids", "from backend.fixture_logic import _build_ticker_rows")

new_text = imports + "\n" + footer
with open("fpl_strategic_dashboard_reflex/pages/fixture_ticker.py", "w", encoding="utf-8") as f:
    f.write(new_text)

print("Moved!")

