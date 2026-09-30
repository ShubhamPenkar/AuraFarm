"""
Compare V2 and V48 on seed 1000 at days 3, 6, 9, 12, 15, 18, 21, 24, 27, 30.
"""
import os
import sys
import json
import collections

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, SCRATCH_DIR)

from kaggle_environments import make
import main_v2 as aura_v2

def run_v2(seed=1000):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    state = env.reset()
    
    check_days = {3, 6, 9, 12, 15, 18, 21, 24, 27, 30}
    snapshots = {}
    
    for step in range(720):
        if env.done:
            break
        obs = state[0].observation
        day = obs.day
        hour = obs.hour
        
        action0 = aura_v2.agent(obs, env.configuration)
        action1 = {"farmer": ["PASS"], "hands": [], "market": []}
        state = env.step([action0, action1])
        
        post_obs = state[0].observation
        post_farm = post_obs.farms[0]
        
        if hour == 23 and (day + 1) in check_days:
            # Count crops, animals, quads
            crops = collections.defaultdict(int)
            animals = collections.defaultdict(int)
            pens = 0
            for r in post_farm["tiles"]:
                for t in r:
                    if isinstance(t, dict):
                        k = t.get("kind")
                        if k == "PLANT":
                            crops[t.get("crop")] += 1
                        elif k in ("COOP", "PASTURE"):
                            pens += 1
                            if "animal" in t and t["animal"]:
                                animals[t["animal"]] += 1
                                
            snapshots[day + 1] = {
                "day": day + 1,
                "money": post_farm["money"],
                "quads": len(post_farm.get("unlocked_quadrants", [])),
                "pens": pens,
                "animals": dict(animals),
                "crops": dict(crops),
                "shed": dict(state[0].observation.private.get("shed", {}))
            }
            
    return snapshots

if __name__ == "__main__":
    v2_snaps = run_v2(1000)
    with open(os.path.join(SCRATCH_DIR, "tools", "v48_telemetry_seed1000.json")) as f:
        v48_data = json.load(f)
    v48_snaps = {s["day"] + 1: s for s in v48_data["daily_snapshots"]}
    
    print("==========================================================================================")
    print(f"{'Day':<4} | {'V2 Money':<10} | {'V48 Money':<10} | {'V2 Quads':<8} | {'V48 Quads':<8} | {'V2 Crops/Animals':<22} | {'V48 Crops/Animals'}")
    print("==========================================================================================")
    for d in [3, 6, 9, 12, 15, 18, 21, 24, 27, 30]:
        v2_s = v2_snaps.get(d, {})
        v48_s = v48_snaps.get(d, {})
        m2 = v2_s.get("money", 0)
        m48 = v48_s.get("money", 0)
        q2 = v2_s.get("quads", 1)
        q48 = v48_s.get("unlocked_quadrants", 1)
        c2 = str(v2_s.get("crops", {}))
        c48 = f"A:{v48_s.get('animals', {})} C:{v48_s.get('crops', {})}"
        print(f"{d:<4} | ${m2:<9,.0f} | ${m48:<9,.0f} | {q2:<8} | {q48:<8} | {c2:<22} | {c48}")
