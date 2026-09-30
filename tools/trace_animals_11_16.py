from kaggle_environments import make
import sys
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(360):
    obs0 = state[0].observation
    act0 = main_v3.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    priv0 = state[0].observation.private
    
    if obs0.day in range(11, 16) and obs0.hour == 23:
        animals = []
        for y in range(10):
            for x in range(10):
                t = farm0["tiles"][y][x]
                if isinstance(t, dict) and "animal" in t:
                    animals.append((x, y, t["animal"], t.get("consecutive_unfed", 0), t.get("fed_today", False)))
        print(f"Day {obs0.day:02d} H23: Animals={animals} | Shed={priv0['shed']}")
        
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
