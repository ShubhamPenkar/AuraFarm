"""
Day 0 Capital Allocation Bootstrap Experiment.
Tests different Day-0 allocations (A, B, C, D, E, F) and measures their Day 10 cash and asset value.
"""
import sys, os, copy
from kaggle_environments import make

sys.path.insert(0, r"C:\Users\Sanjana\.gemini\antigravity\scratch")

# Let's inspect candidate economic return on investment
# Day 0 Capital = $3,000

candidates = {
    "A (2 Cows + 2 Sheep)": {
        "animals": {"COW": 2, "SHEEP": 2},
        "crops": {"MELON": 6, "WHEAT": 8},
        "animal_cost": 2*400 + 2*500, # 1800
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 6*20 + 8*10, # 200
        # total spent: 2262
    },
    "B (4 Sheep)": {
        "animals": {"SHEEP": 4},
        "crops": {"MELON": 4, "WHEAT": 8},
        "animal_cost": 4*500, # 2000
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 4*20 + 8*10, # 160
        # total spent: 2422
    },
    "C (4 Cows)": {
        "animals": {"COW": 4},
        "crops": {"MELON": 4, "WHEAT": 8},
        "animal_cost": 4*400, # 1600
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 4*20 + 8*10, # 160
        # total spent: 2022
    },
    "D (Mixed: 2 Cows + 1 Sheep + 2 Geese)": {
        "animals": {"COW": 2, "SHEEP": 1, "GOOSE": 2},
        "crops": {"MELON": 4, "WHEAT": 8},
        "animal_cost": 2*400 + 1*500 + 2*300, # 1900
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 4*20 + 8*10, # 160
        # total spent: 2322
    },
    "E (2 Cows + 2 Sheep + 12 Melons)": {
        "animals": {"COW": 2, "SHEEP": 2},
        "crops": {"MELON": 12, "WHEAT": 8},
        "animal_cost": 2*400 + 2*500, # 1800
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 12*20 + 8*10, # 320
        # total spent: 2382
    },
    "F (2 Cows + 2 Sheep + 16 Wheat)": {
        "animals": {"COW": 2, "SHEEP": 2},
        "crops": {"WHEAT": 16},
        "animal_cost": 2*400 + 2*500, # 1800
        "feed_buffer": 10 * 25, # 250
        "hands": 5, # 12
        "seeds": 16*10, # 160
        # total spent: 2222
    }
}

print("=== DAY-0 CANDIDATE CAPITAL ALLOCATION ANALYSIS ===")
for name, c in candidates.items():
    spent = c["animal_cost"] + c["feed_buffer"] + c["hands"] + c["seeds"]
    rem = 3000 - spent
    print(f"\nCandidate: {name}")
    print(f"  Animals: {c['animals']} (Cost: ${c['animal_cost']})")
    print(f"  Crops: {c['crops']} (Seeds: ${c['seeds']})")
    print(f"  Feed Buffer: ${c['feed_buffer']} | Hands: ${c['hands']} | Total Capex: ${spent} | Remaining Cash: ${rem}")
    
    # Calculate Day 10 theoretical yield:
    # 1. Melons: mature on Day 10. Each melon tile yields 4 units * ~$230 = $920 gross!
    melon_count = c['crops'].get('MELON', 0)
    melon_rev = melon_count * 4 * 225
    # 2. Animals product by Day 10:
    # Cow: first yield day 8, interval 2 -> yields on day 8, 10 (2 milk yields * 2 units * $85 = $340 per cow)
    cow_rev = c['animals'].get('COW', 0) * 2 * 2 * 85
    # Sheep: first yield day 6, interval 3 -> yields on day 6, 9 (2 wool yields * 2 units * $230 = $920 per sheep)
    sheep_rev = c['animals'].get('SHEEP', 0) * 2 * 2 * 230
    # Goose: first yield day 4, interval 1 -> yields on day 4,5,6,7,8,9,10 (7 egg yields * 2 units * $65 = $910 per goose)
    goose_rev = c['animals'].get('GOOSE', 0) * 7 * 2 * 65
    # Fertilizer: 1 per day per animal from day 1 to 10 = ~10 per animal * $70 = $700 per animal
    tot_animals = sum(c['animals'].values())
    fert_rev = tot_animals * 10 * 70
    
    tot_day10_gross = melon_rev + cow_rev + sheep_rev + goose_rev + fert_rev
    print(f"  Day 10 Theoretical Cumulative Gross Revenue: ${tot_day10_gross:,.2f}")
    print(f"    - Melon Revenue: ${melon_rev:,.2f}")
    print(f"    - Livestock Products: ${cow_rev + sheep_rev + goose_rev:,.2f}")
    print(f"    - Fertilizer Revenue: ${fert_rev:,.2f}")
