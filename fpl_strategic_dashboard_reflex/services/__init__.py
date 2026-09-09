"""Services package for FPL Strategic Dashboard.
Decoupled domain logic, database operations, API integration, and mathematical engines.
Zero dependencies on Streamlit or Reflex UI types.
"""

from .cache import ttl_cache
from .db import (
    get_connection,
    ensure_database_ready,
    get_global_gameweek_info,
    get_summary_stats,
    get_teams_fdr_map,
    get_historical_player_baselines,
    get_manager_squad_ids,
    get_motw_data,
    get_fixture_for_team,
    calculate_projected_points,
    solve_optimal_xi,
    create_price_predictions_table,
    calculate_price_change_predictions,
    get_price_prediction_map,
)
from .betting import (
    load_db_market_odds,
    get_fixture_market_xg_and_movement,
    sync_fixture_odds_with_cooldown,
    fetch_upcoming_betting_odds,
)
from .squad import (
    get_player_img_url,
    fmt_num,
    SILHOUETTE_BASE64,
    enrich_squad_df,
    build_player_tooltip,
    fetch_manager_transfers,
    fetch_manager_entry,
    fetch_manager_history,
    fetch_manager_picks,
    fetch_live_gameweek_points,
    fetch_dream_team_data,
    fetch_motw_manager_data,
    solve_budget_dream_15,
    solve_unconstrained_super_15,
    find_best_chip_gw,
    get_cached_league_dream_15,
    get_cached_league_super_15,
    build_pitch_html,
)
from .transfer import (
    evaluate_league_multi_gw,
    solve_multi_gw_transfers,
    calculate_available_fts,
    prepare_xi_display,
    render_transfer_pitch_component,
)
from .simulator import (
    build_odds_map,
    run_gameweek_simulation,
    run_head_to_head_simulation,
)
from .expected import run_expected_analysis
from .defensive import run_defensive_analysis
from .rolling import run_rolling_analysis
from .fixtures import _build_ticker_rows
from .market import (
    fetch_transfer_targets_base_data,
    apply_target_market_projection,
)
from .audit import (
    load_audit_data,
    lock_audit_version,
    settle_audit_version,
    get_audit_snapshot,
    is_owner_manager,
)

__all__ = [
    "ttl_cache",
    "get_connection",
    "ensure_database_ready",
    "get_global_gameweek_info",
    "get_summary_stats",
    "get_teams_fdr_map",
    "get_historical_player_baselines",
    "get_manager_squad_ids",
    "get_motw_data",
    "get_fixture_for_team",
    "calculate_projected_points",
    "solve_optimal_xi",
    "create_price_predictions_table",
    "calculate_price_change_predictions",
    "get_price_prediction_map",
    "load_db_market_odds",
    "get_fixture_market_xg_and_movement",
    "sync_fixture_odds_with_cooldown",
    "fetch_upcoming_betting_odds",
    "get_player_img_url",
    "fmt_num",
    "SILHOUETTE_BASE64",
    "enrich_squad_df",
    "build_player_tooltip",
    "fetch_manager_transfers",
    "fetch_manager_entry",
    "fetch_manager_history",
    "fetch_manager_picks",
    "fetch_live_gameweek_points",
    "fetch_dream_team_data",
    "fetch_motw_manager_data",
    "solve_budget_dream_15",
    "solve_unconstrained_super_15",
    "find_best_chip_gw",
    "get_cached_league_dream_15",
    "get_cached_league_super_15",
    "build_pitch_html",
    "evaluate_league_multi_gw",
    "solve_multi_gw_transfers",
    "calculate_available_fts",
    "prepare_xi_display",
    "render_transfer_pitch_component",
    "build_odds_map",
    "run_gameweek_simulation",
    "run_head_to_head_simulation",
    "run_expected_analysis",
    "run_defensive_analysis",
    "run_rolling_analysis",
    "_build_ticker_rows",
    "fetch_transfer_targets_base_data",
    "apply_target_market_projection",
    "load_audit_data",
    "lock_audit_version",
    "settle_audit_version",
    "get_audit_snapshot",
    "is_owner_manager",
]

