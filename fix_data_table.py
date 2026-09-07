
import re

def fix_file(filepath, cols_str):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
        
    text = re.sub(r"rx\.data_table\(\s*data=(.*?)State\.table_data,", f"rx.data_table(data=\\1State.table_data, columns={cols_str},", text)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

fix_file("fpl_strategic_dashboard_reflex/pages/defensive_stats.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"Clean_Sheets\", \"Goals_Conceded\", \"xGC\", \"def_xp\", \"DC_per_90\", \"Saves\"]")

fix_file("fpl_strategic_dashboard_reflex/pages/expected_stats.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"xG\", \"xA\", \"xGI\", \"gw_xp\", \"Form\", \"Att_Ret_Prob\", \"BPS\"]")

fix_file("fpl_strategic_dashboard_reflex/pages/rolling_form.py", "[\"Player\", \"Team\", \"Pos\", \"Price\", \"Avg_Mins_GW\", \"Total_Points\", \"Form\", \"Upcoming_FDR\", \"form_xp\", \"xGI\"]")

