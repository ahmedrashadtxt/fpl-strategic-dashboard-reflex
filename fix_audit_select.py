
import re

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("versions: List[Dict[str, Any]] = []", "version_options: List[str] = []")
text = text.replace("self.versions = result", "self.version_options = [v[\"version\"] for v in result]")
text = text.replace("self.versions = []", "self.version_options = []")
text = text.replace("AuditJournalState.versions", "AuditJournalState.version_options")

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

