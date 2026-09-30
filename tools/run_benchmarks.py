"""
Official Benchmark Suite for Kaggriculture Agent
Runs 20 games vs starter and 20 games vs random, alternating player seats.
"""
import os
import sys
import time
import json
import statistics
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kaggle_environments import make
import agent_v1 as ag

def run_tournament():
    opponents = ["starter", "random"]
    games_per_opp = 20
    all_results = []

    print(f"Starting Benchmark: {games_per_opp} games vs starter, {games_per_opp} games vs random...")
    
    total_start = time.time()
    
    for opp_name in opponents:
        opp_results = []
        print(f"\n==========================================")
        print(f"BENCHMARKING AGAINST: {opp_name.upper()} ({games_per_opp} games)")
        print(f"==========================================")
        
        for g in range(games_per_opp):
            seed = 42 + g * 101
            seat = g % 2  # Alternate seats: 0 = P0, 1 = P1
            
            # Wrap agent with latency timer
            latencies = []
            def timed_agent(obs, config=None):
                t0 = time.perf_counter()
                action = ag.agent(obs, config)
                dt = (time.perf_counter() - t0) * 1000.0
                latencies.append(dt)
                return action

            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            
            players = [timed_agent, opp_name] if seat == 0 else [opp_name, timed_agent]
            
            t_game = time.time()
            res = env.run(players)
            game_dur = time.time() - t_game
            
            p_my = res[-1][seat]
            p_opp = res[-1][1 - seat]
            
            my_score = float(p_my.reward if p_my.reward is not None else 0.0)
            opp_score = float(p_opp.reward if p_opp.reward is not None else 0.0)
            win = my_score > opp_score
            tie = my_score == opp_score
            
            # Check for crashes or invalid status
            crashed = (p_my.status != "DONE")
            mean_lat = statistics.mean(latencies) if latencies else 0.0
            max_lat = max(latencies) if latencies else 0.0
            
            record = {
                "opponent": opp_name,
                "game": g + 1,
                "seat": seat,
                "seed": seed,
                "my_score": my_score,
                "opp_score": opp_score,
                "win": win,
                "tie": tie,
                "crashed": crashed,
                "game_duration": game_dur,
                "mean_latency_ms": mean_lat,
                "max_latency_ms": max_lat,
            }
            opp_results.append(record)
            all_results.append(record)
            
            win_str = "WIN" if win else ("TIE" if tie else "LOSS")
            print(f"Game {g+1:02d} [Seat P{seat}, Seed {seed}]: AuraFarm=${my_score:,.0f} vs {opp_name.capitalize()}=${opp_score:,.0f} -> {win_str} (mean {mean_lat:.2f}ms, dur {game_dur:.1f}s)")
            
    total_time = time.time() - total_start
    print(f"\nAll benchmarks finished in {total_time:.1f}s.")
    
    # Save full results to JSON
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
        
    return all_results

if __name__ == "__main__":
    run_tournament()
