
def replace_in_file(filepath, old, new):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "horizon_len: int = 1", "horizon_len: str = \"1\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "ft_count: int = 1", "ft_count: str = \"1\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "max_hits: int = 1", "max_hits: str = \"1\"")

replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "hz = self.horizon_len", "hz = int(self.horizon_len)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "ft = self.ft_count", "ft = int(self.ft_count)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "mh = self.max_hits", "mh = int(self.max_hits)")

replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "TransferAnalyzerState.horizon_len.to_string()", "TransferAnalyzerState.horizon_len")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "TransferAnalyzerState.ft_count.to_string()", "TransferAnalyzerState.ft_count")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "TransferAnalyzerState.max_hits.to_string()", "TransferAnalyzerState.max_hits")

replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "self.ft_count = result[\"init_ft\"]", "self.ft_count = str(result[\"init_ft\"])")

