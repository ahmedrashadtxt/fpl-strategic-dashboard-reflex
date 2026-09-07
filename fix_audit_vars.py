
import re

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

new_vars = """
    @rx.var
    def snapshot_starters(self) -> List[Dict[str, Any]]:
        return self.snapshot_data.get("starters", []) if self.snapshot_data else []
        
    @rx.var
    def snapshot_bench(self) -> List[Dict[str, Any]]:
        return self.snapshot_data.get("bench", []) if self.snapshot_data else []
        
    @rx.var
"""

text = text.replace("@rx.var\n    def has_snapshot(self)", new_vars + "def has_snapshot(self)")
text = text.replace("AuditJournalState.snapshot_data[\"starters\"]", "AuditJournalState.snapshot_starters")
text = text.replace("AuditJournalState.snapshot_data[\"bench\"]", "AuditJournalState.snapshot_bench")

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

