
import re

with open("backend/rolling_logic.py", "r", encoding="utf-8") as f:
    text = f.read()

text = "from backend.squad_logic import get_player_img_url, fmt_num, SILHOUETTE_BASE64\nfrom backend.data import get_manager_squad_ids\n" + text
text = text.replace("def get_player_img_url", "def get_player_img_url_old")

with open("backend/rolling_logic.py", "w", encoding="utf-8") as f:
    f.write(text)

