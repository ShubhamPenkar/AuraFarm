import sys
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(8):
    obs0 = state[0].observation
    act0 = main_v3.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    priv0 = obs0.private
    print(f"Step {step}: Farmer={act0['farmer']} | Hands={len(act0['hands'])} {act0['hands'][:2]} | Mkt={act0['market']}")
    print(f"   Money={farm0['money']} | Shed={priv0['shed']} | Seeds={priv0['seeds']}")
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
