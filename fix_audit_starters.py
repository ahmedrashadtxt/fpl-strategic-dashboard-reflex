
with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("AuditJournalState.snapshot_data[\"starters\"]", "AuditJournalState.snapshot_starters")
text = text.replace("AuditJournalState.snapshot_data[\"bench\"]", "AuditJournalState.snapshot_bench")

with open("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "w", encoding="utf-8") as f:
    f.write(text)

