import os
import sys
import time
import json
import statistics

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, SCRATCH_DIR)

from kaggle_environments import make

import main_v3 as aura_v3

# Opponents
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "vicky0718"))
import main as vicky_module

def run_match_series(agent_name, agent_mod, opp_name, opp_mod, seeds, num_games):
    records = []
    print(f"\n==================================================")
    print(f"RUNNING MATCH SERIES: {agent_name} vs {opp_name} ({num_games} games)")
    print(f"==================================================")
    
    for idx, seed in enumerate(seeds[:num_games]):
        seat = 0 if idx < (num_games // 2) else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        state = env.reset()
        
        t0 = time.time()
        for step in range(720):
            if env.done:
                break
            obs0 = state[0].observation
            obs1 = state[1].observation
            obs0["step"] = step
            obs1["step"] = step
            
            if seat == 0:
                act0 = agent_mod.agent(obs0, env.configuration)
                act1 = opp_mod.agent(obs1, env.configuration)
            else:
                act0 = opp_mod.agent(obs0, env.configuration)
                act1 = agent_mod.agent(obs1, env.configuration)
                
            state = env.step([act0, act1])
            
        dur = time.time() - t0
        
        s_aura = float(state[seat].observation.farms[seat]["money"])
        s_opp = float(state[1 - seat].observation.farms[1 - seat]["money"])
        winner = agent_name if s_aura > s_opp else (opp_name if s_opp > s_aura else "TIE")
        
        rec = {
            "agent": agent_name,
            "opponent": opp_name,
            "game_idx": idx + 1,
            "seed": seed,
            "seat": seat,
            "agent_score": s_aura,
            "opp_score": s_opp,
            "winner": winner,
            "duration_s": dur
        }
        records.append(rec)
        print(f"Game {idx+1:02d} (Seed {seed}, Seat {seat}): {agent_name}=${s_aura:,.2f} | {opp_name}=${s_opp:,.2f} -> Winner: {winner} ({dur:.2f}s)")
        
    a_scores = [r["agent_score"] for r in records]
    o_scores = [r["opp_score"] for r in records]
    wins = sum(1 for r in records if r["winner"] == agent_name)
    
    stats = {
        "agent": agent_name,
        "opponent": opp_name,
        "games": num_games,
        "agent_mean": statistics.mean(a_scores),
        "agent_median": statistics.median(a_scores),
        "agent_min": min(a_scores),
        "agent_max": max(a_scores),
        "opp_mean": statistics.mean(o_scores),
        "opp_median": statistics.median(o_scores),
        "opp_min": min(o_scores),
        "opp_max": max(o_scores),
        "wins": wins,
        "win_rate_pct": (wins / num_games) * 100.0,
        "records": records
    }
    return stats

def main():
    v48_seeds = [1000 + i * 77 for i in range(20)]
    vicky_seeds = [2000 + i * 53 for i in range(10)]
    
    results = {}
    
    # 1. Load historical V1 vs V48 (20 games) and V2 vs V48 (20 games)
    hist_file = os.path.join(SCRATCH_DIR, "tools", "v1_v2_comparative_benchmark.json")
    if os.path.exists(hist_file):
        with open(hist_file, "r") as f:
            hist_data = json.load(f)
            
        v1_records = [d for d in hist_data if d["version"] == "V1" and d["opponent"] == "V48"]
        v2_records = [d for d in hist_data if d["version"] == "V2" and d["opponent"] == "V48"]
        
        v1_a = [r["aura_score"] for r in v1_records]
        v1_o = [r["opp_score"] for r in v1_records]
        v1_wins = sum(1 for r in v1_records if r["aura_score"] > r["opp_score"])
        results["V1_vs_V48"] = {
            "agent": "AuraFarm_V1",
            "opponent": "V48",
            "games": len(v1_records),
            "agent_mean": statistics.mean(v1_a),
            "agent_median": statistics.median(v1_a),
            "agent_min": min(v1_a),
            "agent_max": max(v1_a),
            "opp_mean": statistics.mean(v1_o),
            "opp_median": statistics.median(v1_o),
            "opp_min": min(v1_o),
            "opp_max": max(v1_o),
            "wins": v1_wins,
            "win_rate_pct": (v1_wins / len(v1_records)) * 100.0,
            "records": v1_records
        }
        
        v2_a = [r["aura_score"] for r in v2_records]
        v2_o = [r["opp_score"] for r in v2_records]
        v2_wins = sum(1 for r in v2_records if r["aura_score"] > r["opp_score"])
        results["V2_vs_V48"] = {
            "agent": "AuraFarm_V2",
            "opponent": "V48",
            "games": len(v2_records),
            "agent_mean": statistics.mean(v2_a),
            "agent_median": statistics.median(v2_a),
            "agent_min": min(v2_a),
            "agent_max": max(v2_a),
            "opp_mean": statistics.mean(v2_o),
            "opp_median": statistics.median(v2_o),
            "opp_min": min(v2_o),
            "opp_max": max(v2_o),
            "wins": v2_wins,
            "win_rate_pct": (v2_wins / len(v2_records)) * 100.0,
            "records": v2_records
        }

    # 2. Run V3 vs V48 (20 games)
    results["V3_vs_V48"] = run_match_series("AuraFarm_V3", aura_v3, "V48", wang_module, v48_seeds, 20)
    
    # 3. Run V3 vs Vicky (10 games)
    results["V3_vs_Vicky"] = run_match_series("AuraFarm_V3", aura_v3, "Vicky0718", vicky_module, vicky_seeds, 10)
    
    output_path = os.path.join(SCRATCH_DIR, "tools", "v3_benchmark_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\n==================================================")
    print(f"BENCHMARK COMPLETE. Saved to {output_path}")
    print(f"==================================================")
    print("\n--- Summary Table ---")
    print(f"{'Matchup':<25} | {'Agent Mean':<12} | {'Opp Mean':<12} | {'Win Rate':<10}")
    print("-" * 65)
    for k, v in results.items():
        print(f"{k:<25} | ${v['agent_mean']:<11,.2f} | ${v['opp_mean']:<11,.2f} | {v['win_rate_pct']:<5.1f}%")

if __name__ == "__main__":
    main()
