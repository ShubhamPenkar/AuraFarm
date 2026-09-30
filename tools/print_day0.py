import sys, os
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch\opponents\wangyh666\submissions")
import v48_adv12 as wang_module

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

print("--- V48 DAY 0 ACTIONS ---")
for step in range(24):
    obs0 = state[0].observation
    act0 = wang_module.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    priv0 = state[0].observation.private
    print(f"H{obs0.hour:02d}: Farmer={act0.get('farmer')} | Hands={len(act0.get('hands', []))} | Mkt={act0.get('market')} | Pos={farm0['farmer']}")
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
