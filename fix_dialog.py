
import re

with open("fpl_strategic_dashboard_reflex/components/id_dialog.py", "r", encoding="utf-8") as f:
    text = f.read()

# Change def id_dialog() -> rx.Component:
# to def id_dialog(on_save_handler=None) -> rx.Component:
text = text.replace("def id_dialog() -> rx.Component:", "def id_dialog(on_save_handler=None) -> rx.Component:")

# Change on_click=AppState.save_manager_id,
# to on_click=[AppState.save_manager_id, on_save_handler(AppState.selected_tab)] if on_save_handler else AppState.save_manager_id,
text = text.replace(
    "on_click=AppState.save_manager_id,",
    "on_click=[AppState.save_manager_id, on_save_handler(AppState.selected_tab)] if on_save_handler else AppState.save_manager_id,"
)

with open("fpl_strategic_dashboard_reflex/components/id_dialog.py", "w", encoding="utf-8") as f:
    f.write(text)

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "r", encoding="utf-8") as f:
    app_text = f.read()

app_text = app_text.replace("id_dialog(),", "id_dialog(on_save_handler=_on_tab_change),")

with open("fpl_strategic_dashboard_reflex/fpl_strategic_dashboard_reflex.py", "w", encoding="utf-8") as f:
    f.write(app_text)

