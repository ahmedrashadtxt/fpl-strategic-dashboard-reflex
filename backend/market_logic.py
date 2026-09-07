import math
import pandas as pd
from rapidfuzz import fuzz, process

from backend.betting_engine import fetch_upcoming_betting_odds, get_fixture_market_xg_and_movement
from backend.data import (
    calculate_projected_points,
    get_fixture_for_team,
    get_historical_player_baselines,
    get_manager_squad_ids,
)

def apply_target_market_projection(
    conn,
    base_proj_pts: float,
    pos: str,
    fdr: int,
    is_home: bool,
    team_short: str,
    opp_short: str,
    market_weight: float,
    factor_movement: bool,
    market_cache: dict,
) -> float:
    h_team = team_short if is_home else opp_short
    a_team = opp_short if is_home else team_short
    fdr_h = fdr if is_home else 3
    fdr_a = 3 if is_home else fdr

    mkt_h_xg, mkt_a_xg, mkt_h_cs, mkt_a_cs, mv = get_fixture_market_xg_and_movement(
        conn, h_team, a_team, fdr_h, fdr_a, market_cache
    )

    mkt_team_xg = mkt_h_xg if is_home else mkt_a_xg
    mkt_cs_prob = mkt_h_cs if is_home else mkt_a_cs
    team_mv = mv["home"] if is_home else mv["away"]

    fdr_base = max(0.6, 2.55 - (fdr * 0.35))
    blended_xg = ((1.0 - market_weight) * fdr_base) + (market_weight * mkt_team_xg)

    if factor_movement:
        blended_xg = max(0.4, blended_xg + (0.40 * team_mv["delta_xg"]))

    if pos in ("MID", "FWD"):
        xg_scale = blended_xg / max(fdr_base, 0.4)
        xg_scale = max(0.4, min(2.2, xg_scale))
        return round(base_proj_pts * xg_scale, 2)
    elif pos in ("GKP", "DEF"):
        base_cs_prob = max(0.05, min(0.65, math.exp(-max(0.6, fdr * 0.4))))
        blended_cs_prob = ((1.0 - market_weight) * base_cs_prob) + (market_weight * mkt_cs_prob)
        if factor_movement:
            blended_cs_prob = max(0.02, min(0.85, blended_cs_prob + (0.25 * team_mv["delta_win"])))
        cs_diff = (blended_cs_prob - base_cs_prob) * 4.0
        return round(max(0.5, base_proj_pts + cs_diff), 2)
    return round(base_proj_pts, 2)


def fetch_transfer_targets_base_data(_conn, current_gw: int, target_gw: int, enable_betting_target: bool, odds_api_key: str):
    """Caches base model evaluations and betting projections across all candidates."""
    query = """
    SELECT
        p.id,
        p.id AS element_id,
        p.code,
        p.photo,
        p.web_name AS Player,
        p.first_name || ' ' || p.second_name AS Full_Name,
        t.short_name AS Team,
        t.name AS Club_Name,
        p.team AS team_id,
        CASE p.element_type
            WHEN 1 THEN 'GKP'
            WHEN 2 THEN 'DEF'
            WHEN 3 THEN 'MID'
            WHEN 4 THEN 'FWD'
        END AS Pos,
        pos.singular_name AS Position,
        p.now_cost / 10.0 AS Cost,
        p.now_cost / 10.0 AS Price,
        p.minutes AS minutes,
        p.minutes AS Minutes,
        p.total_points AS Total_Points,
        p.total_points AS Season_Points,
        p.form AS Form,
        p.points_per_game AS PPG,
        p.expected_goals,
        p.expected_assists,
        p.expected_goal_involvements_per_90 AS xGI_per_90,
        p.status AS Status,
        p.chance_of_playing_next_round AS Chance
    FROM players p
    INNER JOIN teams t ON p.team = t.id
    INNER JOIN positions pos ON p.element_type = pos.id
    WHERE (p.status = 'a' OR p.chance_of_playing_next_round >= 75)
    """
    candidates_df = pd.read_sql(query, _conn)
    if candidates_df.empty:
        return pd.DataFrame()

    fixtures_df = pd.read_sql(
        """
        SELECT f.event AS GW, f.team_h AS team_h_id, f.team_a AS team_a_id,
               th.short_name AS Home_Team, ta.short_name AS Away_Team,
               f.team_h_difficulty AS Home_Diff, f.team_a_difficulty AS Away_Diff
        FROM fixtures f
        INNER JOIN teams th ON f.team_h = th.id
        INNER JOIN teams ta ON f.team_a = ta.id
        WHERE f.event >= ? AND f.event <= ?
        """,
        _conn,
        params=[current_gw, current_gw + 4],
    )
    hist_baselines_df = get_historical_player_baselines(_conn)
    market_cache = fetch_upcoming_betting_odds(odds_api_key) if enable_betting_target else {}

    results = []
    for _, p_row in candidates_df.iterrows():
        fix_data = get_fixture_for_team(fixtures_df, p_row["team_id"], target_gw)
        base_xp = calculate_projected_points(p_row, fix_data, current_gw, hist_baselines_df)
        final_xp = base_xp

        if enable_betting_target and fix_data.get("opponent"):
            opp_short = fix_data["opponent"].replace(" (H)", "").replace(" (A)", "")
            final_xp = apply_target_market_projection(
                _conn,
                base_xp,
                p_row["Pos"],
                fix_data["fdr"],
                fix_data["is_home"],
                p_row["Team"],
                opp_short,
                market_weight=0.35,
                factor_movement=True,
                market_cache=market_cache,
            )

        price = float(p_row["Cost"])
        xp_per_mil = round(final_xp / max(price, 4.0), 2)

        row_dict = dict(p_row)
        row_dict.update({
            "Fixture": fix_data.get("opponent", "TBD"),
            "FDR": fix_data.get("fdr", 3),
            "Proj_xP": round(final_xp, 2),
            "xP_per_Mil": xp_per_mil,
        })
        results.append(row_dict)

    target_df = pd.DataFrame(results)
    if not target_df.empty:
        for col in ["Proj_xP", "xP_per_Mil", "Cost", "Price", "Form", "Total_Points", "Season_Points", "FDR"]:
            if col in target_df.columns:
                target_df[col] = pd.to_numeric(target_df[col], errors="coerce").fillna(0)

        target_df["_search_target"] = (
            target_df["Player"].fillna("")
            + " "
            + target_df["Full_Name"].fillna("")
            + " "
            + target_df["Team"].fillna("")
            + " "
            + target_df["Club_Name"].fillna("")
        ).str.strip()

    return target_df


