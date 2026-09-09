"""Centralized UI tokens, layout constants, color schemes, and style dictionaries."""

# App-wide layout metrics
MAX_CONTENT_WIDTH = "1240px"
PAGE_PADDING_X = "1rem"
PAGE_PADDING_Y = "1.5rem"

# Font families
FONT_HEADING = "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_BODY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', monospace"

# Card and Surface Styles
CARD_STYLE = {
    "background": "var(--card-bg, #1e293b)",
    "border": "1px solid var(--border-color, #334155)",
    "border_radius": "12px",
    "padding": "1rem",
}

ELEVATED_CARD_STYLE = {
    **CARD_STYLE,
    "box_shadow": "0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -2px rgba(0, 0, 0, 0.2)",
}

METRIC_CARD_STYLE = {
    "background": "var(--metric-card-bg, rgba(30, 41, 59, 0.7))",
    "border": "1px solid var(--border-color, rgba(255, 255, 255, 0.08))",
    "border_radius": "10px",
    "padding": "0.75rem 1rem",
    "flex": "1",
    "min_width": "150px",
}

FILTER_BAR_STYLE = {
    "background": "rgba(255, 255, 255, 0.02)",
    "border": "1px solid var(--border-color, rgba(255, 255, 255, 0.08))",
    "border_radius": "10px",
    "padding": "0.85rem 1rem",
    "margin_bottom": "1rem",
}

TABLE_CONTAINER_STYLE = {
    "width": "100%",
    "overflow_x": "auto",
    "border": "1px solid var(--border-color, #334155)",
    "border_radius": "10px",
    "background": "var(--card-bg, #1e293b)",
}


def fdr_badge_style(difficulty: int, is_blank: bool = False) -> dict:
    """Returns CSS dictionary for an FDR badge."""
    base = {
        "display": "inline-block",
        "text_align": "center",
        "padding": "0.25rem 0.5rem",
        "border_radius": "6px",
        "font_size": "0.75rem",
        "font_weight": "600",
        "white_space": "nowrap",
        "min_width": "70px",
    }
    if is_blank:
        return {**base, "background": "rgba(15,23,42,0.5)", "color": "#64748b", "font_style": "italic"}

    palette = {
        1: {"background": "rgba(34,197,94,0.22)", "color": "#4ade80"},
        2: {"background": "rgba(34,197,94,0.22)", "color": "#4ade80"},
        3: {"background": "rgba(100,116,139,0.16)", "color": "#cbd5e1"},
        4: {"background": "rgba(249,115,22,0.24)", "color": "#fb923c", "font_weight": "700"},
        5: {"background": "rgba(239,68,68,0.28)", "color": "#f87171", "font_weight": "800"},
    }
    return {**base, **palette.get(difficulty, palette[5])}

