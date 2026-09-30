"""
Experimental ablation to test the Livestock Hypothesis vs Scarcity Hypothesis:
- Agent A: V48 host (livestock + production pipeline WITHOUT CXD scarcity reordering)
- Agent B: V48 with NO LIVESTOCK (crops only: Strawberries, Wheat, Melons with CXD scarcity)
- Agent C: Full V48 (Both Livestock + Scarcity)
Runs 10 games each on identical seeds vs starter.
"""
import os
import sys
import time
import json
import statistics

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

from kaggle_environments import make

seeds = [1000 + i * 83 for i in range(10)]

def agent_a(obs, config=None):
    # Runs the host without CXD scarcity reordering
    return wang_module._CXD_HOST(obs, config)

def agent_b(obs, config=None):
    # Runs full V48 but intercepts and strips all BUY_ANIMAL orders and animal structures
    action = wang_module.agent(obs, config)
    if not isinstance(action, dict):
        return action
    # Strip BUY_ANIMAL
    market = action.get("market", [])
    filtered_market = [o for o in market if not (isinstance(o, list) and len(o) >= 1 and o[0] == "BUY_ANIMAL")]
    # Strip BUILD_COOP / BUILD_PASTURE / FEED / CARE
    def filter_unit(op_list):
        if not isinstance(op_list, list) or not op_list:
            return op_list
        if op_list[0] in ("BUILD_COOP", "BUILD_PASTURE", "FEED", "CARE", "COLLECT_FERTILIZER"):
            return ["PASS"]
        return op_list
    farmer = filter_unit(action.get("farmer", ["PASS"]))
    hands = [filter_unit(h) for h in action.get("hands", [])]
    return {"farmer": farmer, "hands": hands, "market": filtered_market}

def agent_c(obs, config=None):
    # Full V48
    return wang_module.agent(obs, config)

def run_experiment():
    print("=== Testing Agent A (Livestock without Scarcity Reordering) ===")
    scores_a = []
    for idx, s in enumerate(seeds):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        res = env.run([agent_a, "starter"])
        score = float(res[-1][0].reward or 0.0)
        scores_a.append(score)
        print(f"Agent A G{idx+1:02d} [Seed {s}]: ${score:,.0f}")
        
    print("\n=== Testing Agent B (Scarcity without Livestock / Crops Only) ===")
    scores_b = []
    for idx, s in enumerate(seeds):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        res = env.run([agent_b, "starter"])
        score = float(res[-1][0].reward or 0.0)
        scores_b.append(score)
        print(f"Agent B G{idx+1:02d} [Seed {s}]: ${score:,.0f}")

    print("\n=== Testing Agent C (Full V48: Both Livestock + Scarcity) ===")
    scores_c = []
    for idx, s in enumerate(seeds):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        res = env.run([agent_c, "starter"])
        score = float(res[-1][0].reward or 0.0)
        scores_c.append(score)
        print(f"Agent C G{idx+1:02d} [Seed {s}]: ${score:,.0f}")

    print("\n==================================================")
    print("EXPERIMENT RESULTS (10 Seeds vs Starter)")
    print("==================================================")
    print(f"Agent A (Livestock Only, No Scarcity Reorder) Mean: ${statistics.mean(scores_a):,.1f} | Median: ${statistics.median(scores_a):,.1f}")
    print(f"Agent B (Scarcity Only, No Livestock)         Mean: ${statistics.mean(scores_b):,.1f} | Median: ${statistics.median(scores_b):,.1f}")
    print(f"Agent C (Full V48: Both Livestock + Scarcity) Mean: ${statistics.mean(scores_c):,.1f} | Median: ${statistics.median(scores_c):,.1f}")

    results = {
        "agent_a_scores": scores_a,
        "agent_b_scores": scores_b,
        "agent_c_scores": scores_c,
        "agent_a_mean": statistics.mean(scores_a),
        "agent_b_mean": statistics.mean(scores_b),
        "agent_c_mean": statistics.mean(scores_c),
    }
    with open(os.path.join(SCRATCH_DIR, "tools", "hypothesis_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_experiment()
