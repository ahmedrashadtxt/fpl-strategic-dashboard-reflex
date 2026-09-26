"""Central step configuration for interactive spotlight tours across all tabs.

Pre-flight Check 3: Content and behavior are cleanly separated.
All step titles and bodies are defined in this single data structure.
"""

TOUR_STEPS_BY_TAB: dict[str, list[dict[str, str]]] = {
    "squad_analyzer": [
        {
            "target_id": "tour-hero-pts",
            "title": "Gameweek Score & Baseline",
            "body": "Headline score from the latest completed gameweek with benchmark delta against the worldwide average.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-secondary-metrics",
            "title": "Manager Portfolio",
            "body": "Real-time tracking of overall rank, team value, and available in-the-bank capital.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-select-gw",
            "title": "Select Gameweek",
            "body": "Toggle between completed gameweek retrospectives and upcoming fixture planning.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-pitch-formation",
            "title": "Tactical Formation",
            "body": "Interactive 2D pitch showing player roles, fixture FDR ratings, and projected xP.",
            "placement": "top",
        },
        {
            "target_id": "tour-view-toggle",
            "title": "Pitch vs. List View",
            "body": "Switch between visual pitch layout and a tabular breakdown of starter/bench metrics.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-comparison-toggle",
            "title": "Dream 15 Benchmark",
            "body": "Compare your starting XI against the mathematically optimal budget Dream 15.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-betting-controls",
            "title": "Market Overlay & Odds Weight",
            "body": "Blend statistical projections with live bookmaker odds and adjust the weighting slider.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-squad-rating",
            "title": "Squad Rating Index",
            "body": "Holistic composite rating evaluating fixture ease, form momentum, and expected haul security.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-pitch-formation",
            "title": "Pro-Tip: Player Deep Dive",
            "body": "Click on any player shirt on the pitch to view detailed underlying metric popups, injury news, and expected minutes.",
            "placement": "top",
        },
    ],
    "transfer_solver": [
        {
            "target_id": "tour-transfer-mode",
            "title": "Strategy Mode",
            "body": "Choose between Regular Transfers (budget-conserving hits), Wildcard (full 15-man revamp), or Free Hit (1-GW ceiling).",
            "placement": "bottom",
        },
        {
            "target_id": "tour-transfer-horizon",
            "title": "Planning Horizon",
            "body": "Optimize for immediate GW payoff (1-GW) or smooth transitions across multi-week windows (2, 3, 5, or 8 GWs).",
            "placement": "bottom",
        },
        {
            "target_id": "tour-transfer-hits",
            "title": "Max Point Deductions",
            "body": "Allow the MILP solver to take intentional -4 hits if long-term expected points gain justifies the cost.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-transfer-locks",
            "title": "Priorities & Blacklist",
            "body": "Lock current squad players, force target signings, force sales, or blacklist unwanted market assets.",
            "placement": "top",
        },
        {
            "target_id": "tour-transfer-pitch",
            "title": "Squad Lineup Comparison",
            "body": "Side-by-side pitch or list view comparing current starters against solver-recommended replacements.",
            "placement": "top",
        },
    ],
    "match_simulator": [
        {
            "target_id": "tour-sim-gw",
            "title": "Fixture Target",
            "body": "Select any future gameweek to simulate based on bookmaker clean sheet and anytime goalscorer odds.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-sim-squad",
            "title": "Squad Source",
            "body": "Stress-test your active FPL squad, post-transfer plan, Budget Dream 15, or build a custom 15-player team.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-sim-iterations",
            "title": "Monte Carlo Precision",
            "body": "Simulate 1,000 to 20,000 probabilistic iterations to model player goal distributions and variance tails.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-sim-results",
            "title": "Risk Metrics & Percentiles",
            "body": "Assess 10th percentile floor safety when protecting rank, and 90th percentile ceiling when chasing aggressive swings.",
            "placement": "top",
        },
    ],
    "expected_stats": [
        {
            "target_id": "tour-xstats-filters",
            "title": "Attacking Filters & Controls",
            "body": "Filter by position, price ceiling, and minimum average minutes per GW to eliminate bench cameos and focus on nailed starters.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-xstats-cards",
            "title": "Top Attacking Highlights",
            "body": "Quick-reference cards spotlighting the top 4 attacking performers for your selected ranking metric (e.g. Projected Attacking xP or xGI).",
            "placement": "bottom",
        },
        {
            "target_id": "tour-xstats-table",
            "title": "xG, xA & Goal Involvement Table",
            "body": "Detailed statistics covering xG, xA, total xGI, xGI/90, and optional historical multi-season career baselines.",
            "placement": "top",
        },
    ],
    "defensive_stats": [
        {
            "target_id": "tour-def-controls",
            "title": "Defensive Controls & Ranking",
            "body": "Filter by position, set price caps, and rank defenders & goalkeepers by DC/90, CBI, Tackles, Clean Sheets, or Saves.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-def-cards",
            "title": "Top Defensive Highlights",
            "body": "Quick-reference cards spotlighting the top 4 defensive assets based on your selected criteria (e.g. Projected Def xP, DC/90, or Clean Sheets).",
            "placement": "bottom",
        },
        {
            "target_id": "tour-def-table",
            "title": "Defensive Contribution & CS Odds Table",
            "body": "Detailed statistics covering Clean Sheet probabilities (CS%), xGC/90, defensive actions (CBI, Recoveries, Tackles), and historical baselines.",
            "placement": "top",
        },
    ],
    "rolling_form": [
        {
            "target_id": "tour-form-kpis",
            "title": "Form Metrics Strip",
            "body": "Top projected form performers and key risers entering favorable upcoming schedules.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-form-filters",
            "title": "Rolling Form Controls",
            "body": "Filter by budget ceiling and appearances to eliminate small sample noise.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-form-scatter",
            "title": "Quadrant Opportunity Map",
            "body": "Visual scatter plot mapping form against schedule difficulty to isolate top targets in Quadrant I (top-left).",
            "placement": "top",
        },
        {
            "target_id": "tour-form-table",
            "title": "Projected Form xP Table",
            "body": "Blended expected points combining rolling xGI/90, actual match points form, and upcoming 5-GW difficulty.",
            "placement": "top",
        },
    ],
    "fixture_ticker": [
        {
            "target_id": "tour-ticker-filter",
            "title": "Ticker Filters & Squad Isolation",
            "body": "Filter the schedule by player name or isolate clubs represented in your active 15-man squad.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-ticker-grid",
            "title": "Fixture Difficulty Ticker",
            "body": "Upcoming 5 gameweeks ranked by official FDR and venue (Home vs Away) to plan transfers 2-3 weeks ahead of fixture swings.",
            "placement": "top",
        },
    ],
    "transfer_market": [
        {
            "target_id": "tour-market-kpis",
            "title": "Market Highlights",
            "body": "Summary of high-EV transfer targets, top value picks, and projected gainers.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-market-filters",
            "title": "Budget & Transfer Filters",
            "body": "Set exact price ceilings, exclude current squad members, and filter by position to find replacements.",
            "placement": "bottom",
        },
        {
            "target_id": "tour-market-table",
            "title": "Transfer Target Finder",
            "body": "Rank targets by Hybrid Projected Points (Proj xP) and Value Efficiency (xP / £M) to free up funds for premiums.",
            "placement": "top",
        },
    ],
}
