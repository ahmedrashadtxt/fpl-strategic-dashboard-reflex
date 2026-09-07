
import re

with open("fpl_strategic_dashboard_reflex/state.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r"summary_df\s*=\s*get_summary_stats\(conn\).*?self\.cooling_transfers\s*=\s*int\(row\.get\(\"cooling\",\s*0\)\s*or\s*0\)", "", text, flags=re.DOTALL)

with open("fpl_strategic_dashboard_reflex/state.py", "w", encoding="utf-8") as f:
    f.write(text)

