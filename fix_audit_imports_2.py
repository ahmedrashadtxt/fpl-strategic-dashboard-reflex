
import re

with open("backend/audit_logic.py", "r", encoding="utf-8") as f:
    text = f.read()

text = re.sub(r"from \.squad_analyzer import \([\s\S]*?\)", "", text)

with open("backend/audit_logic.py", "w", encoding="utf-8") as f:
    f.write(text)

