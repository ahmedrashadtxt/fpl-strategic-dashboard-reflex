
import re
import os

with open("theme.py", "r", encoding="utf-8") as f:
    text = f.read()

# find everything between <style> and </style>
match = re.search(r"<style>(.*?)</style>", text, re.DOTALL)
if match:
    css = match.group(1)
    
    # We will remove .stApp overrides because they are not needed in Reflex
    css_lines = css.split("\n")
    clean_css = []
    skip = False
    for line in css_lines:
        if ".stApp" in line or "[data-testid" in line or "html, body, [class" in line or "#MainMenu" in line or ".block-container" in line or "h1, h2, h3" in line or "div[data-testid" in line:
            skip = True
        elif "{" in line and skip:
            pass # still skipping
        elif "}" in line and skip:
            skip = False
        elif not skip:
            clean_css.append(line)
            
    os.makedirs("assets", exist_ok=True)
    with open("assets/custom.css", "w", encoding="utf-8") as out:
        out.write("\n".join(clean_css))
    print("CSS extracted!")
else:
    print("No <style> block found!")

