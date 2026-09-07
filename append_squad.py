import sys
content = """
def squad_list_view(starters: list, bench: list):
    return rx.vstack(
        rx.foreach(
            starters,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="10px",
                border="1px solid rgba(255,255,255,0.1)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.6)",
                margin_bottom="2px"
            )
        ),
        rx.text("Bench", font_weight="bold", margin_top="4"),
        rx.foreach(
            bench,
            lambda row: rx.box(
                rx.html(row["tooltip_html"]),
                width="100%",
                padding="10px",
                border="1px solid rgba(255,255,255,0.1)",
                border_radius="8px",
                background="rgba(15, 23, 42, 0.4)",
                margin_bottom="2px"
            )
        ),
        width="100%",
        spacing="2"
    )

def squad_analyzer_page():
    return rx.box(
        rx.cond(
            SquadAnalyzerState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text(SquadAnalyzerState.status_message, color="gray"),
                    spacing="4",
                ),
                padding="8",
            )
        ),
        rx.cond(
            (SquadAnalyzerState.manager_id == ""),
            rx.center(
                rx.callout(
                    "👆 Click 'Enter FPL ID' in the top-right header to load your squad analysis.",
                    icon="info",
                ),
                padding="8"
            )
        ),
        rx.cond(
            (SquadAnalyzerState.manager_id != "") & ~SquadAnalyzerState.is_loading & SquadAnalyzerState.has_data,
            rx.vstack(
                # Metrics Row
                rx.grid(
                    rx.box(rx.text("Manager", size="1", color="gray"), rx.text(SquadAnalyzerState.mgr_name, weight="bold")),
                    rx.box(rx.text("Overall Rank", size="1", color="gray"), rx.text(SquadAnalyzerState.overall_rank, weight="bold")),
                    rx.box(rx.text("Total Points", size="1", color="gray"), rx.text(SquadAnalyzerState.total_points, weight="bold")),
                    rx.box(rx.text(SquadAnalyzerState.active_gw_label, size="1", color="gray"), rx.text(SquadAnalyzerState.active_gw_pts, weight="bold")),
                    rx.box(rx.text("Squad Value", size="1", color="gray"), rx.text(SquadAnalyzerState.squad_value, weight="bold")),
                    rx.box(rx.text("In The Bank", size="1", color="gray"), rx.text(SquadAnalyzerState.bank_balance, weight="bold")),
                    columns="6",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Controls
                rx.hstack(
                    rx.text("GW:", weight="bold"),
                    rx.select(
                        SquadAnalyzerState.gw_options,
                        value=SquadAnalyzerState.selected_eval_gw.to_string(),
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
                ),
                
                # Views
                rx.cond(
                    SquadAnalyzerState.enable_comparison,
                    rx.grid(
                        rx.box(
                            rx.text("Current Squad", weight="bold", margin_bottom="2"),
                            rx.cond(
                                SquadAnalyzerState.pitch_view,
                                rx.html(SquadAnalyzerState.base_pitch_html),
                                squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench)
                            ),
                            width="100%"
                        ),
                        rx.box(
                            rx.text(rx.cond(SquadAnalyzerState.super_team_mode, "Super Team", "Dream 15"), weight="bold", margin_bottom="2"),
                            rx.cond(
                                SquadAnalyzerState.pitch_view,
                                rx.html(SquadAnalyzerState.comp_pitch_html),
                                squad_list_view(SquadAnalyzerState.compare_starters, SquadAnalyzerState.compare_bench)
                            ),
                            width="100%"
                        ),
                        columns="2",
                        spacing="4",
                        width="100%"
                    ),
                    rx.box(
                        rx.text("Current Squad", weight="bold", margin_bottom="2"),
                        rx.cond(
                            SquadAnalyzerState.pitch_view,
                            rx.html(SquadAnalyzerState.base_pitch_html),
                            squad_list_view(SquadAnalyzerState.starters, SquadAnalyzerState.bench)
                        ),
                        width="100%"
                    )
                ),
                width="100%",
                spacing="4"
            )
        ),
        width="100%",
        on_mount=SquadAnalyzerState.load_squad
    )
"""
with open("fpl_strategic_dashboard_reflex/pages/squad_analyzer.py", "a", encoding="utf-8") as f:
    f.write(content)

