
import re

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("\"out\": {\"name\": s[\"out\"][\"Player\"], \"team\": s[\"out\"][\"Team\"], \"pos\": s[\"out\"][\"Pos\"], \"cost\": float(s[\"out\"][\"Cost\"]), \"xp\": float(s[\"out\"][\"Horizon_xP\"])},", "\"out_name\": str(s[\"out\"][\"Player\"]),")
text = text.replace("\"in\": {\"name\": s[\"in\"][\"Player\"], \"team\": s[\"in\"][\"Team\"], \"pos\": s[\"in\"][\"Pos\"], \"cost\": float(s[\"in\"][\"Cost\"]), \"xp\": float(s[\"in\"][\"Horizon_xP\"])},", "\"in_name\": str(s[\"in\"][\"Player\"]),")
text = text.replace("lambda s: rx.text(s[\"out\"][\"name\"], \" ? \", s[\"in\"][\"name\"])", "lambda s: rx.text(s[\"out_name\"], \" ? \", s[\"in_name\"])")
text = text.replace("swaps: List[Dict[str, Any]] = []", "swaps: List[Dict[str, str]] = []")

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

