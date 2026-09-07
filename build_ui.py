
import re

with open("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "r", encoding="utf-8") as f:
    text = f.read()

# Replace Controls section
old_controls = """                # Controls
                rx.hstack(
                    rx.text("GW:", weight="bold"),
                    rx.select(
                        SquadAnalyzerState.gw_options,
                        value=SquadAnalyzerState.selected_eval_gw,
                        on_change=SquadAnalyzerState.set_eval_gw
                    ),
                    rx.checkbox("Pitch View", checked=SquadAnalyzerState.pitch_view, on_change=SquadAnalyzerState.set_pitch_view),
                    rx.checkbox("Compare", checked=SquadAnalyzerState.enable_comparison, on_change=SquadAnalyzerState.set_enable_comparison),
                    rx.cond(
                        SquadAnalyzerState.enable_comparison,
                        rx.checkbox("Super Team", checked=SquadAnalyzerState.super_team_mode, on_change=SquadAnalyzerState.set_super_team_mode)
                    ),
                    rx.checkbox("Betting xG", checked=SquadAnalyzerState.enable_betting, on_change=SquadAnalyzerState.set_enable_betting),
                    spacing="4",
                    width="100%",
                    align_items="center",
                    margin_bottom="4"
                ),"""

new_controls = """                # Chips Row
                rx.vstack(
                    rx.text("HALF 1 CHIPS (GW1-19)", size="1", color="gray", weight="bold"),
                    rx.radio(
                        items=["None", "Wildcard", "Free Hit", "Bench Boost", "Triple Captain"],
                        value=SquadAnalyzerState.simulated_chip,
                        on_change=SquadAnalyzerState.set_simulated_chip,
                        direction="row",
                        spacing="4"
                    ),
                    spacing="1",
                    margin_bottom="4"
                ),
                # Controls
                rx.vstack(
                    rx.hstack(
                        rx.icon("calendar"),
                        rx.text("Select Gameweek:", weight="bold"),
                        align_items="center"
                    ),
                    rx.radio(
                        items=SquadAnalyzerState.gw_options,
                        value=SquadAnalyzerState.selected_eval_gw,
                        on_change=SquadAnalyzerState.set_eval_gw,
                        direction="row",
                        spacing="4"
                    ),
                    spacing="2",
                    margin_bottom="4"
                ),
                rx.hstack(
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.pitch_view, on_change=SquadAnalyzerState.set_pitch_view),
                        rx.text("Pitch View"),
                        align_items="center"
                    ),
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.enable_comparison, on_change=SquadAnalyzerState.set_enable_comparison),
                        rx.text("Comparison"),
                        align_items="center"
                    ),
                    rx.cond(
                        SquadAnalyzerState.enable_comparison,
                        rx.hstack(
                            rx.switch(checked=SquadAnalyzerState.super_team_mode, on_change=SquadAnalyzerState.set_super_team_mode),
                            rx.text("Super Team"),
                            align_items="center"
                        ),
                        rx.box()
                    ),
                    rx.hstack(
                        rx.switch(checked=SquadAnalyzerState.enable_betting, on_change=SquadAnalyzerState.set_enable_betting),
                        rx.text("Betting Market xG"),
                        align_items="center"
                    ),
                    spacing="6",
                    width="100%",
                    align_items="center",
                    margin_bottom="4"
                ),
                # Market Weight Slider
                rx.cond(
                    SquadAnalyzerState.enable_betting,
                    rx.vstack(
                        rx.text("Market Implied Weight: " + SquadAnalyzerState.market_weight.to_string(), size="2"),
                        rx.slider(
                            default_value=[35],
                            min=0,
                            max=100,
                            on_value_commit=SquadAnalyzerState.set_market_weight,
                            width="100%"
                        ),
                        rx.hstack(
                            rx.switch(checked=SquadAnalyzerState.factor_movement, on_change=SquadAnalyzerState.set_factor_movement),
                            rx.text("Line Movement"),
                            align_items="center"
                        ),
                        spacing="2",
                        width="300px",
                        margin_bottom="4"
                    ),
                    rx.box()
                ),"""

if "SquadAnalyzerState.gw_options," in text:
    text = text.replace(old_controls, new_controls)
else:
    print("Could not find controls block!")

with open("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "w", encoding="utf-8") as f:
    f.write(text)

