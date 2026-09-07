
with open("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "def set_simulated_chip(self, val: str):" in line:
        new_lines.append("    def set_simulated_chip(self, val: str):\n")
    elif "self.simulated_chip = val" in line and i > 55 and i < 65:
        new_lines.append("        self.simulated_chip = val\n")
    elif "return SquadAnalyzerState.load_squad" in line and i > 55 and i < 65:
        new_lines.append("        return SquadAnalyzerState.load_squad\n")
    else:
        new_lines.append(line)

with open("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

