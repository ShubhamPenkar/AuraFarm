"""
Strong-Opponent Tournament Suite
Executes real local head-to-head simulations of AuraFarm (main.py)
against vicky0718 and wangyh666 (v48_adv12).
"""
import os
import sys
import time
import json
import statistics

SCRATCH_DIR = r"C:\Users\Sanjana\.gemini\antigravity\scratch"
sys.path.insert(0, SCRATCH_DIR)

from kaggle_environments import make
import main as aura_module

# Import Opponents
sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "vicky0718"))
import main as vicky_module

sys.path.insert(0, os.path.join(SCRATCH_DIR, "opponents", "wangyh666", "submissions"))
import v48_adv12 as wang_module

def run_tournament():
    opponents = [
        ("vicky0718", vicky_module.agent),
        ("wangyh666", wang_module.agent),
    ]
    
    games_per_opponent = 10  # 5 as P0, 5 as P1
    all_game_records = []
    
    print("=================================================================")
    print("STARTING STRONG-OPPONENT TOURNAMENT (Real Local Simulator)")
    print("=================================================================")

    for opp_name, opp_agent in opponents:
        print(f"\n--- MATCHUP: AuraFarm vs {opp_name} ({games_per_opponent} games) ---")
        
        for g in range(games_per_opponent):
            seed = 5000 + g * 123
            aura_seat = g % 2  # 0 for P0, 1 for P1
            
            # Wrapper to measure latency and verify actions
            latencies = []
            def timed_aura(obs, config=None):
                t0 = time.perf_counter()
                action = aura_module.agent(obs, config)
                dt = (time.perf_counter() - t0) * 1000.0
                latencies.append(dt)
                return action
                
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            
            if aura_seat == 0:
                players = [timed_aura, opp_agent]
            else:
                players = [opp_agent, timed_aura]
                
            t_start = time.time()
            res = env.run(players)
            dur = time.time() - t_start
            
            p_aura = res[-1][aura_seat]
            p_opp = res[-1][1 - aura_seat]
            
            aura_score = float(p_aura.reward if p_aura.reward is not None else 0.0)
            opp_score = float(p_opp.reward if p_opp.reward is not None else 0.0)
            
            crashed = (p_aura.status != "DONE")
            invalid_actions = 1 if p_aura.status == "INVALID" else 0
            
            if aura_score > opp_score:
                winner = "AURA"
            elif opp_score > aura_score:
                winner = opp_name
            else:
                winner = "TIE"
                
            mean_lat = statistics.mean(latencies) if latencies else 0.0
            max_lat = max(latencies) if latencies else 0.0
            
            record = {
                "game_idx": g + 1,
                "opponent": opp_name,
                "seed": seed,
                "aura_seat": aura_seat,
                "aura_score": aura_score,
                "opp_score": opp_score,
                "winner": winner,
                "invalid_actions": invalid_actions,
                "crashed": crashed,
                "mean_latency_ms": mean_lat,
                "max_latency_ms": max_lat,
                "duration_s": dur,
            }
            all_game_records.append(record)
            
            margin = aura_score - opp_score
            sign = "+" if margin >= 0 else ""
            print(f"Game {g+1:02d} [P{aura_seat}, Seed {seed}]: Aura=${aura_score:,.0f} | {opp_name}=${opp_score:,.0f} | Winner: {winner:<9} | Margin: {sign}${margin:,.0f} ({dur:.1f}s)")

    # Save to JSON
    json_path = os.path.join(SCRATCH_DIR, "tools", "strong_tournament_results.json")
    with open(json_path, "w") as f:
        json.dump(all_game_records, f, indent=2)
        
    print(f"\nTournament complete. Saved records to {json_path}")
    return all_game_records

if __name__ == "__main__":
    run_tournament()
