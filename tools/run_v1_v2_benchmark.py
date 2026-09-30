"""
Mandatory Comparative Tournament: AuraFarm V1 vs V2 against V48 (wangyh666) and Vicky0718.
Uses identical paired seeds and seats for both versions.
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

# Opponent imports
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "vicky0718"))
import main as vicky_module

def run_suite():
    v48_seeds = [1000 + i * 77 for i in range(20)]
    vicky_seeds = [2000 + i * 53 for i in range(10)]
    
    all_records = []
    
    print("=========================================================================")
    print("STARTING MANDATORY COMPARATIVE BENCHMARK: V1 vs V2")
    print("=========================================================================")

    # --------------------------------------------------------------------------
    # 1. AuraFarm V1 vs V48 (20 games: 10 as P0, 10 as P1)
    # --------------------------------------------------------------------------
    print("\n--- 1. AuraFarm V1 vs V48 (20 games) ---")
    for idx, seed in enumerate(v48_seeds):
        seat = 0 if idx < 10 else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        players = [aura_v1.agent, wang_module.agent] if seat == 0 else [wang_module.agent, aura_v1.agent]
        t0 = time.time()
        res = env.run(players)
        dur = time.time() - t0
        
        s_aura = float(res[-1][seat].reward or 0.0)
        s_opp = float(res[-1][1 - seat].reward or 0.0)
        crashed = res[-1][seat].status != "DONE"
        invalid = 1 if res[-1][seat].status == "INVALID" else 0
        winner = "AURA_V1" if s_aura > s_opp else ("V48" if s_opp > s_aura else "TIE")
        
        rec = {
            "version": "V1",
            "opponent": "V48",
            "game_idx": idx + 1,
            "seed": seed,
            "aura_seat": seat,
            "aura_score": s_aura,
            "opp_score": s_opp,
            "winner": winner,
            "crashed": crashed,
            "invalid_actions": invalid,
            "duration": dur
        }
        all_records.append(rec)
        print(f"V1 vs V48 G{idx+1:02d} [P{seat}, Seed {seed}]: V1=${s_aura:,.0f} | V48=${s_opp:,.0f} | Winner: {winner} ({dur:.1f}s)")

    # --------------------------------------------------------------------------
    # 2. AuraFarm V2 vs V48 (20 games: 10 as P0, 10 as P1, IDENTICAL SEEDS)
    # --------------------------------------------------------------------------
    print("\n--- 2. AuraFarm V2 vs V48 (20 games, identical seeds) ---")
    for idx, seed in enumerate(v48_seeds):
        seat = 0 if idx < 10 else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        players = [aura_v2.agent, wang_module.agent] if seat == 0 else [wang_module.agent, aura_v2.agent]
        t0 = time.time()
        res = env.run(players)
        dur = time.time() - t0
        
        s_aura = float(res[-1][seat].reward or 0.0)
        s_opp = float(res[-1][1 - seat].reward or 0.0)
        crashed = res[-1][seat].status != "DONE"
        invalid = 1 if res[-1][seat].status == "INVALID" else 0
        winner = "AURA_V2" if s_aura > s_opp else ("V48" if s_opp > s_aura else "TIE")
        
        rec = {
            "version": "V2",
            "opponent": "V48",
            "game_idx": idx + 1,
            "seed": seed,
            "aura_seat": seat,
            "aura_score": s_aura,
            "opp_score": s_opp,
            "winner": winner,
            "crashed": crashed,
            "invalid_actions": invalid,
            "duration": dur
        }
        all_records.append(rec)
        print(f"V2 vs V48 G{idx+1:02d} [P{seat}, Seed {seed}]: V2=${s_aura:,.0f} | V48=${s_opp:,.0f} | Winner: {winner} ({dur:.1f}s)")

    # --------------------------------------------------------------------------
    # 3. AuraFarm V1 vs Vicky0718 (10 games: 5 as P0, 5 as P1)
    # --------------------------------------------------------------------------
    print("\n--- 3. AuraFarm V1 vs Vicky0718 (10 games) ---")
    for idx, seed in enumerate(vicky_seeds):
        seat = 0 if idx < 5 else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        players = [aura_v1.agent, vicky_module.agent] if seat == 0 else [vicky_module.agent, aura_v1.agent]
        t0 = time.time()
        res = env.run(players)
        dur = time.time() - t0
        
        s_aura = float(res[-1][seat].reward or 0.0)
        s_opp = float(res[-1][1 - seat].reward or 0.0)
        crashed = res[-1][seat].status != "DONE"
        invalid = 1 if res[-1][seat].status == "INVALID" else 0
        winner = "AURA_V1" if s_aura > s_opp else ("Vicky" if s_opp > s_aura else "TIE")
        
        rec = {
            "version": "V1",
            "opponent": "Vicky",
            "game_idx": idx + 1,
            "seed": seed,
            "aura_seat": seat,
            "aura_score": s_aura,
            "opp_score": s_opp,
            "winner": winner,
            "crashed": crashed,
            "invalid_actions": invalid,
            "duration": dur
        }
        all_records.append(rec)
        print(f"V1 vs Vicky G{idx+1:02d} [P{seat}, Seed {seed}]: V1=${s_aura:,.0f} | Vicky=${s_opp:,.0f} | Winner: {winner} ({dur:.1f}s)")

    # --------------------------------------------------------------------------
    # 4. AuraFarm V2 vs Vicky0718 (10 games: 5 as P0, 5 as P1, IDENTICAL SEEDS)
    # --------------------------------------------------------------------------
    print("\n--- 4. AuraFarm V2 vs Vicky0718 (10 games, identical seeds) ---")
    for idx, seed in enumerate(vicky_seeds):
        seat = 0 if idx < 5 else 1
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        players = [aura_v2.agent, vicky_module.agent] if seat == 0 else [vicky_module.agent, aura_v2.agent]
        t0 = time.time()
        res = env.run(players)
        dur = time.time() - t0
        
        s_aura = float(res[-1][seat].reward or 0.0)
        s_opp = float(res[-1][1 - seat].reward or 0.0)
        crashed = res[-1][seat].status != "DONE"
        invalid = 1 if res[-1][seat].status == "INVALID" else 0
        winner = "AURA_V2" if s_aura > s_opp else ("Vicky" if s_opp > s_aura else "TIE")
        
        rec = {
            "version": "V2",
            "opponent": "Vicky",
            "game_idx": idx + 1,
            "seed": seed,
            "aura_seat": seat,
            "aura_score": s_aura,
            "opp_score": s_opp,
            "winner": winner,
            "crashed": crashed,
            "invalid_actions": invalid,
            "duration": dur
        }
        all_records.append(rec)
        print(f"V2 vs Vicky G{idx+1:02d} [P{seat}, Seed {seed}]: V2=${s_aura:,.0f} | Vicky=${s_opp:,.0f} | Winner: {winner} ({dur:.1f}s)")

    # Save to JSON
    out_file = os.path.join(SCRATCH_DIR, "tools", "v1_v2_comparative_benchmark.json")
    with open(out_file, "w") as f:
        json.dump(all_records, f, indent=2)
    print(f"\nAll benchmark matches finished. Results saved to {out_file}")

if __name__ == "__main__":
    run_suite()
