"""Pitch presentation component rendering the soccer pitch and bench dugout."""

import reflex as rx
from .motion import MotionDiv, MotionSpan


def pitch_view(pitch_html: rx.Var | str, title: str = "", header_text: rx.Var | str = "") -> rx.Component:
    """Renders a responsive soccer pitch board with smooth layout spring transitions."""
    return MotionDiv.create(
        rx.cond(
            header_text != "",
            rx.hstack(
                rx.text(header_text, font_family="'Outfit', sans-serif", font_weight="700", font_size="1rem"),
                width="100%",
                padding_y="0.5rem",
            ),
            rx.box(),
        ),
        rx.box(
            rx.html(pitch_html),
            width="100%",
            overflow="visible",
        ),
        width="100%",
        display="flex",
        flex_direction="column",
        align_items="center",
        layout="position",
        transition={"type": "spring", "stiffness": 380, "damping": 30},
    )


def render_player_item(p: dict, is_bench: bool = False) -> rx.Component:
    """Renders a single player list item card with hover lift, tap scale, and badge pop-in."""
    return MotionDiv.create(
        rx.hstack(
            rx.avatar(
                src=p["photo_url"],
                fallback=p["Pos"],
                size="2",
                radius="full",
            ),
            rx.vstack(
                rx.hstack(
                    rx.text(p["Player"], font_weight="700", font_size="0.9rem", color="var(--text-main)"),
                    rx.badge(p["Team"], variant="soft", color_scheme="gray", size="1"),
                    rx.badge(p["Pos"], variant="outline", color_scheme=p["Pos_Color"], size="1"),
                    rx.cond(
                        (p["Cap_Badge"] != "") & (p["Cap_Badge"] != None),
                        MotionSpan.create(
                            rx.badge(p["Cap_Badge"], color_scheme=p["Cap_Badge_Color"], size="1"),
                            initial={"scale": 0, "opacity": 0},
                            animate={"scale": 1, "opacity": 1},
                            transition={"type": "spring", "stiffness": 400, "damping": 22},
                        ),
                        rx.box(),
                    ),
                    align="center",
                    spacing="2",
                    wrap="wrap",
                ),
                rx.hstack(
                    rx.cond(
                        (p["Opponent_Display"] != "") & (p["Opponent_Display"] != None),
                        rx.text(p["Opponent_Display"], font_size="0.75rem", color="var(--text-sub)"),
                        rx.box(),
                    ),
                    rx.cond(
                        (p["Opponent_Display"] != "") & (p["Opponent_Display"] != None) & (p["FDR_Display"] != "") & (p["FDR_Display"] != None),
                        rx.text("·", font_size="0.75rem", color="var(--text-muted)"),
                        rx.box(),
                    ),
                    rx.cond(
                        (p["FDR_Display"] != "") & (p["FDR_Display"] != None),
                        rx.badge(p["FDR_Display"], variant="surface", size="1", color_scheme=p["FDR_Color"]),
                        rx.box(),
                    ),
                    rx.cond(
                        (p["Cost_Display"] != "") & (p["Cost_Display"] != None),
                        rx.hstack(
                            rx.text("·", font_size="0.75rem", color="var(--text-muted)"),
                            rx.text(p["Cost_Display"], font_size="0.75rem", color="var(--text-muted)"),
                            spacing="2",
                            align="center",
                        ),
                        rx.box(),
                    ),
                    rx.cond(
                        (p["News"] != "") & (p["News"] != None),
                        rx.hstack(
                            rx.icon("triangle-alert", size=12, color="#fb923c"),
                            rx.text(p["News"], font_size="0.75rem", color="#fb923c"),
                            spacing="1",
                            align="center",
                        ),
                        rx.box(),
                    ),
                    align="center",
                    spacing="2",
                    wrap="wrap",
                ),
                align="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.text("xP / Pts", font_size="0.65rem", color="var(--text-muted)"),
                rx.text(p["Proj_Pts_Display"], font_size="1.15rem", font_weight="800", color="#60a5fa"),
                align="end",
                spacing="0",
            ),
            padding="0.6rem 0.85rem",
            border="1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
            border_radius="8px",
            background=rx.cond(is_bench, "rgba(15, 23, 42, 0.4)", "rgba(30, 41, 59, 0.5)"),
            width="100%",
            align="center",
        ),
        width="100%",
        layout="position",
        while_hover={"y": -3, "boxShadow": "0 8px 24px rgba(0, 0, 0, 0.35)"},
        while_tap={"scale": 0.97},
        transition={"type": "spring", "stiffness": 400, "damping": 30},
    )


def squad_list_view(starters: rx.Var, bench: rx.Var, header_text: rx.Var | str = "") -> rx.Component:
    """Renders an accessible alternative list view of starters and bench with position layout glide."""
    return MotionDiv.create(
        rx.vstack(
            rx.cond(
                header_text != "",
                rx.hstack(
                    rx.text(header_text, font_family="'Outfit', sans-serif", font_weight="700", font_size="1rem"),
                    width="100%",
                    padding_y="0.5rem",
                ),
                rx.box(),
            ),
            rx.text("Starting XI", font_weight="700", font_size="0.95rem", color="var(--text-main)", margin_bottom="0.25rem"),
            rx.foreach(starters, lambda p: render_player_item(p, is_bench=False)),
            rx.text("Bench Dugout", font_weight="700", font_size="0.95rem", color="var(--text-sub)", margin_top="1rem", margin_bottom="0.25rem"),
            rx.foreach(bench, lambda p: render_player_item(p, is_bench=True)),
            width="100%",
            spacing="2",
        ),
        width="100%",
        layout="position",
        transition={"type": "spring", "stiffness": 380, "damping": 30},
    )

