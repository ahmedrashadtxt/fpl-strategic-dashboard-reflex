import html
import streamlit as st

SILHOUETTE_BASE64 = (
    "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmci"
    "IHZpZXdCb3g9IjAgMCA0NCA0NCIgZmlsbD0ibm9uZSI+PHJlY3Qgd2lkdGg9IjQ0IiBoZWlnaHQ9"
    "IjQ0IiByeD0iMjIiIGZpbGw9IiMxZTI5M2IiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjE2IiByPSI3"
    "LjUiIGZpbGw9IiM2NDc0OGIiLz48cGF0aCBkPSJNOSAzOWMwLTcuMTggNS44Mi0xMyAxMy0xM3Mx"
    "MyA1LjgyIDEzIDEzIiBmaWxsPSIjNjQ3NDhiIi8+PC9zdmc+"
)


def get_theme_css(is_dark: bool = True) -> str:
    if is_dark:
        bg_app = "#0a0a0a"
        bg_card = "#141414"
        bg_list_card = "#141414"
        border_color = "#222222"
        input_border = "#2e2e2e"
        input_bg = "#141414"
        text_main = "#ffffff"
        text_sub = "#94a3b8"
        text_meta = "#64748b"
        placeholder_color = "#64748b"
        tag_gray_bg = "rgba(255, 255, 255, 0.06)"
        tag_gray_txt = "#94a3b8"
        tag_gray_border = "#2a2a2a"
        shadow_opacity = "0.35"
        button_bg = "#141414"
        button_txt = "#ffffff"
        button_border = "#2e2e2e"
        toggle_track_off = "#334155"
        toggle_border_off = "#475569"

        tag_blue_txt = "#9BBEED"
        tag_green_txt = "#4ade80"
        tag_red_txt = "#f87171"
        tag_yellow_txt = "#facc15"

    else:
        bg_app = "#f8fafc"
        bg_card = "#ffffff"
        bg_list_card = "#ffffff"
        border_color = "#e2e8f0"
        input_border = "#cbd5e1"
        input_bg = "#ffffff"
        text_main = "#0f172a"
        text_sub = "#475569"
        text_meta = "#64748b"
        placeholder_color = "#94a3b8"
        tag_gray_bg = "#f1f5f9"
        tag_gray_txt = "#334155"
        tag_gray_border = "#cbd5e1"
        shadow_opacity = "0.05"
        button_bg = "#ffffff"
        button_txt = "#0f172a"
        button_border = "#cbd5e1"
        toggle_track_off = "#cbd5e1"
        toggle_border_off = "#94a3b8"

        tag_blue_txt = "#1e40af"
        tag_green_txt = "#15803d"
        tag_red_txt = "#b91c1c"
        tag_yellow_txt = "#a16207"

    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800;900&family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
    color: {text_main} !important;
}}

.stApp {{
    background: {bg_app} !important;
    color: {text_main} !important;
}}

{"" if is_dark else f"""
/* ── LIGHT MODE: Override Streamlit's baked-in dark CSS variables ── */
/* config.toml forces base=dark; these rules override every widget that
   resolves var(--text-color) or var(--background-color) to dark values */
.stApp, .stApp * {{
    --text-color: {text_main} !important;
    --background-color: {bg_app} !important;
    --secondary-background-color: {bg_card} !important;
}}

/* Force all block/markdown containers light */
.stApp [data-testid="stVerticalBlock"],
.stApp [data-testid="stHorizontalBlock"],
.stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stElementContainer"],
.stApp [data-testid="element-container"],
.stApp [data-testid="stMain"],
.stApp [data-testid="stMainBlockContainer"] {{
    background: transparent !important;
    color: {text_main} !important;
}}

/* Markdown text */
.stApp [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stMarkdownContainer"] span,
.stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stMarkdownContainer"] td,
.stApp [data-testid="stMarkdownContainer"] th {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

/* Tab button text: was white-on-white because var(--text-color) = #f5f5f5 */
.stApp [data-baseweb="tab-list"] button p,
.stApp [data-baseweb="tab-list"] button span,
.stApp [data-testid="stTabs"] button p,
.stApp [data-testid="stTabs"] button span {{
    -webkit-text-fill-color: #475569 !important;
}}

/* Multiselect/select dropdown backgrounds */
.stApp [data-baseweb="select"] > div,
.stApp [data-baseweb="select"] > div > div,
.stApp div[data-baseweb="popover"] [role="listbox"],
.stApp ul[role="listbox"] {{
    background-color: {bg_card} !important;
    border-color: {input_border} !important;
}}

/* Select option text */
.stApp [data-baseweb="select"] [class*="ValueContainer"] *,
.stApp [data-baseweb="select"] [class*="singleValue"],
.stApp [data-baseweb="select"] [class*="placeholder"],
.stApp [data-baseweb="select"] input,
.stApp [data-baseweb="menu"] [role="option"],
.stApp ul[role="listbox"] li {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    background-color: transparent !important;
}}

/* Multiselect tag pills */
.stApp [data-testid="stMultiSelect"] [data-baseweb="tag"] {{
    background-color: {tag_gray_bg} !important;
    border: 1px solid {tag_gray_border} !important;
}}
.stApp [data-testid="stMultiSelect"] [data-baseweb="tag"] span {{
    color: {tag_gray_txt} !important;
    -webkit-text-fill-color: {tag_gray_txt} !important;
}}

/* Selectbox/number_input backgrounds */
.stApp [data-testid="stSelectbox"] > div > div,
.stApp [data-testid="stNumberInput"] > div > div {{
    background-color: {input_bg} !important;
    border-color: {input_border} !important;
    color: {text_main} !important;
}}

/* Number input text */
.stApp [data-testid="stNumberInput"] input {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    background: transparent !important;
}}

/* St.info / st.success / st.warning / st.error banners */
.stApp [data-testid="stAlert"] {{
    background-color: {bg_card} !important;
    border-color: {input_border} !important;
}}
.stApp [data-testid="stAlert"] p,
.stApp [data-testid="stAlert"] span {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

/* Dataframe/table */
.stApp [data-testid="stDataFrame"] {{
    background-color: {bg_card} !important;
}}

/* Slider track and thumb */
.stApp [data-baseweb="slider"] [data-testid="stThumbValue"],
.stApp [data-baseweb="slider"] p {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

/* Caption text */
.stApp [data-testid="stCaptionContainer"] p {{
    color: {text_meta} !important;
    -webkit-text-fill-color: {text_meta} !important;
}}
"""}

/* ── POPOVER BASE STYLING ── */
.stApp div[data-testid="stPopoverBody"],
.stApp [data-baseweb="popover"] > div {{
    background-color: {bg_card} !important;
    border: 1px solid {input_border} !important;
    color: {text_main} !important;
    min-width: 420px !important;
    max-width: 480px !important;
    border-radius: 12px !important;
    box-shadow: 0 12px 32px rgba(0, 0, 0, {shadow_opacity}) !important;
}}
.stApp div[data-testid="stPopoverBody"] *,
.stApp [data-baseweb="popover"] > div * {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

/* ── MODERN GUIDE POPOVER COMPONENT ── */
.modern-guide-container {{
    display: flex !important;
    flex-direction: column !important;
    gap: 0.75rem !important;
    padding: 0.2rem 0 !important;
}}
.guide-top-banner {{
    padding-bottom: 0.65rem !important;
    border-bottom: 1px solid {border_color} !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-eyebrow {{
    font-size: 0.65rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #38bdf8 !important;
    -webkit-text-fill-color: #38bdf8 !important;
    margin-bottom: 0.2rem !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-main-title {{
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    line-height: 1.25 !important;
    letter-spacing: -0.01em !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-subtitle {{
    font-size: 0.78rem !important;
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    line-height: 1.35 !important;
    margin-top: 0.25rem !important;
}}
.guide-items-list {{
    display: flex !important;
    flex-direction: column !important;
    gap: 0.5rem !important;
}}
.guide-item-card {{
    background: {bg_list_card} !important;
    border: 1px solid {border_color} !important;
    border-radius: 8px !important;
    padding: 0.6rem 0.75rem !important;
    transition: all 0.15s ease !important;
}}
.guide-item-header {{
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
    margin-bottom: 0.3rem !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-item-badge {{
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    padding: 0.15rem 0.45rem !important;
    border-radius: 4px !important;
    letter-spacing: 0.02em !important;
    white-space: nowrap !important;
    -webkit-text-fill-color: currentColor !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-item-title {{
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-item-desc {{
    font-size: 0.75rem !important;
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    line-height: 1.45 !important;
}}
.guide-tip-box {{
    background: rgba(245, 158, 11, 0.08) !important;
    border: 1px solid rgba(245, 158, 11, 0.25) !important;
    border-left: 3px solid #f59e0b !important;
    border-radius: 8px !important;
    padding: 0.6rem 0.75rem !important;
    margin-top: 0.15rem !important;
}}
.guide-tip-header {{
    display: flex !important;
    align-items: center !important;
    gap: 0.4rem !important;
    margin-bottom: 0.2rem !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-tip-title {{
    font-size: 0.68rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em !important;
    color: #f59e0b !important;
    -webkit-text-fill-color: #f59e0b !important;
}}
.stApp div[data-testid="stPopoverBody"] .guide-tip-desc {{
    font-size: 0.74rem !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    line-height: 1.4 !important;
}}

#MainMenu, footer, header[data-testid="stHeader"] {{
    display: none !important;
    visibility: hidden;
    height: 0;
}}

[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {{
    display: none !important;
}}

.block-container {{
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1240px !important;
    margin: 0 auto !important;
}}

/* ── TYPOGRAPHY OVERRIDES ── */
h1, h2, h3, h4, h5, h6, .stSubheader, [data-testid="stHeading"] * {{
    font-family: 'Outfit', sans-serif !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

.stApp label,
.stApp label p,
.stApp label span,
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stWidgetLabel"] span {{
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}}

/* Radio options text */
.stApp [data-testid="stRadio"] label,
.stApp [data-testid="stRadio"] label p,
.stApp [data-testid="stRadio"] label span,
.stApp [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
}}

/* Toggles & Checkboxes */
.stApp [data-testid="stToggle"] label p,
.stApp [data-testid="stToggle"] label span,
.stApp [data-testid="stToggle"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stCheckbox"] label p,
.stApp [data-testid="stCheckbox"] label span {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}}

.stApp div[data-testid="stToggle"] label > div:first-of-type {{
    background-color: {toggle_track_off} !important;
    border: 1px solid {toggle_border_off} !important;
}}

.stApp div[data-baseweb="slider"] p {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    font-weight: 600 !important;
}}

/* ── COMPACT SINGLE-ROW METRIC CARDS ── */
.stApp [data-testid="stMetric"] {{
    background: {bg_card} !important;
    border: 1px solid {border_color} !important;
    border-radius: 8px !important;
    padding: 0.45rem 0.65rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
}}

.stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stMetricLabel"] *,
.stApp [data-testid="stMetricLabel"] p,
.stApp [data-testid="stMetricLabel"] span {{
    font-family: 'Outfit', sans-serif !important;
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    margin-bottom: 2px !important;
}}

.stApp [data-testid="stMetricValue"], 
.stApp [data-testid="stMetricValue"] > div,
.stApp [data-testid="stMetricValue"] *,
.stApp [data-testid="stMetricValue"] p,
.stApp [data-testid="stMetricValue"] span {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    font-weight: 800 !important;
    font-size: 1.05rem !important;
    line-height: 1.2 !important;
}}

/* ── TOP ACTION BAR ── */
.top-nav-brand {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}}

.top-nav-title {{
    font-family: 'Outfit', sans-serif !important;
    font-size: 1.85rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    line-height: 1.1 !important;
}}

.top-nav-sub {{
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    color: {text_sub};
    -webkit-text-fill-color: {text_sub};
    font-weight: 500;
    margin-top: 2px;
}}

div[data-testid="stHorizontalBlock"] {{
    align-items: flex-start !important;
}}

.block-container > div:first-child > div:first-child div[data-testid="stHorizontalBlock"]:first-of-type {{
    align-items: center !important;
    gap: 1rem !important;
}}

/* ── THEME BUTTON EXCLUSIVE STYLING ── */
div[data-testid="column"] div[data-testid="stButton"] button {{
    background-color: {bg_card} !important;
    color: {text_main} !important;
    border: 1px solid {button_border} !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    border-radius: 8px !important;
    height: 40px !important;
    width: 40px !important;
    padding: 0 !important;
    margin: 0 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: all 0.2s ease-in-out !important;
}}

div[data-testid="column"] div[data-testid="stButton"] button:hover {{
    border-color: #2563eb !important;
    transform: translateY(-1px);
}}

/* ── ALL OTHER BUTTONS ── */
.stApp .stButton > button:not([aria-label="Toggle Theme"]) {{
    background-color: {button_bg} !important;
    color: {button_txt} !important;
    border: 1px solid {button_border} !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    background-image: none !important;
}}

.stApp .stButton > button:not([aria-label="Toggle Theme"]) * {{
    color: {button_txt} !important;
    -webkit-text-fill-color: {button_txt} !important;
    display: inline-block !important;
    visibility: visible !important;
}}

.stApp div[data-testid="stPopover"] > button {{
    background-color: {bg_card} !important;
    color: {text_main} !important;
    border: 1px solid {input_border} !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    padding: 0.35rem 0.75rem !important;
    background-image: none !important;
}}

.stApp div[data-testid="stPopover"] > button * {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    display: inline-block !important;
    visibility: visible !important;
}}

/* ── COMPACT STICKY TABS BAR ── */
.stApp [data-baseweb="tab-list"],
.stApp [data-testid="stTabs"] [role="tablist"] {{
    position: sticky !important;
    top: 0px !important;
    z-index: 990 !important;
    background-color: {bg_app} !important;
    border-bottom: 1px solid {border_color} !important;
    padding-top: 0.35rem !important;
    padding-bottom: 0.35rem !important;
    margin-bottom: 1rem !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, {shadow_opacity}) !important;
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    scrollbar-width: none !important;
    gap: 8px !important;
}}

.stApp [data-baseweb="tab-list"] button,
.stApp [data-testid="stTabs"] button {{
    padding: 0.35rem 0.65rem !important;
}}

.stApp [data-baseweb="tab-list"] button[aria-selected="false"] *,
.stApp [data-testid="stTabs"] button[aria-selected="false"] * {{
    color: #64748b !important;
    -webkit-text-fill-color: #64748b !important;
    font-weight: 600 !important;
    font-size: 0.80rem !important;
}}

.stApp [data-baseweb="tab-list"] button[aria-selected="false"]:hover *,
.stApp [data-testid="stTabs"] button[aria-selected="false"]:hover * {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

.stApp [data-baseweb="tab-list"] button[aria-selected="true"] *,
.stApp [data-testid="stTabs"] button[aria-selected="true"] * {{
    color: #10B981 !important;
    -webkit-text-fill-color: #10B981 !important;
    font-weight: 700 !important;
    font-size: 0.80rem !important;
}}

.stApp [data-baseweb="tab-highlight"] {{
    background-color: #10B981 !important;
    height: 2px !important;
}}

.stApp [data-baseweb="tab-border"] {{
    display: none !important;
}}

/* ── INPUT FIELDS ── */
.stApp div[data-baseweb="input"],
.stApp div[data-baseweb="base-input"],
.stApp .stTextInput > div > div {{
    background-color: {input_bg} !important;
    border: 1px solid {input_border} !important;
    border-radius: 8px !important;
}}

.stApp div[data-baseweb="input"]:focus-within,
.stApp .stTextInput > div > div:focus-within {{
    border-color: #2563eb !important;
    box-shadow: 0 0 0 1px #2563eb !important;
}}

.stApp .stTextInput input {{
    background-color: transparent !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    border: none !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}}

.stApp ::placeholder,
.stApp input::placeholder,
.stApp .stTextInput input::placeholder {{
    color: {placeholder_color} !important;
    opacity: 0.85 !important;
}}

/* ── COMPACT SECTION HEADER (REDUCED BANNER) ── */
.section-card {{
    background: transparent !important;
    border: none !important;
    border-left: 3px solid #2563eb !important;
    padding: 0.05rem 0 0.05rem 0.65rem !important;
    margin-top: 0.15rem !important;
    margin-bottom: 0.75rem !important;
}}

.section-card h3 {{
    margin: 0 !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
    letter-spacing: -0.01em !important;
    line-height: 1.2 !important;
}}

.section-card .section-desc {{
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    margin-top: 2px !important;
}}

/* ── LIST CARDS & FAIL-SAFE AVATARS ── */
.list-card {{
    background: {bg_list_card} !important;
    border: 1px solid {border_color} !important;
    border-radius: 8px !important;
    padding: 0.75rem 0.85rem !important;
    margin-bottom: 0.45rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
}}

.list-card-content {{
    display: flex !important;
    align-items: center !important;
    gap: 10px !important;
}}

.list-card-body {{
    flex: 1 !important;
    min-width: 0 !important;
}}

.card-avatar {{
    width: 40px !important;
    height: 40px !important;
    min-width: 40px !important;
    min-height: 40px !important;
    border-radius: 50% !important;
    background-size: cover, cover !important;
    background-position: top center, center !important;
    background-repeat: no-repeat, no-repeat !important;
    border: 1.5px solid {border_color} !important;
    background-color: {input_bg} !important;
    flex-shrink: 0 !important;
}}

.list-card-title {{
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

.list-card-tags {{
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 0.35rem !important;
}}

.tag {{
    display: inline-block !important;
    padding: 0.12rem 0.45rem !important;
    border-radius: 999px !important;
    font-size: 0.68rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
}}

.tag-green {{ background: rgba(34, 197, 94, 0.15) !important; color: {tag_green_txt} !important; border: 1px solid rgba(34, 197, 94, 0.3) !important; }}
.tag-red {{ background: rgba(239, 68, 68, 0.15) !important; color: {tag_red_txt} !important; border: 1px solid rgba(239, 68, 68, 0.3) !important; }}
.tag-blue {{ background: rgba(155, 190, 237, 0.25) !important; color: {tag_blue_txt} !important; border: 1px solid #9BBEED !important; }}
.tag-yellow {{ background: rgba(234, 179, 8, 0.18) !important; color: {tag_yellow_txt} !important; border: 1px solid rgba(234, 179, 8, 0.35) !important; }}
.tag-gray {{ background: {tag_gray_bg} !important; color: {tag_gray_txt} !important; border: 1px solid {tag_gray_border} !important; }}

.list-card-meta {{
    font-size: 0.76rem !important;
    color: {text_sub} !important;
    line-height: 1.4 !important;
}}

.list-card-meta span {{ color: {text_meta} !important; font-weight: 600 !important; }}

.progress-bar-wrap {{
    height: 4px !important;
    background: rgba(255, 255, 255, 0.08) !important;
    border-radius: 2px !important;
    margin-top: 6px !important;
    overflow: hidden !important;
}}

.progress-bar-fill {{
    height: 100% !important;
    background-color: #22c55e !important;
    border-radius: 2px !important;
}}

.progress-bar-fill.red {{
    background-color: #ef4444 !important;
}}

/* ── ANIMATIONS & LOADING STATES ── */
@keyframes spin {{
    0% {{ transform: rotate(0deg); }}
    100% {{ transform: rotate(360deg); }}
}}

@keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}

.optimizer-loader {{
    display: flex !important;
    align-items: center !important;
    gap: 12px !important;
    background: {bg_card} !important;
    border: 1px solid {border_color} !important;
    border-left: 3px solid #2563eb !important;
    border-radius: 8px !important;
    padding: 0.65rem 0.95rem !important;
    margin: 0.5rem 0 0.85rem 0 !important;
    box-shadow: 0 2px 6px rgba(0, 0, 0, {shadow_opacity}) !important;
}}

.optimizer-spinner {{
    width: 20px !important;
    height: 20px !important;
    border: 2px solid rgba(37, 99, 235, 0.2) !important;
    border-top: 2px solid #2563eb !important;
    border-radius: 50% !important;
    animation: spin 0.8s linear infinite !important;
    flex-shrink: 0 !important;
}}

.optimizer-loader-content {{
    display: flex !important;
    flex-direction: column !important;
    gap: 1px !important;
}}

.optimizer-loader-title {{
    font-family: 'Outfit', sans-serif !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

.optimizer-loader-subtext {{
    font-size: 0.74rem !important;
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
    font-weight: 500 !important;
}}

/* Skeleton Placeholders */
.skeleton-card {{
    pointer-events: none !important;
    user-select: none !important;
}}

.skeleton-avatar {{
    width: 40px !important;
    height: 40px !important;
    border-radius: 50% !important;
    background: linear-gradient(90deg, {input_bg} 25%, {tag_gray_bg} 50%, {input_bg} 75%) !important;
    background-size: 200% 100% !important;
    animation: shimmer 1.5s infinite !important;
    flex-shrink: 0 !important;
}}

.skeleton-line {{
    border-radius: 4px !important;
    background: linear-gradient(90deg, {input_bg} 25%, {tag_gray_bg} 50%, {input_bg} 75%) !important;
    background-size: 200% 100% !important;
    animation: shimmer 1.5s infinite !important;
}}

.skeleton-title {{
    width: 45% !important;
    height: 12px !important;
    margin-bottom: 6px !important;
}}

.skeleton-meta {{
    width: 75% !important;
    height: 10px !important;
}}

.gw-badge {{
    display: inline-block !important;
    background: rgba(37, 99, 235, 0.1) !important;
    color: #2563eb !important;
    border: 1px solid rgba(37, 99, 235, 0.3) !important;
    border-radius: 999px !important;
    padding: 0.15rem 0.55rem !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
}}

.gw-badge.live {{
    background: rgba(34, 197, 94, 0.15) !important;
    color: #4ade80 !important;
    border: 1px solid rgba(34, 197, 94, 0.4) !important;
}}

[data-testid="stExpanderDetails"] {{
    background-color: {bg_card} !important;
    color: {text_main} !important;
    border-radius: 0 0 0.5rem 0.5rem;
}}
[data-testid="stExpanderDetails"] * {{
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}

div[data-baseweb="select"] > div {{
    background-color: {input_bg} !important;
    border-color: {input_border} !important;
}}
div[data-baseweb="select"] div[class*="singleValue"] {{
    color: {text_main} !important;
}}
ul[role="listbox"] {{
    background-color: {input_bg} !important;
}}
ul[role="listbox"] li {{
    color: {text_main} !important;
}}

/* ── CHIP PILLS (theme-aware inactive state) ── */
div[class*="st-key-chip_btn_"] button {{
    border-radius: 999px !important;
    font-size: 0.76rem !important;
    font-weight: 700 !important;
    padding: 0.25rem 0.5rem !important;
    margin: 0 !important;
    min-height: 30px !important;
    height: 30px !important;
    transition: all 0.2s ease-in-out !important;
    border: 1px solid {input_border} !important;
    background: {bg_card} !important;
    color: {text_sub} !important;
    -webkit-text-fill-color: {text_sub} !important;
}}
div[class*="st-key-chip_btn_"] button:hover {{
    transform: translateY(-1px);
    border-color: rgba(250, 204, 21, 0.5) !important;
    color: {text_main} !important;
    -webkit-text-fill-color: {text_main} !important;
}}
div[class*="st-key-chip_btn_"] button[kind="primary"],
div[class*="st-key-chip_btn_"] button[data-testid="stBaseButton-primary"] {{
    background: linear-gradient(135deg, rgba(234, 179, 8, 0.28) 0%, rgba(202, 138, 4, 0.42) 100%) !important;
    border: 1.5px solid #facc15 !important;
    color: #fef08a !important;
    -webkit-text-fill-color: #fef08a !important;
    box-shadow: 0 0 16px rgba(250, 204, 21, 0.65), 0 0 4px rgba(250, 204, 21, 0.9), inset 0 0 8px rgba(250, 204, 21, 0.25) !important;
    text-shadow: 0 0 8px rgba(250, 204, 21, 0.7) !important;
}}
</style>
"""


def apply_theme(is_dark: bool = True, *args, **kwargs):
    st.markdown(get_theme_css(is_dark), unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text))


def fmt_num(value, spec: str = ".2f") -> str:
    try:
        return format(float(value), spec)
    except (ValueError, TypeError):
        return str(value)


def render_tag(label: str, tag_type: str = "gray") -> str:
    return f'<span class="tag tag-{tag_type}">{esc(label)}</span>'


def render_optimizer_status(
    title: str = "Optimizing your squad...",
    subtext: str = "Crunching transfer permutations & expected points...",
):
    loader_html = (
        f'<div class="optimizer-loader">'
        f'<div class="optimizer-spinner"></div>'
        f'<div class="optimizer-loader-content">'
        f'<div class="optimizer-loader-title">{esc(title)}</div>'
        f'<div class="optimizer-loader-subtext">{esc(subtext)}</div>'
        f'</div>'
        f'</div>'
    )
    return st.markdown(loader_html, unsafe_allow_html=True)


def render_skeleton_cards(count: int = 3):
    skeleton_cards = "".join(
        f'<div class="list-card skeleton-card">'
        f'<div class="list-card-content">'
        f'<div class="skeleton-avatar"></div>'
        f'<div class="list-card-body">'
        f'<div class="skeleton-line skeleton-title"></div>'
        f'<div class="skeleton-line skeleton-meta"></div>'
        f'</div>'
        f'</div>'
        f'</div>'
        for _ in range(count)
    )
    return st.markdown(skeleton_cards, unsafe_allow_html=True)


from typing import Optional

def render_list_card(
    title: str,
    tags: list[tuple[str, str]],
    meta: str,
    progress: Optional[float] = None,
    progress_red: bool = False,
    img_url: Optional[str] = None,
):
    tags_html = "".join(render_tag(label, t) for label, t in tags)

    if img_url:
        clean_url = esc(str(img_url))
        avatar_html = (
            f'<div class="card-avatar" style="background-image: url(\'{clean_url}\'), url(\'{SILHOUETTE_BASE64}\');"></div>'
        )
    else:
        avatar_html = (
            f'<div class="card-avatar" style="background-image: url(\'{SILHOUETTE_BASE64}\');"></div>'
        )

    progress_html = ""
    if progress is not None:
        fill_class = " red" if progress_red else ""
        progress_html = (
            f'<div class="progress-bar-wrap">'
            f'<div class="progress-bar-fill{fill_class}" style="width: {min(progress, 100):.0f}%"></div>'
            f'</div>'
        )

    card_html = (
        f'<div class="list-card">'
        f'<div class="list-card-content">'
        f'{avatar_html}'
        f'<div class="list-card-body">'
        f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">'
        f'<div class="list-card-title" style="margin-bottom: 0;">{esc(title)}</div>'
        f'<div class="list-card-tags" style="margin-bottom: 0;">{tags_html}</div>'
        f'</div>'
        f'<div class="list-card-meta">{meta}</div>'
        f'{progress_html}'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)


def section_header(title: str, description: str = ""):
    desc = f'<div class="section-desc">{esc(description)}</div>' if description else ""
    st.markdown(
        f'<div class="section-card"><h3>{esc(title)}</h3>{desc}</div>',
        unsafe_allow_html=True,
    )


def get_guide_html(title: str, subtitle: str, items: list[dict], tip: str = None) -> str:
    items_html = []
    for item in items:
        badge = item.get("badge", "")
        item_title = item.get("title", "")
        desc = item.get("desc", "")
        badge_color = item.get("color", "#38bdf8")
        
        badge_html = (
            f'<span class="guide-item-badge" style="background: {badge_color}22; color: {badge_color}; border: 1px solid {badge_color}44;">'
            f'{esc(badge)}</span>'
            if badge else ""
        )
        
        desc_html = desc if ("<" in desc and ">" in desc) else esc(desc)
        
        items_html.append(
            f'<div class="guide-item-card">'
            f'<div class="guide-item-header">'
            f'{badge_html}'
            f'<span class="guide-item-title">{esc(item_title)}</span>'
            f'</div>'
            f'<div class="guide-item-desc">{desc_html}</div>'
            f'</div>'
        )

    tip_html = ""
    if tip:
        clean_tip = tip if ("<" in tip and ">" in tip) else esc(tip)
        tip_html = (
            f'<div class="guide-tip-box">'
            f'<div class="guide-tip-header">'
            f'<span class="guide-tip-icon" style="-webkit-text-fill-color: #f59e0b !important;">&#x1F4A1;</span>'
            f'<span class="guide-tip-title">PRO STRATEGY</span>'
            f'</div>'
            f'<div class="guide-tip-desc">{clean_tip}</div>'
            f'</div>'
        )

    return (
        f'<div class="modern-guide-container">'
        f'<div class="guide-top-banner">'
        f'<div class="guide-eyebrow">STRATEGIC TOOL GUIDE</div>'
        f'<div class="guide-main-title">{esc(title)}</div>'
        f'<div class="guide-subtitle">{esc(subtitle)}</div>'
        f'</div>'
        f'<div class="guide-items-list">'
        f'{"".join(items_html)}'
        f'</div>'
        f'{tip_html}'
        f'</div>'
    )


def render_guide_popover(title: str, subtitle: str, items: list[dict], tip: str = None, key: str = None):
    """Renders a standardized modern guide popover button and structured content dialog."""
    popover_kwargs = {"help": f"Open {title} Guide"}
    if key:
        popover_kwargs["key"] = key
    with st.popover(":material/menu_book:  Guide", **popover_kwargs):
        st.markdown(get_guide_html(title, subtitle, items, tip), unsafe_allow_html=True)


def render_sortable_table(table_html: str, is_dark: bool = True, height: int = 560):
    bg_color = "#0a0a0a" if is_dark else "#f8fafc"
    text_color = "#ffffff" if is_dark else "#0f172a"

    component_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        html, body {{
          background: {bg_color};
          color: {text_color};
          font-family: 'Inter', sans-serif;
          overflow-y: hidden !important;
          overflow-x: auto;
          width: 100%;
        }}
        th {{
          cursor: pointer !important;
          user-select: none !important;
          position: relative;
          transition: background 0.15s ease;
        }}
        th:hover {{
          filter: brightness(1.25);
        }}
        th::after {{
          content: ' ';
          opacity: 0.35;
          font-size: 0.72rem;
          margin-left: 4px;
          display: inline-block;
        }}
        th.sort-asc::after {{
          content: ' ';
          opacity: 1;
          color: #2563eb;
        }}
        th.sort-desc::after {{
          content: ' ';
          opacity: 1;
          color: #2563eb;
        }}
      </style>
    </head>
    <body>
      {table_html}

      <script>
        document.addEventListener('DOMContentLoaded', () => {{
          const table = document.querySelector('table');
          if (!table) return;
          const headers = table.querySelectorAll('th');

          headers.forEach((header, index) => {{
            header.addEventListener('click', () => {{
              const isAsc = header.classList.contains('sort-asc');
              headers.forEach(h => h.classList.remove('sort-asc', 'sort-desc'));

              header.classList.toggle('sort-asc', !isAsc);
              header.classList.toggle('sort-desc', isAsc);

              sortTable(table, index, !isAsc);
            }});
          }});

          function extractValue(text) {{
            if (!text) return '';
            let clean = text.replace(/,/g, '').trim();

            const fdrMatch = clean.match(/^\\[(\\d+)\\]/);
            if (fdrMatch) return parseFloat(fdrMatch[1]);

            clean = clean.replace(/[£$%]/g, '').replace(/\\b(pts|xP|m|Mins|Apps)\\b/gi, '').trim();
            const numMatch = clean.match(/^[-+]?\\d+(\\.\\d+)?/);
            if (numMatch) {{
              return parseFloat(numMatch[0]);
            }}
            return clean.toLowerCase();
          }}

          function sortTable(tbl, colIdx, asc) {{
            const tbody = tbl.querySelector('tbody');
            if (!tbody) return;
            const rows = Array.from(tbody.querySelectorAll('tr'));

            rows.sort((rowA, rowB) => {{
              const valA = extractValue(rowA.children[colIdx]?.innerText);
              const valB = extractValue(rowB.children[colIdx]?.innerText);

              const isNumA = typeof valA === 'number';
              const isNumB = typeof valB === 'number';

              if (isNumA && isNumB) {{
                return asc ? valA - valB : valB - valA;
              }}
              return asc ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
            }});

            rows.forEach(r => tbody.appendChild(r));
          }}
        }});
      </script>
    </body>
    </html>
    """
    st.iframe(component_code, height=height)

