
def fix(filepath, col_str):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("data=ExpectedStatsState.table_data,", f"data=ExpectedStatsState.table_data,\n                columns={col_str},")
    text = text.replace("data=DefensiveStatsState.table_data,", f"data=DefensiveStatsState.table_data,\n                columns={col_str},")
    text = text.replace("data=RollingFormState.table_data,", f"data=RollingFormState.table_data,\n                columns={col_str},")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

fix("fpl_strategic_dashboard_reflex/pages/expected_stats.py", "ExpectedStatsState.columns")
fix("fpl_strategic_dashboard_reflex/pages/defensive_stats.py", "DefensiveStatsState.columns")
fix("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "RollingFormState.columns")

