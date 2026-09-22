"""Visually appealing tactical loading HUD component for optimizer and analytics views."""

import reflex as rx


def loading_view(
    status_message: rx.Var | str = "Syncing squad and match center...",
    title: str = "Tactical Analytics Engine",
    badge_text: str = "OPTIMIZER ACTIVE",
) -> rx.Component:
    """Renders a high-tech tactical radar loading display with glassmorphism and pulsing orbital animations."""
    return rx.center(
        rx.box(
            # Orbital Pulse Radar
            rx.box(
                rx.box(class_name="tactical-radar-outer"),
                rx.box(class_name="tactical-radar-inner"),
                rx.box(
                    rx.icon("activity", size=18),
                    class_name="tactical-radar-core",
                ),
                class_name="tactical-radar-orb",
            ),
            # Pulse Status Badge
            rx.box(
                rx.box(class_name="tactical-pulse-dot"),
                rx.text(badge_text),
                class_name="tactical-pulse-badge",
            ),
            # Headline Title
            rx.text(
                title,
                font_family="'Outfit', sans-serif",
                font_size="1.15rem",
                font_weight="800",
                color="var(--text-main)",
                letter_spacing="-0.02em",
                margin_bottom="0.25rem",
            ),
            # Dynamic Live Status Message
            rx.text(
                status_message,
                font_size="0.84rem",
                color="var(--text-sub)",
                font_weight="500",
                text_align="center",
            ),
            # Scanning Track with sweeping gradient
            rx.box(
                rx.box(class_name="tactical-scan-bar"),
                class_name="tactical-scan-track",
            ),
            class_name="tactical-loader-wrap",
        ),
        padding_y="3rem",
        width="100%",
    )

