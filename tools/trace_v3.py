from kaggle_environments import make
import sys
sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1000})
state = env.reset()

for step in range(8):
    obs0 = state[0].observation
    act0 = main_v3.agent(obs0, env.configuration)
    farm0 = obs0.farms[0]
    t44 = farm0["tiles"][4][4]
    print("Step", step, "Act:", act0["farmer"], "Hands:", act0["hands"], "t44:", t44)
    state = env.step([act0, {"farmer": ["PASS"], "hands": [], "market": []}])
