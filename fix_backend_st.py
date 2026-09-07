
import glob
import re

for filepath in glob.glob("backend/*.py"):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Remove any stray @st. decorators
    text = re.sub(r"@st\.[a-zA-Z_]+\n", "", text)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

