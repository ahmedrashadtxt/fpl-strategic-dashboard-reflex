
import os

with open("tabs/expected_stats.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

backend_lines = []
for line in lines:
    if "import streamlit as st" in line:
        continue
    if "@st.cache_data" in line:
        continue
    if "from st_keyup import st_keyup" in line:
        continue
    if "from theme import" in line:
        continue
    if "def render_expected_stats_tab" in line:
        break
    backend_lines.append(line)

with open("backend/expected_logic.py", "w", encoding="utf-8") as f:
    f.writelines(backend_lines)

