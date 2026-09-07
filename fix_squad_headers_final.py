import re
with open('fpl_strategic_dashboard_reflex/pages/squad_analyzer.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add set_simulated_chip
if 'def set_simulated_chip' not in text:
    chip_code = '''
    def set_simulated_chip(self, val: str):
        self.simulated_chip = val
        return SquadAnalyzerState.load_squad
'''
    text = text.replace('def set_eval_gw', chip_code.strip('\n') + '\n    def set_eval_gw')

# Change gw_options from list[int] to list[str]
text = text.replace('gw_options: list[int] = []', 'gw_options: list[str] = []')

# In _run_squad_analysis, change the return to include header texts
old_return = '''        return {
            'mgr_name': mgr_data.get("name", "My Team"),'''

new_return = '''
        squad_pts = int(starters_df["GW_Points"].sum() - transfers_cost) if not starters_df.empty else 0
        squad_xp = float(starters_df["Proj_Pts"].sum()) if not starters_df.empty else 0.0
        squad_header = f"Your Squad - GW{selected_eval_gw} ({squad_pts} pts)" if is_live else f"Your Squad - GW{selected_eval_gw} ({squad_xp:.1f} xP)"
        
        comp_header = ""
        if comp and not comp_xi.empty:
            comp_xp = float(comp_xi["Proj_Pts"].sum())
            comp_header = f"Super Team - GW{selected_eval_gw} ({comp_xp:.1f} xP)" if super_t else f"Dream 15 - GW{selected_eval_gw} ({comp_xp:.1f} xP)"

        return {
            'squad_header_text': squad_header,
            'comp_header_text': comp_header,
            'gw_options': [str(gw) for gw in all_gw_options],
            'mgr_name': mgr_data.get("name", "My Team"),'''

text = text.replace(old_return, new_return)

# In load_squad state update, add the header fields
state_update_old = '''                if str(self.selected_eval_gw) not in self.gw_options and self.gw_options:
                    self.selected_eval_gw = result.get('default_gw', self.gw_options[0])'''

state_update_new = '''                if str(self.selected_eval_gw) not in self.gw_options and self.gw_options:
                    self.selected_eval_gw = str(result.get('default_gw', self.gw_options[0]))
                self.squad_header_text = result.get('squad_header_text', 'Current Squad')
                self.comp_header_text = result.get('comp_header_text', 'Dream 15')'''

text = text.replace(state_update_old, state_update_new)

# Add the state variables
if 'squad_header_text: str' not in text:
    text = text.replace('enable_comparison: bool = False', 'enable_comparison: bool = False\n    squad_header_text: str = "Current Squad"\n    comp_header_text: str = "Dream 15"')

# Change the rx.heading in UI
text = text.replace('rx.heading("Current Squad", size="4", margin_bottom="2")', 'rx.heading(SquadAnalyzerState.squad_header_text, size="4", margin_bottom="2")')
text = text.replace('rx.heading("Dream 15", size="4", margin_bottom="2")', 'rx.heading(SquadAnalyzerState.comp_header_text, size="4", margin_bottom="2")')

# Remove the old gw_options
text = text.replace("'gw_options': all_gw_options,", "")

with open('fpl_strategic_dashboard_reflex/pages/squad_analyzer.py', 'w', encoding='utf-8') as f:
    f.write(text)

