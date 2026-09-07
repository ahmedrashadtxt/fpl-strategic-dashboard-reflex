# FPL Optimizer: Reflex Migration Plan

## Overview
This document outlines the implementation plan for migrating the FPL Strategic Dashboard from Streamlit to a Reflex web app. 
Reflex uses a React frontend and Python backend, meaning all state is managed via `rx.State` classes and all UI components are built using `rx` components.

The backend logic (`data.py`, `fetch_data.py`, `betting_engine.py`, `audit_db.py`) has been decoupled into the `backend/` directory to facilitate cleaner imports from our Reflex state classes.

## State Management Architecture
In Streamlit, state is managed via `st.session_state` and the script re-runs from top to bottom on every interaction. In Reflex, state is preserved in the backend `rx.State` classes, and we explicitly define event handlers to mutate this state and trigger UI updates.

We will create a global `AppState(rx.State)` to hold cross-cutting state like the user's `manager_id`, `theme_mode`, and the global `current_gw`. Then, we will create sub-states for each tab.

### Global AppState
**State Variables:**
- `manager_id: str`
- `manager_name: str`
- `theme_mode: str = "dark"`
- `current_gw: int`
- `gw_name: str`
- `is_data_loaded: bool = False`

**Event Handlers:**
- `load_initial_data()`: Connects to `fpl.db`, populates `current_gw`, `gw_name`.
- `set_manager_id(new_id: str)`: Updates manager ID and triggers fetches for squad data.
- `toggle_theme()`: Switches `theme_mode`.

---

## Tab-by-Tab Migration Plan

### 1. Squad Analyzer (`tabs/squad_analyzer.py`)
**State Variables:**
- `squad_players: list[dict]`: The current team's players with their enriched stats.
- `eval_gw: int`: The gameweek currently being evaluated (defaults to `current_gw`).
- `chip_active: str`: Which chip is being simulated (None, Wildcard, Bench Boost, etc.).
- `squad_cost: float`
- `bank: float`

**Event Handlers:**
- `fetch_manager_squad()`: Uses `backend/data.py` to get squad IDs and populate `squad_players`.
- `update_eval_gw(gw: int)`: Changes the target gameweek and recalculates projected points (xP).
- `simulate_chip(chip: str)`: Applies chip logic (e.g., doubling captain points for TC) and re-evaluates the squad.

### 2. Transfer Solver (`tabs/transfer_analyzer.py`)
**State Variables:**
- `available_transfers: int`
- `bank_balance: float`
- `proposed_transfers_in: list[dict]`
- `proposed_transfers_out: list[dict]`
- `target_player_ids: list[int]`
- `forced_out_player_ids: list[int]`

**Event Handlers:**
- `solve_transfers()`: Calls the optimizer engine to find the best transfers given the budget and constraints.
- `add_target_player(player_id: int)`: Adds a player to the must-buy list.
- `force_out_player(player_id: int)`: Adds a player to the must-sell list.
- `clear_constraints()`: Resets target and forced out lists.

### 3. Expected Stats (`tabs/expected_stats.py`)
**State Variables:**
- `expected_stats_data: list[dict]`: Table of players with xG, xA, xGI.
- `position_filter: str`
- `team_filter: str`

**Event Handlers:**
- `load_expected_stats()`: Queries `player_match_history` to aggregate xG data.
- `apply_filters(pos: str, team: str)`: Updates the table view.

### 4. Defensive Contributions (`tabs/defensive_stats.py`)
**State Variables:**
- `defensive_stats_data: list[dict]`: Table of teams/players with xGC, saves, clearances.
- `sort_by: str`: Column to sort by.

**Event Handlers:**
- `load_defensive_stats()`: Loads defensive metrics from the database.
- `sort_data(column: str)`: Sorts the defensive stats table.

### 5. Rolling Form (`tabs/rolling_form.py`)
**State Variables:**
- `rolling_window: int = 5`: Number of gameweeks to look back.
- `rolling_form_data: list[dict]`

**Event Handlers:**
- `update_rolling_window(window: int)`: Re-queries rolling stats using `get_rolling_match_stats` for the new window size.

### 6. Fixture Ticker (`tabs/fixture_ticker.py`)
**State Variables:**
- `fixture_ticker_data: list[dict]`: The FDR (Fixture Difficulty Rating) for the next 5 GWs per team.
- `search_query: str`
- `only_my_squad: bool = False`

**Event Handlers:**
- `load_fixtures()`: Queries the `fixtures` table to build the ticker.
- `update_search(query: str)`: Filters the ticker by club or player name using RapidFuzz.
- `toggle_only_my_squad(checked: bool)`: Filters to show only teams of players currently in the manager's squad.

### 7. Transfer Market (`tabs/transfer_market.py`)
**State Variables:**
- `price_changes: list[dict]`: Nightly price prediction data.
- `ownership_trends: list[dict]`: Transfers in/out data.

**Event Handlers:**
- `load_market_data()`: Calls `calculate_price_change_predictions` to get price rise/fall indicators.
- `refresh_live_prices()`: Triggers a quick sync of live prices from the FPL API.

### 8. Audit Journal (`tabs/audit_journal.py`)
**State Variables:**
- `audit_logs: list[dict]`: Historical snapshots of predictions vs actuals.
- `selected_audit_gw: int`

**Event Handlers:**
- `load_audit_logs(gw: int)`: Fetches past predictions from `audit_db.py`.
- `compare_actuals_to_predictions()`: Calculates the delta between predicted xP and actual points scored.

---
## Next Steps
1. Create `rx.State` classes mapping to the above.
2. Build Reflex UI components mapping each function (e.g., `render_fixture_ticker_tab`) to a Reflex function returning `rx.Component`.
3. Wire the components to the `State` using `on_change` or `on_click` triggers.

