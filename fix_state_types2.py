
def replace_in_file(filepath, old, new):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace(old, new)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

replace_in_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "selected_eval_gw: int = 1", "selected_eval_gw: str = \"1\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "eval_gw = self.selected_eval_gw", "eval_gw = int(self.selected_eval_gw)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "SquadAnalyzerState.selected_eval_gw.to_string()", "SquadAnalyzerState.selected_eval_gw")
replace_in_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "self.selected_eval_gw = c_gw", "self.selected_eval_gw = str(c_gw)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "if self.selected_eval_gw not in self.gw_options", "if str(self.selected_eval_gw) not in self.gw_options")

replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "next_gw: int = 1", "next_gw: str = \"1\"")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "active_calc_gw = self.next_gw", "active_calc_gw = int(self.next_gw)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "TransferAnalyzerState.next_gw.to_string()", "TransferAnalyzerState.next_gw")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "self.next_gw = c_gw", "self.next_gw = str(c_gw)")
replace_in_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "if self.next_gw not in self.gw_options", "if str(self.next_gw) not in self.gw_options")

