
import re

with open("backend/rolling_logic.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r"@st\.[a-zA-Z_]+\n", "", text)
text = re.sub(r"    SILHOUETTE_BASE64,\n    fmt_num,\n    render_list_card,\n    render_sortable_table,\n    section_header,\n\)\n", "", text)

text = text.replace("from backend.data import get_manager_squad_ids\nfrom data import get_manager_squad_ids, get_teams_fdr_map", "from backend.data import get_manager_squad_ids, get_teams_fdr_map")

with open("backend/rolling_logic.py", "w", encoding="utf-8") as f:
    f.write(text)

