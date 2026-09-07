import asyncio
import pandas as pd
from backend.data import ensure_database_ready
from fpl_strategic_dashboard_reflex.pages.squad_analyzer import _run_squad_analysis
from fpl_strategic_dashboard_reflex.pages.transfer_analyzer import _run_transfer_analysis

def run_tests():
    print("Ensuring database is ready...")
    ensure_database_ready()
    
    print("Testing Squad Analysis...")
    # Manager 420 is just a generic ID (could be Magnus Carlsen or random manager). FPL limits mean we might get a valid response or 404.
    squad_res = _run_squad_analysis(manager_id="420", current_gw=1, selected_eval_gw=1, chip="None", comp=False, super_t=False, betting=False, weight=0.35, movement=False)
    if squad_res:
        print(f"Squad loaded: {squad_res['mgr_name']}, {len(squad_res['starters'])} starters.")
    else:
        print("Squad load returned None (Manager 420 might be invalid or no data).")
        
    print("Testing Transfer Analysis...")
    transfer_res = _run_transfer_analysis(manager_id="420", current_gw=1, horizon=1, ft=1, hits=0, betting=False, weight=0.35, mins=45, pos_sel=[], neg_sel=[])
    if transfer_res:
        print(f"Transfer analysis done. Swaps evaluated: {len(transfer_res['swaps'])}.")
    else:
        print("Transfer analysis returned None.")

run_tests()

