
with open("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace("lookback_window: int = 4", "lookback_window: str = \"4\"")
text = text.replace("self.lookback_window = int(val)", "self.lookback_window = str(val)")
text = text.replace("lw = self.lookback_window", "lw = int(self.lookback_window)")
text = text.replace("RollingFormState.lookback_window.to_string()", "RollingFormState.lookback_window")

with open("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "w", encoding="utf-8") as f:
    f.write(text)

