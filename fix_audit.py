
import pandas as pd
from backend.squad_logic import get_player_img_url, fmt_num

def load_audit_data(conn, selected_gw):
    from backend.audit_db import init_audit_tables, get_all_gw_versions
    init_audit_tables(conn)
    versions = get_all_gw_versions(conn, selected_gw)
    return versions

def lock_audit_version(conn, manager_id, selected_gw, current_gw):
    from backend.audit_logic import compute_active_solver_squad
    from backend.audit_db import save_pre_gw_snapshot
    lineup_records, err = compute_active_solver_squad(conn, manager_id, selected_gw, current_gw)
    if err:
        return False, err
    new_ver = save_pre_gw_snapshot(conn, selected_gw, lineup_records, transfers_data=[])
    return True, new_ver

def settle_audit_version(conn, selected_gw, selected_version):
    from backend.squad_logic import fetch_live_gameweek_points
    from backend.audit_db import settle_post_gw_snapshot
    raw_live_map = fetch_live_gameweek_points(selected_gw)
    if not raw_live_map:
        return False, "Live data not available"
    clean_points_map = {
        pid: data["points"] if isinstance(data, dict) else data 
        for pid, data in raw_live_map.items()
    }
    settle_post_gw_snapshot(conn, selected_gw, clean_points_map, target_version=selected_version)
    return True, ""
    
def get_audit_snapshot(conn, selected_gw, selected_version):
    from backend.audit_db import get_snapshot
    import json
    snapshot = get_snapshot(conn, selected_gw, version=selected_version)
    if not snapshot:
        return None
    
    lineups_raw = snapshot.get("lineups_json", "[]")
    lineup = json.loads(lineups_raw) if lineups_raw else []
    
    # Process for UI
    starters = []
    bench = []
    for p in lineup:
        p["img_url"] = get_player_img_url(p.get("photo"), p.get("code"))
        if p.get("bench_order", 0) == 0:
            starters.append(p)
        else:
            bench.append(p)
            
    return {
        "created_at": snapshot.get("created_at"),
        "starters": starters,
        "bench": bench,
        "total_proj": sum(p.get("proj_pts", 0) for p in starters),
        "total_act": sum(p.get("actual_pts", 0) for p in starters if p.get("actual_pts") is not None),
        "is_settled": any(p.get("actual_pts") is not None for p in starters)
    }

with open("backend/audit_logic.py", "a", encoding="utf-8") as f:
    import inspect
    f.write("\n\n")
    f.write(inspect.getsource(load_audit_data))
    f.write("\n")
    f.write(inspect.getsource(lock_audit_version))
    f.write("\n")
    f.write(inspect.getsource(settle_audit_version))
    f.write("\n")
    f.write(inspect.getsource(get_audit_snapshot))

