
with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix on_change binding
text = text.replace("on_change=AppState.set_tab", "on_change=_on_tab_change")

# Fix transfer_market missing in _on_tab_change
old_tab_cond = """rx.cond(
                                    tab == "audit_journal",
                                    AuditJournalState.load_data(),
                                    rx.noop()
                                )"""
new_tab_cond = """rx.cond(
                                    tab == "audit_journal",
                                    AuditJournalState.load_data(),
                                    rx.cond(
                                        tab == "transfer_market",
                                        TransferMarketState.load_data(),
                                        rx.noop()
                                    )
                                )"""
text = text.replace(old_tab_cond, new_tab_cond)

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(text)

