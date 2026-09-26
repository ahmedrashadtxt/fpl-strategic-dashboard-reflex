"""Table column sorting utilities for FPL Optimizer dashboard."""

from typing import Any, Dict, List, Optional


EXPECTED_STATS_KEY_MAP = {
    "Player": "Player",
    "Club": "Team",
    "Pos": "Pos",
    "Price": "Price_Display",
    "Mins": "Minutes_Display",
    "Avg M/GW": "Avg_Mins_GW",
    "Pts": "Total_Points",
    "Gls": "Goals",
    "Ast": "Assists",
    "CS": "Clean_Sheets",
    "Saves": "Saves",
    "xG": "xG_Display",
    "xA": "xA_Display",
    "xGI": "xGI_Display",
    "Proj xP": "Proj_XP_Display",
    "xGI/90": "xGI_90_Display",
    "Career GI/90": "Career_GI_90_Display",
    "Career Pts/90": "Career_Pts_90_Display",
    "Career Mins": "Career_Mins_Display",
}

DEFENSIVE_STATS_KEY_MAP = {
    "Player": "Player",
    "Club": "Team",
    "Pos": "Pos",
    "Price": "Price_Display",
    "Mins": "Minutes_Display",
    "Avg M/GW": "Avg_Mins_GW",
    "Pts": "Total_Points",
    "CS": "Clean_Sheets",
    "GC": "Goals_Conceded",
    "xGC": "xGC_Display",
    "Proj Def xP": "Proj_Def_XP_Display",
    "xGC/90": "xGC_90_Display",
    "DC": "DC",
    "DC/90": "DC_90_Display",
    "CBI": "CBI",
    "R": "R",
    "T": "T",
    "Saves": "Saves",
    "Saves/90": "Saves_90_Display",
    "Career GC/90": "Career_GC_90_Display",
    "Career CS/90": "Career_CS_90_Display",
    "Career Pts/90": "Career_Pts_90_Display",
    "Career Mins": "Career_Mins_Display",
}

ROLLING_FORM_KEY_MAP = {
    "Player": "Player",
    "Club": "Team",
    "Pos": "Pos",
    "Price": "Price_Display",
    "GW": "Latest_GW",
    "Proj Form xP": "Proj_Form_XP_Display",
    "Avg Pts": "Rolling_Avg_Pts_Display",
    "xGI": "Rolling_Sum_xGI_Display",
    "xGI/90": "Rolling_xGI_90_Display",
    "Next 5 FDR": "FDR_Display",
    "Mins": "Rolling_Avg_Mins_Display",
    "Apps": "Rolling_Matches_Played",
}

TRANSFER_MARKET_KEY_MAP = {
    "Target Player": "Player",
    "Player": "Player",
    "Club": "Team",
    "Pos": "Pos",
    "Price": "Price_Display",
    "Price Trend": "Price_Trend_Label",
    "GW Fixture": "Fixture",
    "FDR": "FDR",
    "Proj xP": "Proj_xP",
    "xP / £M": "xP_per_Mil",
    "Form": "Form",
    "Own %": "Own_Pct",
    "Season Pts": "Season_Points",
}

FIXTURE_TICKER_KEY_MAP = {
    "Club": "club_display",
    "Squad Players": "my_players",
    "gw0": "gw0_diff",
    "gw1": "gw1_diff",
    "gw2": "gw2_diff",
    "gw3": "gw3_diff",
    "gw4": "gw4_diff",
    "Total FDR": "difficulty_rating",
    "Total FDR (5 GW)": "difficulty_rating",
}


def extract_sort_key(val: Any, reverse: bool = False):
    """Safely extracts a sort tuple so that numeric values sort numerically,
    strings sort alphabetically, and missing/null values always sort to the bottom.
    """
    if val is None or val == "" or val == "—" or val == "-" or val == "TBD":
        # Missing values always placed at the bottom regardless of asc/desc
        return (-1, 0.0, "") if reverse else (2, 0.0, "")

    if isinstance(val, (int, float)):
        return (0, float(val), "")

    s = str(val).strip()

    # Clean currency, percentage, thousands comma, and 'm' suffix
    clean = s.lstrip("£$").rstrip("%m").replace(",", "").strip()

    # Handle FDR prefix, e.g. "FDR 3" -> 3.0
    if clean.upper().startswith("FDR "):
        clean = clean[4:].strip()

    try:
        return (0, float(clean), "")
    except ValueError:
        return (1, 0.0, s.lower())


def sort_table_rows(
    rows: List[Dict[str, Any]],
    col_name: str,
    reverse: bool = False,
    key_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Sorts a list of row dictionaries by the given column name using key_map."""
    if not rows or not col_name:
        return rows

    key = key_map.get(col_name, col_name) if key_map else col_name

    # If key still not in first row, try finding by case-insensitive match
    if rows and key not in rows[0]:
        for k in rows[0].keys():
            if k.lower() == key.lower():
                key = k
                break

    return sorted(rows, key=lambda r: extract_sort_key(r.get(key), reverse=reverse), reverse=reverse)

