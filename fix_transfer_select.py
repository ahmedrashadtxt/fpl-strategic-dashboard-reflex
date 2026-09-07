
import re

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("value=TransferAnalyzerState.selected_positive[0] if TransferAnalyzerState.selected_positive else \"\"", "value=rx.cond(TransferAnalyzerState.selected_positive.length() > 0, TransferAnalyzerState.selected_positive[0], \"\")")
text = text.replace("value=TransferAnalyzerState.selected_negative[0] if TransferAnalyzerState.selected_negative else \"\"", "value=rx.cond(TransferAnalyzerState.selected_negative.length() > 0, TransferAnalyzerState.selected_negative[0], \"\")")

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

