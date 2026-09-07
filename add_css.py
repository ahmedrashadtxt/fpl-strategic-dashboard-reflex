
with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    text = f.read()

if "stylesheets=" not in text:
    text = text.replace("app = rx.App(", "app = rx.App(stylesheets=[\"/custom.css\"],\n             theme=rx.theme(appearance=\"dark\", accent_color=\"green\", panel_background=\"solid\"),\n             ")
    
    with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
        f.write(text)

