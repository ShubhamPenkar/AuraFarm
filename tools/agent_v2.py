"""
AuraFarm V2: Optimized Compact Production Engine
Key improvements:
- Eliminates wasteful travel overhead by concentrating high-density production in NW.
- Day 0 Melon batch (high-value premium anchor).
- Daily fast Carrot rotation for compounding cash.
- Dynamic market selling preserving town demand absorption.
"""
import math

BOARD_SIZE = 10
SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

MARKET_I0 = 10000
PRICE_FLOOR = 1
MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

HINGE_GAIN = 8.0

def _shape(func, x, T=None):
    x = max(0.0, float(x))
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log(1.0 + x)
    if func == "log10":  return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0: return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x

def market_price(item, inventory, params=None):
    p = (params or MARKET_PARAMS)[item]
    base = p["base"]
    I0 = p["I0"]
    T = p["T"]
    if inventory < I0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T, T)
        price = base + amp * _shape(f, I0 - inventory, T)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T, T)
        price = base - amp * _shape(f, inventory - I0, T)
    return max(PRICE_FLOOR, int(round(price)))

def bfs_move(start, target, board_size=BOARD_SIZE):
    sx, sy = start
    tx, ty = target
    if sx == tx and sy == ty:
        return "PASS"
    queue = [(sx, sy, None)]
    visited = {(sx, sy)}
    moves = [("NORTH", 0, -1), ("SOUTH", 0, 1), ("EAST", 1, 0), ("WEST", -1, 0)]
    while queue:
        cx, cy, first_move = queue.pop(0)
        if cx == tx and cy == ty:
            return first_move
        for m_name, dx, dy in moves:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < board_size and 0 <= ny < board_size and (nx, ny) not in visited:
                visited.add((nx, ny))
                fm = first_move if first_move is not None else m_name
                queue.append((nx, ny, fm))
    return "PASS"

def is_shed_tile(pos):
    return tuple(pos) in {(4, 4), (5, 4), (4, 5), (5, 5)}

class AuraAgentV2:
    def __init__(self):
        self.worker_targets = {}

    def plan(self, obs):
        player = obs["player"]
        farms = obs["farms"]
        me = farms[player]
        opp = farms[1 - player]
        private = obs["private"]
        market = obs["market"]
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        money = me["money"]
        tiles = me["tiles"]
        seeds = dict(private.get("seeds", {}))
        shed = dict(private.get("shed", {}))
        inventories = private.get("inventories", [{}])

        market_orders = []

        # 1. MORNING HIRING (Hour 0)
        # 2 hands daily costs only $2, giving 3 units total
        if hour == 0 and money >= 50:
            market_orders.append(["HIRE"])
            market_orders.append(["HIRE"])
            if money >= 400:
                market_orders.append(["HIRE"])  # 3rd hand costs $2

        # 2. SEED PROCUREMENT
        # Focus on NW quadrant (0..4, 0..4)
        empty_tiles = []
        for y in range(5):
            for x in range(5):
                if (x, y) != (4, 4) and tiles[y][x] is None:
                    empty_tiles.append((x, y))

        total_seeds_held = sum(seeds.values())
        seeds_needed = max(0, len(empty_tiles) - total_seeds_held)

        if seeds_needed > 0 and day < 27 and money >= 50:
            # On day 0 and day 12, buy up to 4 melons for massive yield
            current_melons = sum(1 for y in range(5) for x in range(5) if isinstance(tiles[y][x], dict) and tiles[y][x].get("crop") == "MELON")
            melon_seeds = seeds.get("MELON", 0)
            
            if (day == 0 or (day == 12 and hour < 6)) and (current_melons + melon_seeds < 4) and money >= 200:
                buy_melon = min(4 - (current_melons + melon_seeds), seeds_needed, 4)
                if buy_melon > 0 and money >= buy_melon * 80 + 50:
                    market_orders.append(["BUY_SEED", "MELON", buy_melon])
                    seeds["MELON"] = seeds.get("MELON", 0) + buy_melon
                    money -= buy_melon * 80
                    seeds_needed -= buy_melon

            # Fill all remaining tiles with Carrots
            if seeds_needed > 0 and money >= 50:
                buy_carrot = min(seeds_needed, int((money - 20) // 20), 10 - len(market_orders))
                if buy_carrot > 0:
                    market_orders.append(["BUY_SEED", "CARROT", buy_carrot])
                    seeds["CARROT"] = seeds.get("CARROT", 0) + buy_carrot
                    money -= buy_carrot * 20

        # 3. MARKET SALES
        for item, count in shed.items():
            if count <= 0 or len(market_orders) >= 10:
                continue
            item_price = market.get("prices", {}).get(item, 0)
            base_p = MARKET_PARAMS.get(item, {}).get("base", 20)
            
            # Sells: liquidate completely at day >= 28, or sell when price is healthy
            if day >= 28 or item_price >= base_p * 0.70:
                sell_amt = min(count, 10 - len(market_orders))
                if sell_amt > 0:
                    market_orders.append(["SELL", item, sell_amt])

        # 4. WORKER SCHEDULING
        all_workers = [me["farmer"]] + list(me.get("hands", []))
        worker_actions = []

        harvest_tiles = []
        water_tiles = []
        weed_tiles = []

        for y in range(5):
            for x in range(5):
                tile = tiles[y][x]
                if isinstance(tile, dict):
                    kind = tile.get("kind")
                    if kind == "PLANT":
                        c_spec = CROPS[tile["crop"]]
                        age = day - tile["planted_day"]
                        if tile.get("yield_units", 0) > 0 and (age >= c_spec["max_yield_day"] or c_spec["ongoing"] or day >= 28):
                            harvest_tiles.append((x, y))
                        elif not tile.get("watered_today", False):
                            water_tiles.append((x, y))
                    elif kind == "WEED":
                        weed_tiles.append((x, y))

        seeds_to_plant = dict(seeds)
        assigned_tasks = set()

        for w_idx, pos in enumerate(all_workers):
            wx, wy = pos[0], pos[1]
            tile = tiles[wy][wx]
            w_inv = inventories[w_idx] if w_idx < len(inventories) else {}
            has_produce = sum(w_inv.values()) > 0

            # Action 1: On-tile harvest/water
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                c_spec = CROPS[tile["crop"]]
                age = day - tile["planted_day"]
                if tile.get("yield_units", 0) > 0 and (age >= c_spec["max_yield_day"] or c_spec["ongoing"] or day >= 28):
                    worker_actions.append(["HARVEST"])
                    continue
                if not tile.get("watered_today", False):
                    worker_actions.append(["WATER"])
                    continue

            # Action 2: On-tile weed clear
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                worker_actions.append(["DIG"])
                continue

            # Action 3: Shed drop if carrying produce
            if is_shed_tile((wx, wy)) and has_produce:
                worker_actions.append(["DROP"])
                continue

            # Action 4: Plant if on empty tile
            if tile is None and day < 27:
                planted = False
                # Prioritize planting Melon if available, else Carrot
                for pref_crop in ["MELON", "CARROT", "WHEAT"]:
                    if seeds_to_plant.get(pref_crop, 0) > 0:
                        worker_actions.append(["PLANT", pref_crop])
                        seeds_to_plant[pref_crop] -= 1
                        planted = True
                        break
                if planted:
                    continue

            # Action 5: Move to highest priority target
            target = None
            min_dist = 999

            # Harvest targets
            for tx, ty in harvest_tiles:
                if (tx, ty) not in assigned_tasks:
                    d = abs(wx - tx) + abs(wy - ty)
                    if d < min_dist:
                        min_dist = d
                        target = (tx, ty)

            # Water targets
            if target is None:
                for tx, ty in water_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            # Plant targets
            if target is None and sum(seeds_to_plant.values()) > 0 and day < 27:
                for tx, ty in empty_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            # Weed targets
            if target is None:
                for tx, ty in weed_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            # Shed drop target
            if target is None and has_produce:
                target = (4, 4)

            if target is not None:
                assigned_tasks.add(target)
                move = bfs_move((wx, wy), target)
                worker_actions.append([move])
            else:
                worker_actions.append(["PASS"])

        farmer_action = worker_actions[0] if worker_actions else ["PASS"]
        hands_actions = worker_actions[1:] if len(worker_actions) > 1 else []

        return {
            "farmer": farmer_action,
            "hands": hands_actions,
            "market": market_orders[:10]
        }

_GLOBAL_AGENT = None

def agent(obs, config=None):
    global _GLOBAL_AGENT
    if _GLOBAL_AGENT is None or obs.get("step", 0) == 0:
        _GLOBAL_AGENT = AuraAgentV2()
    try:
        return _GLOBAL_AGENT.plan(obs)
    except Exception as e:
        return {"farmer": ["PASS"], "hands": [], "market": []}
