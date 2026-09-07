
with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("s[\"out\"][\"name\"]", "s[\"out_name\"]")
text = text.replace("s[\"in\"][\"name\"]", "s[\"in_name\"]")

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

