import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kaggle_environments import make
import agent_v1 as ag

def run_test():
    env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
    t0 = time.time()
    res = env.run([ag.agent, "starter"])
    elapsed = time.time() - t0
    
    p0 = res[-1][0]
    p1 = res[-1][1]
    
    print(f"Game finished in {elapsed:.2f}s!")
    print(f"Player 0 (AuraFarm): status={p0.status}, reward={p0.reward}")
    print(f"Player 1 (Starter):  status={p1.status}, reward={p1.reward}")

if __name__ == "__main__":
    run_test()
