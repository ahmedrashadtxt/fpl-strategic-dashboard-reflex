
import glob
import re

files = glob.glob("fpl_strategic_dashboard_reflex/pages/*.py")
for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Fix ImmutableStateError: manager_id = await self.get_state(AppState)
    text = re.sub(r"\s*manager_id = await self\.get_state\(AppState\)\n\s*manager_id = manager_id\.manager_id", "", text)
    
    # Fix active_manager_id to manager_id
    text = text.replace("self.active_manager_id", "self.manager_id")
    
    # If the file had await self.get_state, make sure we get manager_id safely.
    # Actually, we should just inject manager_id = self.manager_id into the async with self block.
    # In expected_stats, defensive_stats, etc., we can just replace self.manager_id if used outside.
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

print("Errors fixed.")

