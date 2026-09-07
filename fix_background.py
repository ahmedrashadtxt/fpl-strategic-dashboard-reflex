
import re

for filename in ["fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py"]:
    with open(filename, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("@rx.background", "@rx.event(background=True)")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

