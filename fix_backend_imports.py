
import glob
import re

for filepath in glob.glob("backend/*.py"):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    text = text.replace("from data import ", "from backend.data import ")
    text = text.replace("import data", "import backend.data as data")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)

