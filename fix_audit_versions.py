
with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("    selected_version: str = \"\"", "    selected_version: str = \"\"\n    \n    @rx.var\n    def version_options(self) -> list[str]:\n        return [v[\"version_id\"] for v in self.versions]")
text = text.replace("rx.select(\n                            AuditJournalState.versions,", "rx.select(\n                            AuditJournalState.version_options,")
text = text.replace("AuditJournalState.versions.length() > 0", "AuditJournalState.version_options.length() > 0")

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

