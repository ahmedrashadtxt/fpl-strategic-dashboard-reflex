
import os

with open("tabs/audit_journal.py", "r", encoding="utf-8") as f:
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
    if "def render_audit_journal_tab" in line:
        break
    backend_lines.append(line)

with open("backend/audit_logic.py", "w", encoding="utf-8") as f:
    f.writelines(backend_lines)

