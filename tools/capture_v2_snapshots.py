import sys, os, collections
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
from tools.agent_v2 import agent as agent_v2

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

v2_snapshots = {}

for step in range(720):
    if env.done:
        break
    obs0 = state[0].observation
    day = obs0.day
    hour = obs0.hour
    
    # Run V2
    action0 = agent_v2(obs0, env.configuration)
    action1 = {"farmer": ["PASS"], "hands": [], "market": []}
    
    hands_count = len(obs0.farms[0].get("hands", []))
    
    state = env.step([action0, action1])
    
    if hour == 23 and day in (0, 5, 10, 15, 20, 25, 29):
        post_obs = state[0].observation
        post_farm = post_obs.farms[0]
        priv = state[0].observation.private
        shed = priv.get("shed", {})
        prices = post_obs.market.get("prices", {})
        
        inv_val = sum(qty * prices.get(item, 0) for item, qty in shed.items())
        
        crops = collections.defaultdict(int)
        animals = collections.defaultdict(int)
        for r in post_farm["tiles"]:
            for t in r:
                if isinstance(t, dict):
                    if t.get("kind") == "PLANT":
                        crops[t.get("crop")] += 1
                    elif t.get("kind") in ("COOP", "PASTURE") and t.get("animal"):
                        animals[t.get("animal")] += 1
                        
        primary_crop = max(crops.items(), key=lambda x: x[1])[0] if crops else "None"
        
        v2_snapshots[day] = {
            "money": post_farm["money"],
            "quads": len(post_farm.get("unlocked_quadrants", [])),
            "hands": hands_count,
            "animals": sum(animals.values()),
            "primary_crop": primary_crop,
            "inv_val": inv_val,
            "crops": dict(crops),
            "animal_dict": dict(animals)
        }

print("V2 Final score:", state[0].observation.farms[0]["money"])
import json
print(json.dumps(v2_snapshots, indent=2))
