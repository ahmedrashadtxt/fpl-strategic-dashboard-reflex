
import re

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("render_transfer_pitch_component(base_xi, base_bench, is_live=False)", "render_transfer_pitch_component(base_xi, base_bench)")
text = text.replace("render_transfer_pitch_component(trans_xi, trans_bench, is_live=False)", "render_transfer_pitch_component(trans_xi, trans_bench)")

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

