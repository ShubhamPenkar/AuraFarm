"""
Head-to-head tournament runner:
- V1 vs V48 (20 games on identical paired seeds & seats)
- V2 vs V48 (20 games on identical paired seeds & seats)
- V3 vs V48 (20 games on identical paired seeds & seats)
- V3 vs Vicky0718 (10 games on paired seeds & seats)
"""
import os
import sys
import time
import json
import statistics

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, SCRATCH_DIR)

from kaggle_environments import make

import main_v1 as aura_v1
import main_v2 as aura_v2
import main_v3 as aura_v3

# Opponents
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "vicky0718"))
import main as vicky_module

def run_matchup(agent_name, agent_mod, opp_name, opp_mod, seeds, num_games):
    records = []
    print(f"\n==================================================")
    print(f"RUNNING MATCHUP: {agent_name} vs {opp_name} ({num_games} games)")
    print(f"==================================================")
    
    for idx, seed in enumerate(seeds[:num_games]):
        seat = 0 if idx < (num_games // 2) else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        players = [agent_mod.agent, opp_mod.agent] if seat == 0 else [opp_mod.agent, agent_mod.agent]
        
        t0 = time.time()
        res = env.run(players)
        dur = time.time() - t0
        
        s_aura = float(res[-1][seat].reward or 0.0)
        s_opp = float(res[-1][1 - seat].reward or 0.0)
        crashed = res[-1][seat].status != "DONE"
        invalid = 1 if res[-1][seat].status == "INVALID" else 0
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
            "crashed": crashed,
            "invalid": invalid,
            "duration_s": dur
        }
        records.append(rec)
        print(f"Game {idx+1:02d} (Seed {seed}, Seat {seat}): {agent_name}=${s_aura:,.2f} | {opp_name}=${s_opp:,.2f} -> Winner: {winner} ({dur:.1f}s)")
        
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
    
    # 1. V1 vs V48 (20 games)
    results["V1_vs_V48"] = run_matchup("AuraFarm_V1", aura_v1, "V48", wang_module, v48_seeds, 20)
    
    # 2. V2 vs V48 (20 games)
    results["V2_vs_V48"] = run_matchup("AuraFarm_V2", aura_v2, "V48", wang_module, v48_seeds, 20)
    
    # 3. V3 vs V48 (20 games)
    results["V3_vs_V48"] = run_matchup("AuraFarm_V3", aura_v3, "V48", wang_module, v48_seeds, 20)
    
    # 4. V3 vs Vicky (10 games)
    results["V3_vs_Vicky"] = run_matchup("AuraFarm_V3", aura_v3, "Vicky0718", vicky_module, vicky_seeds, 10)
    
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
