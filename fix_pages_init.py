
import re

with open("fpl_strategic_dashboard_reflex/pages/__init__.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("from .transfer_analyzer import transfer_analyzer_page, TransferAnalyzerState\n", "from .transfer_analyzer import transfer_analyzer_page, TransferAnalyzerState\nfrom .transfer_market import transfer_market_page, TransferMarketState\n")

# __all__ 
if "transfer_market_page" not in text:
    text = text.replace("]", ", \"transfer_market_page\", \"TransferMarketState\"]")

with open("fpl_strategic_dashboard_reflex/pages/__init__.py", "w", encoding="utf-8") as f:
    f.write(text)

