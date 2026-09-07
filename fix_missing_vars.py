
with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

new_vars = """
    @rx.var
    def snapshot_starters(self) -> list[dict]:
        return self.snapshot_data.get("starters", []) if self.snapshot_data else []
        
    @rx.var
    def snapshot_bench(self) -> list[dict]:
        return self.snapshot_data.get("bench", []) if self.snapshot_data else []
"""
if "def snapshot_starters" not in text:
    text = text.replace("    def has_snapshot(self) -> bool:", new_vars + "\n    @rx.var\n    def has_snapshot(self) -> bool:")
    # remove duplicate @rx.var if it happened
    text = text.replace("@rx.var\n    @rx.var\n    def has_snapshot", "@rx.var\n    def has_snapshot")
    
with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

