
def add_cols(filepath, cols_list, state_name):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    if "def columns(self)" not in text:
        # add to the end of state class
        # we will just add it before the first rx.event or before the end of class
        # just replace is_loading: bool = False
        text = text.replace("is_loading: bool = False\n", f"is_loading: bool = False\n    @rx.var\n    def columns(self) -> list[str]:\n        return {cols_list}\n")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

add_cols("fpl_strategic_dashboard_reflex/pages/expected_stats.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"xG\", \"xA\", \"xGI\", \"gw_xp\", \"Form\", \"Att_Ret_Prob\", \"BPS\"]", "ExpectedStatsState")
add_cols("fpl_strategic_dashboard_reflex/pages/defensive_stats.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"Clean_Sheets\", \"Goals_Conceded\", \"xGC\", \"def_xp\", \"DC_per_90\", \"Saves\"]", "DefensiveStatsState")
add_cols("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"Form\", \"Upcoming_FDR\", \"form_xp\", \"xGI\"]", "RollingFormState")

