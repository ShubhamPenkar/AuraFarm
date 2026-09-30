"""
Detailed telemetry instrumenter for V48 (wangyh666).
Records every action, market trade, tile state, inventory, and revenue event across all 720 turns.
"""
import os
import sys
import json
import collections

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, SCRATCH_DIR)

from kaggle_environments import make

# Opponent import
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

def instrument_game(seed=1000):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    
    revenue_by_commodity = collections.defaultdict(float)
    qty_sold_by_commodity = collections.defaultdict(int)
    all_sales_events = []
    daily_snapshots = []
    
    state = env.reset()
    
    for step in range(720):
        if env.done:
            break
            
        obs0 = state[0].observation
        day = obs0.day
        hour = obs0.hour
        farm0 = obs0.farms[0]
        priv0 = state[0].observation.private
        market = obs0.market
        town = obs0.town
        
        # Pre-step snapshot
        pre_inv = dict(market.get("inventory", {}))
        pre_prices = dict(market.get("prices", {}))
        pre_money = farm0["money"]
        pre_shed = dict(priv0.get("shed", {}))
        
        # Call V48
        action0 = wang_module.agent(obs0, env.configuration)
        action1 = {"farmer": ["PASS"], "hands": [], "market": []}
        
        # Step the environment
        state = env.step([action0, action1])
        
        # Post-step analysis
        post_obs0 = state[0].observation
        post_farm0 = post_obs0.farms[0]
        post_priv0 = state[0].observation.private
        post_money = post_farm0["money"]
        post_shed = dict(post_priv0.get("shed", {}))
        post_inv = dict(post_obs0.market.get("inventory", {}))
        
        # Track sales
        if post_money > pre_money:
            # Money increased -> something sold
            for item in pre_shed:
                sold_qty = max(0, pre_shed[item] - post_shed.get(item, 0))
                if sold_qty > 0:
                    unit_p = pre_prices.get(item, 0)
                    total_rev = sold_qty * unit_p
                    revenue_by_commodity[item] += total_rev
                    qty_sold_by_commodity[item] += sold_qty
                    all_sales_events.append({
                        "step": step,
                        "day": day,
                        "hour": hour,
                        "commodity": item,
                        "quantity": sold_qty,
                        "unit_price": unit_p,
                        "revenue": total_rev,
                        "pre_inv": pre_inv.get(item, 0),
                        "post_inv": post_inv.get(item, 0),
                        "unlocked_shops": list(town.get("unlocked_shops", []))
                    })

        # Record daily snapshot at hour 23
        if hour == 23:
            crops_count = collections.defaultdict(int)
            animals_count = collections.defaultdict(int)
            pens_count = 0
            for r in post_farm0["tiles"]:
                for t in r:
                    if isinstance(t, dict):
                        k = t.get("kind")
                        if k == "PLANT":
                            crops_count[t.get("crop")] += 1
                        elif k in ("COOP", "PASTURE"):
                            pens_count += 1
                            if "animal" in t and t["animal"]:
                                animals_count[t["animal"]] += 1
                                
            daily_snapshots.append({
                "day": day,
                "money": post_money,
                "hands": len(post_farm0.get("hands", [])),
                "unlocked_quadrants": len(post_farm0.get("unlocked_quadrants", [])),
                "pens": pens_count,
                "animals": dict(animals_count),
                "crops": dict(crops_count),
                "shed": dict(post_shed),
                "unlocked_shops": list(post_obs0.town.get("unlocked_shops", [])),
            })
            
    final_score = state[0].observation.farms[0]["money"]
    print(f"Game completed! V48 Final Score: ${final_score:,.2f}")
    
    out_data = {
        "final_score": final_score,
        "revenue_by_commodity": dict(revenue_by_commodity),
        "qty_sold_by_commodity": dict(qty_sold_by_commodity),
        "sales_events": all_sales_events,
        "daily_snapshots": daily_snapshots
    }
    
    out_path = os.path.join(SCRATCH_DIR, "tools", "v48_telemetry_seed1000.json")
    with open(out_path, "w") as f:
        json.dump(out_data, f, indent=2)
        
    print(f"Saved telemetry to {out_path}")
    return out_data

if __name__ == "__main__":
    instrument_game(1000)
