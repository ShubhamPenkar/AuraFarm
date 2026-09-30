"""
AuraFarm V2: Town-Shop Demand Router & Market Scarcity Exploiter
Standard Library Only. Sub-second execution guarantee (<1 ms/step).
Preserves V1 baseline while incorporating town demand routing & quadratic hinge price exploitation.
"""

import math

# ==============================================================================
# 1. OFFICIAL CONSTANTS & SPECIFICATIONS (From kaggriculture.py)
# ==============================================================================
BOARD_SIZE = 10
SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

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

# ==============================================================================
# 2. EXACT MARKET PRICING (Line-for-line mirror of kaggriculture.py)
# ==============================================================================
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

# ==============================================================================
# 3. TOWN DEMAND & SCARCITY ENGINE
# ==============================================================================
class TownDemandEngine:
    @staticmethod
    def analyze_demand(unlocked_shops):
        """Calculates exact town daily consumption rates for each commodity."""
        daily_consumption = {p: 1 for p in PRODUCTS}  # Town center consumes 1/day
        for shop in unlocked_shops:
            products = SHOPS.get(shop, [])
            mult = 2 if len(products) == 1 else 1
            for p in products:
                # 6 ticks per 24-hour day
                daily_consumption[p] = daily_consumption.get(p, 0) + (6 * mult)
        return daily_consumption

# ==============================================================================
# 4. AURA FARM V2 CONTROLLER
# ==============================================================================
class AuraFarmV2Controller:
    def __init__(self):
        self.assigned_targets = {}

    def select_crop_portfolio(self, day, market_inv, town_demand, opp_crops):
        """Scores candidate crops based on shop synergy, quadratic hinge scarcity, and turnover."""
        remaining_days = 29 - day
        best_crop = "CARROT"
        best_score = -1e9

        for crop, spec in CROPS.items():
            grow_time = spec["max_yield_day"] if not spec["ongoing"] else spec["first_yield_day"]
            if grow_time > remaining_days:
                continue

            demand_rate = town_demand.get(crop, 1)
            curr_inv = market_inv.get(crop, MARKET_I0)
            p_param = MARKET_PARAMS[crop]
            
            # Forecast inventory drain over growth window
            future_drain = demand_rate * (grow_time / 24.0)
            opp_supply = opp_crops.get(crop, 0) * 3  # Approximate heuristic
            projected_inv = curr_inv - future_drain + opp_supply

            exp_price = market_price(crop, projected_inv)
            expected_yield = 3 if crop == "CARROT" else (4 if crop == "WHEAT" else (6 if crop == "MELON" else 4))
            
            net_profit_per_day = ((expected_yield * exp_price) - spec["seed"]) / float(grow_time)

            # Bonus for crops with quadratic hinge pricing when town demand is high
            if p_param["below_func"] == "hinge" and demand_rate >= 7:
                net_profit_per_day *= 1.4

            # Extra weight on rapid cash recycling in early game (Days 0-9)
            if crop == "CARROT" and day < 10:
                net_profit_per_day *= 1.2

            if net_profit_per_day > best_score:
                best_score = net_profit_per_day
                best_crop = crop

        return best_crop

    def plan(self, obs):
        player = obs["player"]
        farms = obs["farms"]
        me = farms[player]
        opp = farms[1 - player]
        private = obs["private"]
        market = obs["market"]
        town = obs.get("town", {})
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        money = me["money"]
        tiles = me["tiles"]
        seeds = dict(private.get("seeds", {}))
        shed = dict(private.get("shed", {}))
        inventories = private.get("inventories", [{}])

        unlocked_shops = town.get("unlocked_shops", [])
        town_demand = TownDemandEngine.analyze_demand(unlocked_shops)

        # Track opponent commitments (heuristic)
        opp_crops = {}
        for row in opp.get("tiles", []):
            for t in row:
                if isinstance(t, dict) and t.get("kind") == "PLANT":
                    c = t.get("crop")
                    opp_crops[c] = opp_crops.get(c, 0) + 1

        market_orders = []

        # ----------------------------------------------------------------------
        # LAYER 1: LAND EXPANSION
        # ----------------------------------------------------------------------
        # Unlocks NE quadrant when bank >= $2500 and midgame has arrived
        if "NE" not in me.get("unlocked_quadrants", []) and money >= 2500 and day < 18:
            market_orders.append(["BUY_LAND"])
            money -= 1000

        # ----------------------------------------------------------------------
        # LAYER 2: MORNING HIRING (Fibonacci Cost Curve)
        # ----------------------------------------------------------------------
        if hour == 0 and money >= 100:
            market_orders.append(["HIRE"])
            market_orders.append(["HIRE"])
            if money >= 500:
                market_orders.append(["HIRE"])

        # ----------------------------------------------------------------------
        # LAYER 3: DYNAMIC SEED PROCUREMENT
        # ----------------------------------------------------------------------
        empty_tiles = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                if tiles[y][x] is None:
                    empty_tiles.append((x, y))

        total_seeds_held = sum(seeds.values())
        seeds_needed = max(0, len(empty_tiles) - total_seeds_held)

        if seeds_needed > 0 and day < 27 and money >= 80:
            best_crop = self.select_crop_portfolio(day, market.get("inventory", {}), town_demand, opp_crops)
            seed_price = CROPS[best_crop]["seed"]
            buy_qty = min(seeds_needed, int((money - 80) // seed_price), 10)
            if buy_qty > 0:
                market_orders.append(["BUY_SEED", best_crop, buy_qty])
                seeds[best_crop] = seeds.get(best_crop, 0) + buy_qty
                money -= buy_qty * seed_price

        # ----------------------------------------------------------------------
        # LAYER 4: SCARCITY-AWARE MARKET CONTROLLER
        # ----------------------------------------------------------------------
        # Avoid premature dumping: hold inventory if town demand is actively driving price up
        for item, count in shed.items():
            if count <= 0 or len(market_orders) >= 10:
                continue
            
            item_price = market.get("prices", {}).get(item, 0)
            base_p = MARKET_PARAMS.get(item, {}).get("base", 20)
            curr_inv = market.get("inventory", {}).get(item, MARKET_I0)
            p_param = MARKET_PARAMS.get(item, {})
            T = p_param.get("T", 400)
            
            u = max(0.0, (MARKET_I0 - curr_inv) / float(T))
            is_endgame = (day >= 28)
            
            should_sell = False
            if is_endgame:
                should_sell = True
            elif item_price >= base_p * 1.4:
                should_sell = True  # Capture the scarcity spike!
            elif sum(shed.values()) >= 70 and item_price >= base_p * 0.90:
                should_sell = True  # Shed relief
            elif u < 0.2 and item_price >= base_p * 0.85:
                should_sell = True  # Baseline non-scarce profit

            if should_sell:
                sell_amt = min(count, 5, 10 - len(market_orders))
                if sell_amt > 0:
                    market_orders.append(["SELL", item, sell_amt])

        # ----------------------------------------------------------------------
        # LAYER 5: CLUSTER-BASED WORKER DISPATCH
        # ----------------------------------------------------------------------
        all_workers = [me["farmer"]] + list(me.get("hands", []))
        worker_actions = []

        harvest_tiles = []
        water_tiles = []
        weed_tiles = []

        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
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

        seeds_available_to_plant = dict(seeds)
        assigned_tasks = set()

        for w_idx, pos in enumerate(all_workers):
            wx, wy = pos[0], pos[1]
            tile = tiles[wy][wx]
            w_inv = inventories[w_idx] if w_idx < len(inventories) else {}
            has_produce = sum(w_inv.values()) > 0

            # Step 1: Immediate on-tile action (0 movement turns)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                c_spec = CROPS[tile["crop"]]
                age = day - tile["planted_day"]
                if tile.get("yield_units", 0) > 0 and (age >= c_spec["max_yield_day"] or c_spec["ongoing"] or day >= 28):
                    worker_actions.append(["HARVEST"])
                    continue
                if not tile.get("watered_today", False):
                    worker_actions.append(["WATER"])
                    continue

            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                worker_actions.append(["DIG"])
                continue

            # Step 2: Drop if already shed-adjacent and carrying items
            if is_shed_tile((wx, wy)) and has_produce:
                worker_actions.append(["DROP"])
                continue

            # Step 3: Plant on empty tile
            if tile is None and day < 27:
                planted = False
                for c_name, c_cnt in seeds_available_to_plant.items():
                    if c_cnt > 0:
                        worker_actions.append(["PLANT", c_name])
                        seeds_available_to_plant[c_name] -= 1
                        planted = True
                        break
                if planted:
                    continue

            # Step 4: BFS navigation to nearest task in worker's local cluster
            target = None
            min_dist = 999

            for tx, ty in harvest_tiles:
                if (tx, ty) not in assigned_tasks:
                    d = abs(wx - tx) + abs(wy - ty)
                    if d < min_dist:
                        min_dist = d
                        target = (tx, ty)

            if target is None:
                for tx, ty in water_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            if target is None and sum(seeds_available_to_plant.values()) > 0 and day < 27:
                for tx, ty in empty_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            if target is None:
                for tx, ty in weed_tiles:
                    if (tx, ty) not in assigned_tasks:
                        d = abs(wx - tx) + abs(wy - ty)
                        if d < min_dist:
                            min_dist = d
                            target = (tx, ty)

            # Shed drop only when inventory is full or in late afternoon (hour >= 20)
            if target is None and has_produce and (sum(w_inv.values()) >= 15 or hour >= 20):
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

# ==============================================================================
# 5. ENTRY POINT
# ==============================================================================
_GLOBAL_V2 = None

def agent(obs, config=None):
    global _GLOBAL_V2
    if _GLOBAL_V2 is None or obs.get("step", 0) == 0:
        _GLOBAL_V2 = AuraFarmV2Controller()
    try:
        return _GLOBAL_V2.plan(obs)
    except Exception:
        return {"farmer": ["PASS"], "hands": [], "market": []}
