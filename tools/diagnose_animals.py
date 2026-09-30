import sys, collections
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

def diagnose_animals(seed=1000):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    state = env.reset()
    
    for step in range(720):
        if env.done:
            break
        obs0 = state[0].observation
        day = obs0.day
        hour = obs0.hour
        
        act0 = main_v3.agent(obs0, env.configuration)
        act1 = {"farmer": ["PASS"], "hands": [], "market": []}
        
        state = env.step([act0, act1])
        
        # Check animal states daily at hour 23
        if hour == 23 and day in range(8, 20):
            farm = state[0].observation.farms[0]
            priv = state[0].observation.private
            shed = priv.get("shed", {})
            animals = []
            for y in range(10):
                for x in range(10):
                    t = farm["tiles"][y][x]
                    if isinstance(t, dict) and t.get("kind") in ("PASTURE", "COOP"):
                        animals.append((x, y, t.get("animal"), t.get("consecutive_unfed", 0), t.get("fed_today", False)))
            print(f"Day {day:02d} H23: Money={farm['money']} | Shed Wheat={shed.get('WHEAT', 0)} | Animals={animals}")

if __name__ == "__main__":
    diagnose_animals(1000)
