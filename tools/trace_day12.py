from kaggle_environments import make
import sys
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(24 * 13):
    obs0 = state[0].observation
    day = obs0.day
    hour = obs0.hour
    act0 = main_v3.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    priv0 = state[0].observation.private
    
    if day == 12:
        # print farmer and hands positions and actions
        f_pos = farm0["farmer"]
        h_pos = farm0["hands"]
        f_inv = priv0["inventories"][0] if len(priv0["inventories"]) > 0 else {}
        h0_inv = priv0["inventories"][1] if len(priv0["inventories"]) > 1 else {}
        h1_inv = priv0["inventories"][2] if len(priv0["inventories"]) > 2 else {}
        
        print(f"D12 H{hour:02d}: Farmer@{f_pos} act={act0['farmer']} inv={f_inv.get('WHEAT', 0)} | Hand0@{h_pos[0] if h_pos else None} act={act0['hands'][0] if act0['hands'] else None} inv={h0_inv.get('WHEAT', 0)}")
        
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
