
with open("backend/rolling_logic.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "SILHOUETTE_BASE64," in line and "    " in line:
        continue
    if "fmt_num," in line and "    " in line:
        continue
    if "render_list_card," in line and "    " in line:
        continue
    if "render_sortable_table," in line and "    " in line:
        continue
    if "section_header," in line and "    " in line:
        continue
    if line.strip() == ")":
        continue
    new_lines.append(line)

with open("backend/rolling_logic.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

