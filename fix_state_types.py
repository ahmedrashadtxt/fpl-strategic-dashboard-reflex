
def replace_in_file(filepath, old, new):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

replace_in_file("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "selected_gw: int = 1", "selected_gw: str = \"1\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "c_gw = self.selected_gw", "c_gw = int(self.selected_gw)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "AuditJournalState.selected_gw.to_string()", "AuditJournalState.selected_gw")
replace_in_file("fpl_strategic_dashboard_reflex/pages/audit_journal.py", "self.selected_gw = c_gw", "self.selected_gw = str(c_gw)")

replace_in_file("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "lookback_window: int = 4", "lookback_window: str = \"4\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "lw = self.lookback_window", "lw = int(self.lookback_window)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "RollingFormState.lookback_window.to_string()", "RollingFormState.lookback_window")

