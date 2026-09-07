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

def transfer_analyzer_page():
    return rx.box(
        rx.cond(
            TransferAnalyzerState.is_loading,
            rx.center(
                rx.vstack(
                    rx.spinner(size="3"),
                    rx.text(TransferAnalyzerState.status_message, color="gray"),
                    spacing="4",
                ),
                padding="8",
            )
        ),
        rx.cond(
            (TransferAnalyzerState.manager_id == ""),
            rx.center(
                rx.callout(
                    "👆 Click 'Enter FPL ID' in the top-right header to load your transfer analysis.",
                    icon="info",
                ),
                padding="8"
            )
        ),
        rx.cond(
            (TransferAnalyzerState.manager_id != "") & ~TransferAnalyzerState.is_loading & TransferAnalyzerState.has_data,
            rx.vstack(
                # Controls
                rx.grid(
                    rx.box(
                        rx.text("Horizon (GWs)"),
                        rx.select(["1", "2", "3", "5"], value=TransferAnalyzerState.horizon_len.to_string(), on_change=TransferAnalyzerState.set_horizon)
                    ),
                    rx.box(
                        rx.text("Free Transfers"),
                        rx.select(["0", "1", "2", "3", "4", "5"], value=TransferAnalyzerState.ft_count.to_string(), on_change=TransferAnalyzerState.set_fts)
                    ),
                    rx.box(
                        rx.text("Max Hits"),
                        rx.select(["0", "1", "2", "3", "4"], value=TransferAnalyzerState.max_hits.to_string(), on_change=TransferAnalyzerState.set_max_hits)
                    ),
                    rx.box(
                        rx.text("Pitch View"),
                        rx.checkbox("", checked=TransferAnalyzerState.pitch_view, on_change=TransferAnalyzerState.set_pitch_view)
                    ),
                    rx.box(
                        rx.text("Betting xG"),
                        rx.checkbox("", checked=TransferAnalyzerState.enable_betting, on_change=TransferAnalyzerState.set_enable_betting)
                    ),
                    columns="5",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Multi Selects
                rx.grid(
                    rx.box(
                        rx.text("🔒 Keep / 🎯 Target", weight="bold"),
                        rx.select(TransferAnalyzerState.pos_options, value=TransferAnalyzerState.selected_positive[0] if TransferAnalyzerState.selected_positive else "", on_change=lambda x: TransferAnalyzerState.set_selected_positive([x]))
                        # Note: Reflex select only supports single selection easily out of the box in this form, so we adapt it.
                    ),
                    rx.box(
                        rx.text("🔴 Sell / ⛔ Block", weight="bold"),
                        rx.select(TransferAnalyzerState.neg_options, value=TransferAnalyzerState.selected_negative[0] if TransferAnalyzerState.selected_negative else "", on_change=lambda x: TransferAnalyzerState.set_selected_negative([x]))
                    ),
                    columns="2",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                rx.divider(),
                
                # Results Metrics
                rx.grid(
                    rx.box(rx.text("Current Bank", size="1", color="gray"), rx.text(TransferAnalyzerState.bank_balance, weight="bold")),
                    rx.box(rx.text("Bank After", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["bank_after"], weight="bold")),
                    rx.box(rx.text("Old xP", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["old_xp"], weight="bold")),
                    rx.box(rx.text("New xP", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["new_xp"], weight="bold")),
                    rx.box(rx.text("Diff", size="1", color="gray"), rx.text(TransferAnalyzerState.metrics["xp_diff"], weight="bold", color="green")),
                    columns="5",
                    width="100%",
                    spacing="4",
                    margin_bottom="4"
                ),
                
                # Recommended Transfers
                rx.box(
                    rx.text("Recommended Transfers", font_weight="bold", margin_bottom="2"),
                    rx.foreach(
                        TransferAnalyzerState.swaps,
                        lambda s: rx.text(s["out"]["name"], " ➔ ", s["in"]["name"])
                    ),
                    margin_bottom="4"
                ),
                
                # Views
                rx.grid(
                    rx.box(
                        rx.text("Current Squad", weight="bold", margin_bottom="2"),
                        rx.cond(
                            TransferAnalyzerState.pitch_view,
                            rx.html(TransferAnalyzerState.base_pitch_html),
                            squad_list_view(TransferAnalyzerState.base_starters, TransferAnalyzerState.base_bench)
                        ),
                        width="100%"
                    ),
                    rx.box(
                        rx.text("Optimal Path", weight="bold", margin_bottom="2"),
                        rx.cond(
                            TransferAnalyzerState.pitch_view,
                            rx.html(TransferAnalyzerState.comp_pitch_html),
                            squad_list_view(TransferAnalyzerState.trans_starters, TransferAnalyzerState.trans_bench)
                        ),
                        width="100%"
                    ),
                    columns="2",
                    spacing="4",
                    width="100%"
                ),
                width="100%",
                spacing="4"
            )
        ),
        width="100%",
        on_mount=TransferAnalyzerState.analyze
    )
"""
with open("fpl_strategic_dashboard_reflex/pages/transfer_analyzer.py", "a", encoding="utf-8") as f:
    f.write(content)

