
import glob
import re

files = glob.glob("fpl_strategic_dashboard_reflex/pages/*.py")
for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # We want to insert `manager_id = self.manager_id` inside the `async with self` block before `c_gw = self.current_gw` or similar.
    # Let us just find `async with self:\n            c_gw = self.current_gw`
    text = text.replace("async with self:\n            c_gw = self.current_gw", "async with self:\n            manager_id = self.manager_id\n            c_gw = self.current_gw")
    text = text.replace("async with self:\n            current_gw = self.current_gw", "async with self:\n            manager_id = self.manager_id\n            current_gw = self.current_gw")
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

print("Fixed manager_id injection.")

