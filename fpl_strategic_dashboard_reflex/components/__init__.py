"""Component exports for the Reflex shell."""
"""Components package for FPL Strategic Dashboard.
Pure presentation UI functions returning rx.Component.
Stateless and agnostic of backend database/logic.
"""

from .header import header
from .global_stats_panel import global_stats_panel
from .id_dialog import id_dialog
from .metric_card import metric_card
from .player_card import player_highlight_card
from .pitch import pitch_view, squad_list_view
from .filters import search_input, filter_select, filter_bar
from .data_table import data_table
from .utils import concat
from .loading import loading_view
from .motion import (
    MotionConfig,
    MotionDiv,
    MotionSpan,
    MotionLi,
    MotionCircle,
    AnimatePresence,
    motion_tab_content,
    motion_card,
    motion_fade_in,
    motion_slide_up,
    motion_scale_in,
    directional_slide,
    rating_ring,
)
from .count_up import CountUp, count_up
from .tour import tour_driver, tour_button
from .tour_config import TOUR_STEPS_BY_TAB

__all__ = [
    "header",
    "global_stats_panel",
    "id_dialog",
    "metric_card",
    "player_highlight_card",
    "pitch_view",
    "squad_list_view",
    "search_input",
    "filter_select",
    "filter_bar",
    "data_table",
    "concat",
    "loading_view",
    "MotionConfig",
    "MotionDiv",
    "MotionSpan",
    "MotionLi",
    "MotionCircle",
    "AnimatePresence",
    "motion_tab_content",
    "motion_card",
    "motion_fade_in",
    "motion_slide_up",
    "motion_scale_in",
    "directional_slide",
    "rating_ring",
    "CountUp",
    "count_up",
    "tour_driver",
    "tour_button",
    "TOUR_STEPS_BY_TAB",
]

