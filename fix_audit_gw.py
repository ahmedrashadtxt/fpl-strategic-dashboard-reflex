
with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("selected_gw: int = 1", "selected_gw: str = \"1\"")
text = text.replace("self.selected_gw = int(val)", "self.selected_gw = str(val)")
text = text.replace("c_gw = self.selected_gw", "c_gw = int(self.selected_gw)")
text = text.replace("self.selected_gw = c_gw", "self.selected_gw = str(c_gw)")

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

