
import re

with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

old_loading = """            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text(TransferAnalyzerState.status_message, color="gray"),
                    spacing="4",
                ),
                padding="8",
            )"""

new_loading = """            rx.center(
                rx.card(
                    rx.vstack(
                        rx.icon("bot", size=40, color="var(--accent-9)"),
                        rx.heading("Synthesizing Path...", size="4"),
                        rx.text(TransferAnalyzerState.status_message, color="gray", size="2"),
                        rx.progress(value=None, width="100%", color_scheme="green"),
                        align_items="center",
                        spacing="4"
                    ),
                    padding="6",
                    width="350px",
                    box_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)"
                ),
                padding="12",
                width="100%",
                min_height="300px"
            )"""

if "rx.spinner(size=\"3\")" in text:
    text = text.replace(old_loading, new_loading)
    with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Updated transfer_analyzer loading UI")
else:
    print("Could not find old loading UI in transfer_analyzer.py")

