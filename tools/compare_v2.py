import os
import sys
import time
import statistics
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kaggle_environments import make
import agent_v2 as ag2

def compare():
    print("=== Testing Agent V2 (5 Seeds vs Starter) ===")
    scores = []
    for g in range(5):
        seed = 42 + g * 101
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        res = env.run([ag2.agent, "starter"])
        my_s = float(res[-1][0].reward)
        opp_s = float(res[-1][1].reward)
        scores.append(my_s)
        print(f"Seed {seed}: AuraFarm V2=${my_s:,.0f} vs Starter=${opp_s:,.0f}")
        
    print(f"V2 Mean Score: ${statistics.mean(scores):,.1f} (vs V1 Mean: $30,793.2)")

if __name__ == "__main__":
    compare()
