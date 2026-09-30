import sys, os, json, time, collections
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")
import main_v3

class AblationAgent:
    def __init__(self, mode):
        self.mode = mode # "A", "B", "C", "D", "E"
        self.underlying = main_v3.AuraFarmV3()
        
    def act(self, observation, configuration=None):
        step = int(observation.get("step", 0))
        day = int(observation.get("day", step // 24))
        hour = int(observation.get("hour", step % 24))
        farms = observation.get("farms", [])
        p_id = int(observation.get("player", 0))
        my_farm = farms[p_id] if len(farms) > p_id else {}
        hands = my_farm.get("hands", [])
        
        # Test A: Livestock only (no crops)
        if self.mode == "A":
            # Strip all seed purchases and non-livestock actions
            res = self.underlying.act(observation, configuration)
            filtered_orders = []
            for o in res.get("market", []):
                if o[0] not in ("BUY_SEED",) and not (o[0] == "SELL" and o[1] in ("WHEAT", "MELON", "STRAWBERRY", "CARROT")):
                    filtered_orders.append(o)
            res["market"] = filtered_orders
            # Filter unit actions: no PLANT or WATER
            f_act = res.get("farmer", ["PASS"])
            if f_act and f_act[0] in ("PLANT", "WATER"):
                res["farmer"] = ["PASS"]
            h_acts = []
            for ha in res.get("hands", []):
                if ha and ha[0] in ("PLANT", "WATER"):
                    h_acts.append(["PASS"])
                else:
                    h_acts.append(ha)
            res["hands"] = h_acts
            return res
            
        # Test B: Livestock + Wheat (no Strawberry, Melon, Carrot)
        elif self.mode == "B":
            res = self.underlying.act(observation, configuration)
            filtered_orders = []
            for o in res.get("market", []):
                if o[0] == "BUY_SEED" and o[1] != "WHEAT":
                    continue
                if o[0] == "SELL" and o[1] in ("MELON", "STRAWBERRY", "CARROT"):
                    continue
                filtered_orders.append(o)
            res["market"] = filtered_orders
            f_act = res.get("farmer", ["PASS"])
            if f_act and f_act[0] == "PLANT" and len(f_act) > 1 and f_act[1] != "WHEAT":
                res["farmer"] = ["PASS"]
            h_acts = []
            for ha in res.get("hands", []):
                if ha and ha[0] == "PLANT" and len(ha) > 1 and ha[1] != "WHEAT":
                    h_acts.append(["PASS"])
                else:
                    h_acts.append(ha)
            res["hands"] = h_acts
            return res
            
        # Test C: Livestock + Wheat + Strawberry (Fixed 3 hands, no dynamic workforce)
        elif self.mode == "C":
            # Cap hands at 3
            res = self.underlying.act(observation, configuration)
            raw_orders = res.get("market", [])
            filtered_orders = []
            for o in raw_orders:
                if o[0] == "HIRE" and len(hands) >= 3:
                    continue
                if o[0] == "BUY_SEED" and o[1] in ("MELON", "CARROT"):
                    continue
                if o[0] == "SELL" and o[1] in ("MELON", "CARROT"):
                    continue
                filtered_orders.append(o)
            res["market"] = filtered_orders
            f_act = res.get("farmer", ["PASS"])
            if f_act and f_act[0] == "PLANT" and len(f_act) > 1 and f_act[1] in ("MELON", "CARROT"):
                res["farmer"] = ["PASS"]
            h_acts = []
            for ha in res.get("hands", []):
                if ha and ha[0] == "PLANT" and len(ha) > 1 and ha[1] in ("MELON", "CARROT"):
                    h_acts.append(["PASS"])
                else:
                    h_acts.append(ha)
            res["hands"] = h_acts
            return res

        # Test D: Livestock + Wheat + Strawberry + Dynamic Workforce (no Melon/Carrot)
        elif self.mode == "D":
            res = self.underlying.act(observation, configuration)
            filtered_orders = []
            for o in res.get("market", []):
                if o[0] == "BUY_SEED" and o[1] in ("MELON", "CARROT"):
                    continue
                if o[0] == "SELL" and o[1] in ("MELON", "CARROT"):
                    continue
                filtered_orders.append(o)
            res["market"] = filtered_orders
            f_act = res.get("farmer", ["PASS"])
            if f_act and f_act[0] == "PLANT" and len(f_act) > 1 and f_act[1] in ("MELON", "CARROT"):
                res["farmer"] = ["PASS"]
            h_acts = []
            for ha in res.get("hands", []):
                if ha and ha[0] == "PLANT" and len(ha) > 1 and ha[1] in ("MELON", "CARROT"):
                    h_acts.append(["PASS"])
                else:
                    h_acts.append(ha)
            res["hands"] = h_acts
            return res

        # Test E: Full V3
        else:
            return self.underlying.act(observation, configuration)


def run_single_ablation(mode, seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    state = env.reset()
    agent = AblationAgent(mode)
    
    for step in range(720):
        if env.done:
            break
        obs0 = state[0].observation
        act0 = agent.act(obs0, env.configuration)
        act1 = {"farmer": ["PASS"], "hands": [], "market": []}
        state = env.step([act0, act1])
        
    score = state[0].observation.farms[0]["money"]
    return score

def main():
    seeds = [1000 + i for i in range(10)]
    modes = [
        ("A", "Test A: Livestock Only (No Crops)"),
        ("B", "Test B: Livestock + Wheat"),
        ("C", "Test C: Livestock + Wheat + Strawberry (Fixed 3 Hands)"),
        ("D", "Test D: Livestock + Wheat + Strawberry + Dynamic Workforce"),
        ("E", "Test E: Full AuraFarm V3")
    ]
    
    all_results = {}
    
    print("=" * 60)
    print("STARTING AURAFARM V3 ISOLATED ABLATION TOURNAMENT")
    print("=" * 60)
    
    for mode, desc in modes:
        print(f"\nRunning {desc} across 10 seeds...")
        scores = []
        t0 = time.time()
        for s in seeds:
            sc = run_single_ablation(mode, s)
            scores.append(sc)
            print(f"  Seed {s}: ${sc:,.2f}")
        elap = time.time() - t0
        
        mean_sc = sum(scores) / len(scores)
        sorted_sc = sorted(scores)
        median_sc = (sorted_sc[4] + sorted_sc[5]) / 2.0
        min_sc = min(scores)
        max_sc = max(scores)
        
        all_results[mode] = {
            "description": desc,
            "seeds": seeds,
            "scores": scores,
            "mean": mean_sc,
            "median": median_sc,
            "min": min_sc,
            "max": max_sc,
            "runtime_sec": elap
        }
        print(f"-> {mode} Mean: ${mean_sc:,.2f} | Median: ${median_sc:,.2f} | Min: ${min_sc:,.2f} | Max: ${max_sc:,.2f}")

    with open(r"C:\Users\Sanjana\.gemini\antigravity\scratch\tools\v3_ablation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
        
    print("\nSaved all ablation results to tools/v3_ablation_results.json")

if __name__ == "__main__":
    main()
