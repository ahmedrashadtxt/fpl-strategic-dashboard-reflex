"""Centralized UI tokens, layout constants, color schemes, and style dictionaries."""

# App-wide layout metrics
MAX_CONTENT_WIDTH = "1240px"
PAGE_PADDING_X = "1rem"
PAGE_PADDING_Y = "1.5rem"

# Font families
FONT_HEADING = "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_BODY = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', monospace"

# Apple HIG Semantic Color Tokens
# Value direction: strictly for positive/negative value deltas, rating quality
COLOR_POSITIVE = "var(--color-positive, #22c55e)"
COLOR_POSITIVE_SUBTLE = "var(--color-positive-subtle, rgba(34, 197, 94, 0.15))"
COLOR_NEGATIVE = "var(--color-negative, #ef4444)"
COLOR_NEGATIVE_SUBTLE = "var(--color-negative-subtle, rgba(239, 68, 68, 0.15))"

# Interactive selection: toggles-on, active radio buttons, active tab indicators, view toggles
COLOR_INTERACTIVE = "var(--color-interactive, #38bdf8)"
COLOR_INTERACTIVE_SUBTLE = "var(--color-interactive-subtle, rgba(56, 189, 248, 0.15))"
COLOR_INTERACTIVE_SCHEME = "blue"  # Reflex color_scheme prop for interactive controls

# Accent Warning / Special Callouts: reserved for Super Team star
COLOR_ACCENT_WARNING = "var(--color-accent-warning, #f59e0b)"
COLOR_ACCENT_WARNING_SUBTLE = "var(--color-accent-warning-subtle, rgba(245, 158, 11, 0.15))"

# Surface Elevation Hierarchy (Apple HIG clarity & deference)
SURFACE_0 = "var(--surface-0, #0a0a0a)"
SURFACE_1 = "var(--surface-1, rgba(255, 255, 255, 0.035))"
BORDER_LEVEL_1 = "var(--border-level-1, rgba(255, 255, 255, 0.05))"
BORDER_ACTIONABLE = "var(--border-actionable, rgba(255, 255, 255, 0.16))"

# Elevated Overlay Tokens (Apple HIG Depth: Popovers, Modals, Dropdowns)
SURFACE_OVERLAY = "var(--surface-overlay, rgba(18, 18, 22, 0.90))"
BORDER_OVERLAY = "var(--border-overlay, rgba(255, 255, 255, 0.12))"
SHADOW_ELEVATED = "var(--shadow-elevated, 0 16px 36px -4px rgba(0, 0, 0, 0.55), 0 6px 12px -2px rgba(0, 0, 0, 0.3))"
SHADOW_MODAL = "var(--shadow-modal, 0 24px 48px -8px rgba(0, 0, 0, 0.65), 0 8px 16px -4px rgba(0, 0, 0, 0.4))"
SHADOW_DROPDOWN = "var(--shadow-dropdown, 0 14px 30px -4px rgba(0, 0, 0, 0.5), 0 4px 10px -2px rgba(0, 0, 0, 0.25))"
SHADOW_TOOLTIP = "var(--shadow-tooltip, 0 10px 24px -2px rgba(0, 0, 0, 0.5), 0 2px 6px rgba(0, 0, 0, 0.3))"

# Card and Surface Styles (Level 1: filled surface, subtle low-opacity border)
CARD_STYLE = {
    "background": "var(--surface-1, rgba(255, 255, 255, 0.035))",
    "border": "1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
    "border_radius": "12px",
    "padding": "1rem",
}

ELEVATED_CARD_STYLE = {
    **CARD_STYLE,
    "box_shadow": "0 2px 6px rgba(0, 0, 0, 0.25)",
}

METRIC_CARD_STYLE = {
    "background": "var(--surface-1, rgba(255, 255, 255, 0.035))",
    "border": "1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
    "border_radius": "10px",
    "padding": "0.75rem 1rem",
    "flex": "1",
    "min_width": "0",
}

FILTER_BAR_STYLE = {
    "background": "var(--surface-1, rgba(255, 255, 255, 0.035))",
    "border": "1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
    "border_radius": "10px",
    "padding": "0.85rem 1rem",
    "margin_bottom": "1rem",
}

TABLE_CONTAINER_STYLE = {
    "width": "100%",
    "overflow_x": "auto",
    "border": "1px solid var(--border-level-1, rgba(255, 255, 255, 0.05))",
    "border_radius": "10px",
    "background": "var(--surface-1, rgba(255, 255, 255, 0.02))",
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

