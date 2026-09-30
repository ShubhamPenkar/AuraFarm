from kaggle_environments import make
import sys
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(320):
    obs0 = state[0].observation
    act0 = main_v3.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    priv0 = state[0].observation.private
    if obs0.day in (10, 11, 12, 13) and obs0.hour in (0, 1, 2, 12, 23):
        print(f"D{obs0.day:02d} H{obs0.hour:02d}: Money={farm0['money']} | Shed={priv0['shed']} | Orders={act0['market']}")
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
