"""
Ablation study measuring incremental contributions of core components.
"""
import os
import sys
import time
import statistics
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kaggle_environments import make
import agent_v1 as ag

def run_ablations():
    print("=== Running Component Ablations ===")
    
    # 1. Full Agent (Benchmark)
    # We already have 20 games vs starter: Mean = 30,756
    
    # 2. Ablation 1: No Hired Hands (Farmer only)
    print("\nTesting: No Hired Hands (Farmer Solo)...")
    scores_no_hire = []
    for g in range(4):
        seed = 100 + g * 37
        def no_hire_agent(obs, config=None):
            # Intercept and strip HIRE orders
            action = ag.agent(obs, config)
            action["market"] = [o for o in action.get("market", []) if o[0] != "HIRE"]
            return action
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        res = env.run([no_hire_agent, "starter"])
        scores_no_hire.append(float(res[-1][0].reward))
    print(f"No Hire Mean: ${statistics.mean(scores_no_hire):,.1f} (vs Full: $30,756)")

    # 3. Ablation 2: No Land Expansion (NW Quadrant only)
    print("\nTesting: No Land Expansion (NW Quadrant only)...")
    scores_no_land = []
    for g in range(4):
        seed = 100 + g * 37
        def no_land_agent(obs, config=None):
            # Strip BUY_LAND orders
            action = ag.agent(obs, config)
            action["market"] = [o for o in action.get("market", []) if o[0] != "BUY_LAND"]
            return action
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        res = env.run([no_land_agent, "starter"])
        scores_no_land.append(float(res[-1][0].reward))
    print(f"No Land Expansion Mean: ${statistics.mean(scores_no_land):,.1f} (vs Full: $30,756)")

    # 4. Ablation 3: Blind Crop Selection (Fixed Wheat only, no market optimization)
    print("\nTesting: Fixed Crop (Wheat Only, no dynamic pricing)...")
    scores_wheat = []
    for g in range(4):
        seed = 100 + g * 37
        def wheat_agent(obs, config=None):
            # Replace crop purchases with Wheat
            action = ag.agent(obs, config)
            new_market = []
            for o in action.get("market", []):
                if o[0] == "BUY_SEED":
                    new_market.append(["BUY_SEED", "WHEAT", o[2]])
                else:
                    new_market.append(o)
            action["market"] = new_market
            return action
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        res = env.run([wheat_agent, "starter"])
        scores_wheat.append(float(res[-1][0].reward))
    print(f"Fixed Wheat Mean: ${statistics.mean(scores_wheat):,.1f} (vs Full: $30,756)")

if __name__ == "__main__":
    run_ablations()
