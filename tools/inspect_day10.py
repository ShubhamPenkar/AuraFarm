from kaggle_environments import make
import sys, os

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch\opponents\wangyh666\submissions")
import v48_adv12 as wang_module

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(265):
    obs0 = state[0].observation
    action0 = wang_module.agent(obs0, env.configuration)
    action1 = {"farmer": ["PASS"], "hands": [], "market": []}
    state = env.step([action0, action1])
    if 238 <= step <= 264:
        post_obs = state[0].observation
        post_farm = post_obs.farms[0]
        priv = state[0].observation.private
        mkt_orders = action0.get("market", [])
        print(f"Step {step:03d} (D{post_obs.day:02d} H{post_obs.hour:02d}): Money=${post_farm['money']:,.1f} | Shed={priv.get('shed')} | Orders={mkt_orders}")
