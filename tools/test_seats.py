import os
import sys
import time
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kaggle_environments import make
import agent_v1 as ag

def run_both_seats():
    # Match 1: AuraFarm as Player 1 vs Starter as Player 0
    env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
    res = env.run(["starter", ag.agent])
    p0 = res[-1][0]
    p1 = res[-1][1]
    print(f"Seat Test (P1 AuraFarm vs P0 Starter): Starter=${p0.reward}, AuraFarm=${p1.reward}")

    # Match 2: AuraFarm as Player 0 vs Random as Player 1
    env2 = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
    res2 = env2.run([ag.agent, "random"])
    p0_2 = res2[-1][0]
    p1_2 = res2[-1][1]
    print(f"Random Test (P0 AuraFarm vs P1 Random): AuraFarm=${p0_2.reward}, Random=${p1_2.reward}")

if __name__ == "__main__":
    run_both_seats()
