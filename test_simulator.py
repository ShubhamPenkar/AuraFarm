import time
from kaggle_environments import make

def minimal_bot(obs):
    # Parses the real observation and returns valid actions
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    
    # Simple market order: if we have wheat in shed, sell it
    market = []
    wheat_in_shed = private["shed"].get("WHEAT", 0)
    if wheat_in_shed > 0:
        market.append(["SELL", "WHEAT", wheat_in_shed])
    
    # Main farmer action: PASS
    farmer = ["PASS"]
    # Hands action: PASS for each hand
    hands = [["PASS"] for _ in me.get("hands", [])]
    
    return {"farmer": farmer, "hands": hands, "market": market}

if __name__ == "__main__":
    print("=== TEST 1: 10 Real Simulator Turns ===")
    env = make("kaggriculture", configuration={"episodeSteps": 10}, debug=True)
    res = env.run([minimal_bot, "starter"])
    print("Test 1 completed successfully! Final step:", len(res))

    print("\n=== TEST 2: Full Real Game (720 Turns) ===")
    env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=True)
    
    latencies = []
    def timed_bot(obs):
        t0 = time.perf_counter()
        action = minimal_bot(obs)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)
        return action
        
    res = env.run([timed_bot, "starter"])
    p0_final = res[-1][0]
    p1_final = res[-1][1]
    
    print(f"Full game finished!")
    print(f"Player 0 status: {p0_final.status}, reward: {p0_final.reward}")
    print(f"Player 1 status: {p1_final.status}, reward: {p1_final.reward}")
    print(f"Mean latency: {sum(latencies)/len(latencies):.3f} ms")
    print(f"Max latency: {max(latencies):.3f} ms")
