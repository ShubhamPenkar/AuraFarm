import sys, os, collections
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

def test_v3_game(seed=1000):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    state = env.reset()
    
    daily_snapshots = []
    
    for step in range(720):
        if env.done:
            break
        obs0 = state[0].observation
        day = obs0.day
        hour = obs0.hour
        
        act0 = main_v3.agent(obs0, env.configuration)
        
        # Simple starter opponent
        act1 = {"farmer": ["PASS"], "hands": [], "market": []}
        
        state = env.step([act0, act1])
        
        if hour == 23:
            post_obs = state[0].observation
            post_farm = post_obs.farms[0]
            priv = state[0].observation.private
            
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
                            if t.get("animal"):
                                animals[t.get("animal")] += 1
            
            daily_snapshots.append({
                "day": day,
                "money": post_farm["money"],
                "quads": len(post_farm.get("unlocked_quadrants", [])),
                "pens": pens,
                "animals": dict(animals),
                "crops": dict(crops),
                "shed": dict(priv.get("shed", {}))
            })
            
    final_score = state[0].observation.farms[0]["money"]
    print(f"Game finished! Final Score: ${final_score:,.2f}")
    print("\n--- Daily Progression ---")
    for s in daily_snapshots:
        if s["day"] in (0, 5, 10, 15, 20, 25, 29):
            print(f"Day {s['day']:02d}: Money=${s['money']:,.0f} | Quads={s['quads']} | Pens={s['pens']} | Animals={s['animals']} | Crops={s['crops']}")

if __name__ == "__main__":
    test_v3_game(1000)
