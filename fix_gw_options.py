
import re

def fix_state(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace("gw_options: List[int] = []", "gw_options: List[str] = []")
    text = text.replace("all_gw_options = list(range(c_gw, min(c_gw + 6, 39)))", "all_gw_options = [str(x) for x in range(c_gw, min(c_gw + 6, 39))]")
    
    # Also handle selected_eval_gw and next_gw
    # We still need them as int for backend. Let's just convert string for gw_options.
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

fix_state("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py")
fix_state("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py")

