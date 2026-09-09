"""Domain constants, position mappings, chips, and FDR thresholds."""

POSITIONS = ["GKP", "DEF", "MID", "FWD"]

POSITION_NAMES = {
    1: "Goalkeeper",
    2: "Defender",
    3: "Midfielder",
    4: "Forward",
}

POSITION_SHORT = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}

CHIPS = ["None", "TC", "BB", "FH", "WC"]

CHIP_LABELS = {
    "None": "No Chip",
    "TC": "Triple Captain (3x)",
    "BB": "Bench Boost",
    "FH": "Free Hit",
    "WC": "Wildcard",
}

FDR_PALETTE = {
    1: {"bg": "rgba(34,197,94,0.22)", "color": "#4ade80", "label": "Very Easy"},
    2: {"bg": "rgba(34,197,94,0.22)", "color": "#4ade80", "label": "Easy"},
    3: {"bg": "rgba(100,116,139,0.16)", "color": "#cbd5e1", "label": "Moderate"},
    4: {"bg": "rgba(249,115,22,0.24)", "color": "#fb923c", "label": "Difficult"},
    5: {"bg": "rgba(239,68,68,0.28)", "color": "#f87171", "label": "Very Hard"},
}

BLANK_FDR_STYLE = {
    "bg": "rgba(15,23,42,0.5)",
    "color": "#64748b",
    "label": "Blank",
}

