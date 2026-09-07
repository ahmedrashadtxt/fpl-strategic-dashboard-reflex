
import re

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Find load_squad or analyze or any background task doing get_state
    text = re.sub(
        r"(\s*)manager_id = await self.get_state\(AppState\)\s*manager_id = manager_id\.manager_id",
        "", 
        text
    )
    
    # We will inject manager_id = self.manager_id inside the preceding async with self block
    # OR we can just add manager_id = self.manager_id to the NEXT async with self block
    text = text.replace(
        "async with self:\n            current_gw = self.current_gw",
        "async with self:\n            manager_id = self.manager_id\n            current_gw = self.current_gw"
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

fix_file("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py")
fix_file("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py")

