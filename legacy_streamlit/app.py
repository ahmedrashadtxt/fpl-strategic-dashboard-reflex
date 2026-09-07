import os
import subprocess
import sys

import streamlit as st
import streamlit.components.v1 as components
from streamlit.runtime.scriptrunner import get_script_run_ctx

from data import (
    ensure_database_ready,
    get_connection,
    get_global_gameweek_info,
    get_summary_stats,
    get_teams_fdr_map,
)
from tabs import (
    render_audit_journal_tab,
    render_defensive_stats_tab,
    render_expected_stats_tab,
    render_fixture_ticker_tab,
    render_rolling_form_tab,
    render_squad_analyzer_tab,
    render_transfer_analyzer_tab,
    render_transfer_market_tab,
)
from theme import (
    apply_theme,
    render_optimizer_status,
    render_skeleton_cards,
)

if get_script_run_ctx() is None:
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", __file__]))

st.set_page_config(
    page_title="FPL Optimizer",
    page_icon="assets/fplo.png",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Theme State ───────────────────────────────────────────────────────────────
if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "dark"

is_dark = st.session_state["theme_mode"] == "dark"
apply_theme(is_dark=is_dark)

# ── Google Analytics 4 ────────────────────────────────────────────────────────
GA_MEASUREMENT_ID = st.secrets.get(
    "GA_MEASUREMENT_ID", os.getenv("GA_MEASUREMENT_ID", "")
)
if GA_MEASUREMENT_ID:
    ga_tracking_code = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{GA_MEASUREMENT_ID}', {{
          'send_page_view': true,
          'page_location': document.referrer || window.location.href,
          'page_title': 'FPL Strategic Dashboard',
          'cookie_flags': 'SameSite=None;Secure'
      }});
    </script>
    """
    components.html(
        f"<div style='display:none;'>{ga_tracking_code}</div>",
        height=0,
        width=0,
    )

# ── Data & Connection Initialization ──────────────────────────────────────────
ensure_database_ready()
conn = get_connection()
events_df, current_gw, gw_name = get_global_gameweek_info(conn)
summary_df = get_summary_stats(conn)
teams_fdr_map = get_teams_fdr_map(conn, current_gw)

# ── Robust Team ID Sync from Query Parameters ─────────────────────────────────
url_param_team = str(st.query_params.get("team", "") or "").strip()
if url_param_team:
    st.session_state["manager_id"] = url_param_team
elif "manager_id" not in st.session_state:
    st.session_state["manager_id"] = ""


# ── FPL ID Form Component ─────────────────────────────────────────────────────
def _render_id_modal_body():
    st.markdown(
        """
        <style>
        div[data-testid="stDialog"] div[data-testid="stForm"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row-reverse !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.form("fpl_id_dialog_form", border=False):
        new_id = st.text_input(
            "FPL Team ID",
            value=st.session_state.get("manager_id", ""),
            placeholder="e.g. 7716321",
        )

        st.markdown(
            """
            <div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px 12px; margin: 10px 0 16px 0; font-size: 0.8rem; color: #94a3b8; line-height: 1.5;">
                <strong style="color: #f8fafc;">💡 How to find your Team ID:</strong><br>
                1. Log into <span style="color: #60a5fa;">fantasy.premierleague.com</span> and click the <strong>Points</strong> or <strong>Pick Team</strong> tab.<br>
                2. Check the URL in your browser's address bar:<br>
                <div style="margin-top: 4px; padding: 4px 8px; background: rgba(0,0,0,0.4); border-radius: 4px; word-break: break-all; font-family: monospace;">
                    https://fantasy.premierleague.com/entry/<span style="color: #4ade80; font-weight: 800;">7716321</span>/event/2
                </div>
                👉 The number right after <code>/entry/</code> is your Team ID.
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_save, col_cancel = st.columns(2)
        with col_save:
            save_btn = st.form_submit_button("Save", type="primary", use_container_width=True)
        with col_cancel:
            cancel_btn = st.form_submit_button("Cancel", use_container_width=True)

    if cancel_btn:
        st.rerun()

    if save_btn:
        cleaned_id = new_id.strip()
        if cleaned_id:
            st.session_state["manager_id"] = cleaned_id
            st.query_params["team"] = cleaned_id
        else:
            st.session_state["manager_id"] = ""
            st.query_params.pop("team", None)
        st.rerun()


# ── Top-Level Dialog Functions ────────────────────────────────────────────────
@st.dialog("Enter FPL Team ID")
def show_enter_id_dialog():
    _render_id_modal_body()


@st.dialog("Change FPL ID")
def show_change_id_dialog():
    _render_id_modal_body()


# ── First-Time Visitor Prompt (Fires Once If No ID Exists) ────────────────────
if "prompted_for_id" not in st.session_state:
    st.session_state["prompted_for_id"] = True
    if not st.session_state.get("manager_id"):
        show_enter_id_dialog()

# ── Header & Action Bar ───────────────────────────────────────────────────────
col_brand, col_search, col_theme = st.columns([5.2, 2.3, 0.5], vertical_alignment="center")

with col_brand:
    badge_html = (
        f'<span class="gw-badge live">● {gw_name.upper()}</span>'
        if "(Live)" in gw_name
        else f'<span class="gw-badge">NEXT · {gw_name}</span>'
    )
    st.markdown(
        f"""
        <div class="top-nav-brand">
            <span class="top-nav-title">FPL Optimizer</span>
            {badge_html}
        </div>
        <div class="top-nav-sub">Strategic analytics & squad optimizer</div>
        """,
        unsafe_allow_html=True,
    )

with col_search:
    curr_id = st.session_state.get("manager_id", "").strip()
    mgr_name = st.session_state.get("manager_name", "")
    display_title = mgr_name or "My Team"

    badge_label = f"👤 {display_title} · #{curr_id} ✏️" if curr_id else "➕ Enter FPL ID"

    st.markdown(
        """
        <style>
        div[data-testid="column"]:has(button[key="manager_badge_btn"]) button {
            border-radius: 999px !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            height: 40px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            padding: 0 1rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.button(badge_label, key="manager_badge_btn", use_container_width=True, help="Click to change FPL ID"):
        if curr_id:
            show_change_id_dialog()
        else:
            show_enter_id_dialog()

with col_theme:
    st.markdown('<span class="theme-toggle-marker"></span>', unsafe_allow_html=True)
    theme_icon = "🌞" if is_dark else "🌙"
    if st.button(theme_icon, key="theme_toggle_btn", help="Toggle Theme"):
        st.session_state["theme_mode"] = "light" if is_dark else "dark"
        st.rerun()

# ── Main Sticky Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "Squad Analyzer",
        "Transfer Solver",
        "Expected Stats",
        "Defensive Contributions",
        "Rolling Form",
        "Fixture Ticker",
        "Transfer Market",
        "🤖 Journey & Social",
    ]
)

with tab1:
    render_squad_analyzer_tab(conn, events_df, current_gw)
with tab2:
    render_transfer_analyzer_tab(conn, events_df, current_gw)
with tab3:
    render_expected_stats_tab(conn, current_gw)
with tab4:
    render_defensive_stats_tab(conn, current_gw)
with tab5:
    render_rolling_form_tab(conn, current_gw, teams_fdr_map)
with tab6:
    render_fixture_ticker_tab(conn, current_gw)
with tab7:
    render_transfer_market_tab(conn, current_gw)
with tab8:
    render_audit_journal_tab(conn, events_df, current_gw)