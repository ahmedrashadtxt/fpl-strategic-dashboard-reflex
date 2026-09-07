
import re

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Find rx.select([...]) with ints and convert to strings
    # But doing this properly requires ast or manual.
    text = re.sub(r"rx\.select\(\s*\[1,\s*2,\s*3,\s*4,\s*5\]", "rx.select([\"1\", \"2\", \"3\", \"4\", \"5\"]", text)
    text = re.sub(r"rx\.select\(\s*\[str\(i\) for i in range\(1, 39\)\]", "rx.select([str(i) for i in range(1, 39)])", text)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

fix_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py")
fix_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py")
fix_file("fpl_strategic_dashboard_reflex/pages/audit_journal.py")

