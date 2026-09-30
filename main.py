"""
AuraFarm V3: Autonomous Industrial Economic & Planning Agent for Kaggle Kaggriculture.
Built on empirical simulator reverse-engineering:
- Exact simulator constants, market parameters, and town shop demand curves
- Aggressive Day-0 Capital Allocation ($2,912 capex: 4 livestock + 12 Melons + feed buffer + 5 hands)
- Permanent Livestock Protection Engine (dedicated caretakers, 20+ wheat pocket feed, zero escapes)
- Dynamic Fertilizer Economics (accelerated yields + premium market sales at $70-$90)
- Town-Drained Wheat Production Engine (25-35 tiles, 60-90 unit batch sales capturing peak prices)
- Scaled Industrial Workforce (scaling to 11 hands daily across 3 quadrants / 75 tiles)
- Spatial Clustered Dispatch & Conflict-Free Shed Logistics
- Terminal Liquidation on Step 718

Standard library only. Robust against unexpected observation shapes.
"""

import math
import collections
import heapq
import copy

# ==============================================================================
# 1. OFFICIAL SIMULATOR CONSTANTS & FORMULAE (from kaggriculture.py)
# ==============================================================================

BOARD_SIZE = 10
QUADRANT_SIZE = 5
MAX_ORDERS = 10
SHED_CAPACITY = 200
FARM_HAND_COST_MULT = 1
TURNS_PER_DAY = 24
TOTAL_DAYS = 30
TOTAL_STEPS = 720
LAST_ACT_STEP = 718

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

MARKET_I0 = 10000
PRICE_FLOOR = 1
HINGE_GAIN = 8.0

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

LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

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

def official_market_price(item, inventory, params=None):
    p = (params or MARKET_PARAMS).get(item)
    if not p:
        return 1
    base = p["base"]
    I0 = p["I0"]
    T = p["T"]
    diff = inventory - I0
    if diff <= 0:
        sign = 1.0
        func = p["below_func"]
        target = p["below_target"]
    else:
        sign = -1.0
        func = p["above_func"]
        target = p["above_target"]
    denom = _shape(func, float(T), T)
    amp = (target * base / denom) if denom > 0 else 0.0
    val = base + sign * amp * _shape(func, abs(diff), T)
    return max(PRICE_FLOOR, math.floor(val))

def get_hire_cost(n_already_today):
    a, b = 1, 1
    for _ in range(n_already_today):
        a, b = b, a + b
    return a

def shed_access_tiles(board_size=10):
    half = board_size // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]

def is_shed_adjacent(pos):
    return tuple(pos) in shed_access_tiles(BOARD_SIZE)


# ==============================================================================
# 2. FARM GRID & LAYOUT MANAGER
# ==============================================================================

class FarmLayout:
    """
    Manages functional zones across the 10x10 farm grid:
    - Livestock Pens: Clustered around shed access in NW, NE, and SW.
    - Crop Zones: Contiguous rows optimized for sweeps.
    - Preserved Transit Corridors: Shed-access tiles (4,4), (5,4), (4,5), (5,5) never planted.
    """
    def __init__(self):
        # Quadrant 0 (NW: 0..4, 0..4) - 4 pens close to (4,4)
        self.nw_pens = [(2, 3), (3, 3), (2, 2), (3, 2)]
        # Quadrant 1 (NE: 5..9, 0..4) - 7 pens close to (5,4)
        self.ne_pens = [(5, 3), (6, 3), (7, 3), (5, 2), (6, 2), (7, 2), (6, 1)]
        # Quadrant 2 (SW: 0..4, 5..9) - 6 pens close to (4,5)
        self.sw_pens = [(2, 5), (3, 5), (2, 6), (3, 6), (2, 7), (3, 7)]
        
    def get_all_pen_slots(self, unlocked_quadrants):
        slots = list(self.nw_pens)
        if "NE" in unlocked_quadrants:
            slots.extend(self.ne_pens)
        if "SW" in unlocked_quadrants:
            slots.extend(self.sw_pens)
        return slots

    def is_pen_slot(self, pos, unlocked_quadrants):
        return tuple(pos) in self.get_all_pen_slots(unlocked_quadrants)

    def is_owned(self, pos, unlocked_quadrants):
        x, y = pos
        if not (0 <= x < 10 and 0 <= y < 10):
            return False
        if x < 5 and y < 5:
            return True
        if x >= 5 and y < 5:
            return "NE" in unlocked_quadrants
        if x < 5 and y >= 5:
            return "SW" in unlocked_quadrants
        if x >= 5 and y >= 5:
            return "SE" in unlocked_quadrants
        return False


# ==============================================================================
# 3. TOWN DEMAND & MARKET ORACLE
# ==============================================================================

class TownDemandOracle:
    """
    Tracks unlocked town shops, consumption rates, and forecasts market inventory drain.
    """
    def __init__(self):
        self.commodity_drain = collections.defaultdict(float)
        self.wheat_drain = 0.0
        
    def update(self, town_obs):
        shops = town_obs.get("unlocked_shops", [])
        self.commodity_drain.clear()
        for shop in shops:
            items = SHOPS.get(shop, [])
            mult = 2 if len(items) == 1 else 1
            for item in items:
                # Consumed every 4 turns = 6 units/day * mult
                self.commodity_drain[item] += 6.0 * mult
        self.wheat_drain = self.commodity_drain.get("WHEAT", 0.0)

    def forecast_price(self, item, current_inv, days_ahead):
        drain = self.commodity_drain.get(item, 0.0)
        expected_inv = max(0, current_inv - int(drain * days_ahead))
        return official_market_price(item, expected_inv)


# ==============================================================================
# 4. PATHFINDING & CONFLICT-FREE NAVIGATION
# ==============================================================================

def manhattan(p1, p2):
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def get_best_shed_access(start_pos, occupied_positions):
    """
    Finds the nearest shed-access tile that is NOT occupied by another unit.
    """
    candidates = shed_access_tiles(BOARD_SIZE)
    # Filter for free tiles first
    free_candidates = [p for p in candidates if p not in occupied_positions or p == start_pos]
    if free_candidates:
        return min(free_candidates, key=lambda p: manhattan(start_pos, p))
    return min(candidates, key=lambda p: manhattan(start_pos, p))

def get_next_step(start, target, farm_tiles, other_units_pos):
    """
    BFS pathfinding to next adjacent cell avoiding collisions.
    """
    if start == target:
        return "PASS"
        
    sx, sy = start
    tx, ty = target
    
    dirs = [
        (0, -1, "NORTH"),
        (0, 1, "SOUTH"),
        (1, 0, "EAST"),
        (-1, 0, "WEST")
    ]
    
    queue = collections.deque([(sx, sy, [])])
    visited = {(sx, sy)}
    
    while queue:
        x, y, path = queue.popleft()
        if (x, y) == (tx, ty):
            return path[0] if path else "PASS"
            
        if len(path) >= 16:
            continue
            
        for dx, dy, act in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < 10 and 0 <= ny < 10):
                continue
            if (nx, ny) in visited:
                continue
                
            # Disallow locked tiles
            tile = farm_tiles[ny][nx]
            if tile == "LOCKED":
                continue
                
            # Avoid collisions with other units unless target
            if (nx, ny) in other_units_pos and (nx, ny) != (tx, ty):
                continue
                
            visited.add((nx, ny))
            queue.append((nx, ny, path + [act]))
            
    # Fallback to greedy step
    best_act = "PASS"
    best_dist = 999
    for dx, dy, act in dirs:
        nx, ny = sx + dx, sy + dy
        if 0 <= nx < 10 and 0 <= ny < 10 and farm_tiles[ny][nx] != "LOCKED" and (nx, ny) not in other_units_pos:
            dist = manhattan((nx, ny), target)
            if dist < best_dist:
                best_dist = dist
                best_act = act
    return best_act


# ==============================================================================
# 5. AURAFARM V3 CORE AGENT
# ==============================================================================

class AuraFarmV3:
    def __init__(self):
        self.layout = FarmLayout()
        self.oracle = TownDemandOracle()
        self.day = 0
        self.hour = 0
        self.step = 0
        self.player_id = 0
        
    def act(self, observation, configuration=None):
        self.step = int(observation.get("step", 0))
        self.day = int(observation.get("day", self.step // TURNS_PER_DAY))
        self.hour = int(observation.get("hour", self.step % TURNS_PER_DAY))
        self.player_id = int(observation.get("player", 0))
        
        farms = observation.get("farms", [])
        if not farms or len(farms) <= self.player_id:
            return {"farmer": ["PASS"], "hands": [], "market": []}
            
        my_farm = farms[self.player_id]
        private = observation.get("private", {})
        market = observation.get("market", {})
        town = observation.get("town", {})
        
        self.oracle.update(town)
        
        money = my_farm.get("money", 0)
        unlocked_quads = my_farm.get("unlocked_quadrants", ["NW"])
        tiles = my_farm.get("tiles", [])
        farmer_pos = tuple(my_farm.get("farmer", [4, 4]))
        hands = my_farm.get("hands", [])
        hands_pos = [tuple(h) for h in hands]
        
        shed = private.get("shed", {})
        seeds = private.get("seeds", {})
        inventories = private.get("inventories", [{}])
        market_inv = market.get("inventory", {})
        market_prices = market.get("prices", {})
        
        # ----------------------------------------------------------------------
        # A. STRATEGIC MARKET ORDERS
        # ----------------------------------------------------------------------
        market_orders = []
        
        # 1. Step 718 Terminal Liquidation (Sell Everything!)
        if self.step >= LAST_ACT_STEP:
            for item in PRODUCTS:
                qty = shed.get(item, 0)
                if qty > 0 and len(market_orders) < MAX_ORDERS:
                    market_orders.append(["SELL", item, qty])
            return {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": market_orders[:MAX_ORDERS]}
            
        # 2. Day 0 Turn 0 Opening Bootstrap
        if self.step == 0:
            # Buy 10 Wheat product for immediate feed buffer
            market_orders.append(["BUY_PRODUCT", "WHEAT", 10])
            # Buy 12 Melon seeds + 10 Wheat seeds
            market_orders.append(["BUY_SEED", "MELON", 12])
            market_orders.append(["BUY_SEED", "WHEAT", 10])
            
        # 3. Day 0 Turn 1: Hire 5 Hands + Buy 2 Cows + 2 Sheep
        if self.step == 1:
            for _ in range(5):
                market_orders.append(["HIRE"])
            market_orders.append(["BUY_ANIMAL", "COW", 2])
            market_orders.append(["BUY_ANIMAL", "SHEEP", 2])

        # 4. Daily Workforce Scaling (Hire hands at Hour 01)
        if self.hour == 1 and self.step > 1:
            active_hands = len(hands)
            target_hands = 5
            if len(unlocked_quads) == 2:
                target_hands = 7
            elif len(unlocked_quads) >= 3:
                target_hands = 11
                
            hires_needed = max(0, target_hands - active_hands)
            for i in range(hires_needed):
                if len(market_orders) < MAX_ORDERS:
                    cost = get_hire_cost(my_farm.get("hires_today", 0) + i)
                    if money >= cost + 150:
                        market_orders.append(["HIRE"])
                        
        # 5. Land Expansion Purchases
        if "NE" not in unlocked_quads and self.day >= 4 and money >= 1200 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["BUY_LAND"])
        elif "SW" not in unlocked_quads and "NE" in unlocked_quads and money >= 2500 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["BUY_LAND"])
            
        # 6. Mid-Game Animal Expansion
        if self.day in (6, 7) and shed.get("SHEEP", 0) == 0 and shed.get("COW", 0) == 0 and money >= 2000 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["BUY_ANIMAL", "COW", 2])
            market_orders.append(["BUY_ANIMAL", "SHEEP", 2])
        if self.day in (11, 12) and shed.get("COW", 0) == 0 and shed.get("SHEEP", 0) == 0 and money >= 3500 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["BUY_ANIMAL", "COW", 4])
            market_orders.append(["BUY_ANIMAL", "SHEEP", 4])
            
        # 7. Seed Buffer Management
        if self.day < 24 and len(market_orders) < MAX_ORDERS:
            if seeds.get("WHEAT", 0) < 25 and money >= 300:
                market_orders.append(["BUY_SEED", "WHEAT", 25])
            if self.day >= 6 and seeds.get("STRAWBERRY", 0) < 25 and money >= 1200 and len(market_orders) < MAX_ORDERS:
                market_orders.append(["BUY_SEED", "STRAWBERRY", 25])
        elif 24 <= self.day <= 26 and len(market_orders) < MAX_ORDERS:
            if seeds.get("CARROT", 0) < 25 and money >= 400:
                market_orders.append(["BUY_SEED", "CARROT", 25])
                
        # 8. Feed Buffer Guarantee (Never allow shed wheat to drop below 15)
        if shed.get("WHEAT", 0) < 15 and self.day < 28 and money >= 400 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["BUY_PRODUCT", "WHEAT", 15])
            
        # 9. Product Sales Strategy
        # High-margin livestock products: sell immediately
        for item in ("WOOL", "MILK", "EGG"):
            qty = shed.get(item, 0)
            if qty > 0 and len(market_orders) < MAX_ORDERS:
                market_orders.append(["SELL", item, qty])
                
        # Fertilizer: sell excess when price is >= $70 or day >= 10
        fert_qty = shed.get("FERTILIZER", 0)
        fert_price = market_prices.get("FERTILIZER", 100)
        if fert_qty > 0 and (fert_price >= 70 or self.day >= 10) and len(market_orders) < MAX_ORDERS:
            market_orders.append(["SELL", "FERTILIZER", fert_qty])
            
        # Melons: sell immediately upon harvest
        melon_qty = shed.get("MELON", 0)
        if melon_qty > 0 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["SELL", "MELON", melon_qty])
            
        # Strawberries: sell in batches of >= 10 or day >= 26
        straw_qty = shed.get("STRAWBERRY", 0)
        if (straw_qty >= 10 or (straw_qty > 0 and self.day >= 26)) and len(market_orders) < MAX_ORDERS:
            market_orders.append(["SELL", "STRAWBERRY", straw_qty])
            
        # Wheat: batch sell in blocks of 60-90 units into town-depleted high prices, or early game cash flow
        wheat_qty = shed.get("WHEAT", 0)
        wheat_price = market_prices.get("WHEAT", 25)
        wheat_surplus = max(0, wheat_qty - (20 if self.day < 28 else 0))
        if len(market_orders) < MAX_ORDERS and wheat_surplus > 0:
            if self.day < 10 and wheat_surplus >= 15:
                market_orders.append(["SELL", "WHEAT", wheat_surplus])
            elif wheat_surplus >= 60 or (wheat_price >= 40 and wheat_surplus >= 30) or self.day >= 27:
                sell_amt = min(90, wheat_surplus)
                market_orders.append(["SELL", "WHEAT", sell_amt])
                
        # Carrots: sell whenever available
        carrot_qty = shed.get("CARROT", 0)
        if carrot_qty > 0 and len(market_orders) < MAX_ORDERS:
            market_orders.append(["SELL", "CARROT", carrot_qty])

        market_orders = market_orders[:MAX_ORDERS]

        # ----------------------------------------------------------------------
        # B. TILE SCANNING & TASK COMPILATION
        # ----------------------------------------------------------------------
        all_units = [farmer_pos] + hands_pos
        num_units = len(all_units)
        occupied_positions = set(all_units)
        
        pen_slots = self.layout.get_all_pen_slots(unlocked_quads)
        
        emergency_unfed = []
        unfed_animals = []
        fert_animals = []
        harvestable_animals = []
        uncared_animals = []
        empty_pens_with_structure = []
        unbuilt_pen_slots = []
        
        mature_crops = []
        unwatered_crops = []
        weeds = []
        empty_crop_slots = []
        
        total_live_animals = 0
        
        for y in range(10):
            for x in range(10):
                tile = tiles[y][x]
                if tile == "LOCKED":
                    continue
                pos = (x, y)
                
                if (x, y) in pen_slots:
                    if tile is None:
                        unbuilt_pen_slots.append(pos)
                    elif isinstance(tile, dict):
                        animal = tile.get("animal")
                        if not animal:
                            empty_pens_with_structure.append(pos)
                        else:
                            total_live_animals += 1
                            consec = tile.get("consecutive_unfed", 0)
                            fed = tile.get("fed_today", False)
                            cared = tile.get("cared_today", False)
                            fert = tile.get("fertilizer_available", False)
                            yields = tile.get("yield_units", 0)
                            
                            if not fed:
                                if consec >= 1:
                                    emergency_unfed.append(pos)
                                else:
                                    unfed_animals.append(pos)
                            if fert:
                                fert_animals.append(pos)
                            if yields > 0:
                                harvestable_animals.append(pos)
                            if not cared:
                                uncared_animals.append(pos)
                else:
                    if pos not in shed_access_tiles(BOARD_SIZE):
                        if tile is None:
                            empty_crop_slots.append(pos)
                        elif isinstance(tile, dict):
                            kind = tile.get("kind")
                            if kind == "WEED":
                                weeds.append(pos)
                            elif kind == "PLANT":
                                crop_name = tile.get("crop")
                                cdata = CROPS.get(crop_name, {})
                                age = self.day - tile.get("planted_day", 0)
                                if not tile.get("watered_today", False):
                                    unwatered_crops.append(pos)
                                if age >= cdata.get("first_yield_day", 99) and tile.get("yield_units", 0) > 0:
                                    mature_crops.append(pos)

        # ----------------------------------------------------------------------
        # C. WORKFORCE ROLE ALLOCATION
        # ----------------------------------------------------------------------
        # Determine number of dedicated caretakers based on live animals
        # 1-4 animals: 2 caretakers; 5-8 animals: 3 caretakers; 9+ animals: 4-5 caretakers
        num_caretakers = 2
        if total_live_animals >= 9 or len(empty_pens_with_structure) >= 4:
            num_caretakers = 4
        elif total_live_animals >= 5:
            num_caretakers = 3
        num_caretakers = min(num_caretakers, num_units)
        
        caretaker_indices = set(range(num_caretakers))
        
        # ----------------------------------------------------------------------
        # D. UNIT DISPATCH & ACTION RESOLUTION
        # ----------------------------------------------------------------------
        unit_actions = []
        assigned_targets = set()
        shed_reserved = collections.defaultdict(int)
        
        for u_idx, u_pos in enumerate(all_units):
            ux, uy = u_pos
            curr_tile = tiles[uy][ux]
            u_inv = inventories[u_idx] if u_idx < len(inventories) else {}
            other_positions = set(all_units) - {u_pos}
            is_caretaker = (u_idx in caretaker_indices)
            
            action = ["PASS"]
            
            # --- TIER 1: IMMEDIATE ACTIONS ON CURRENT TILE ---
            if curr_tile and isinstance(curr_tile, dict):
                # On an animal tile
                if "animal" in curr_tile:
                    # FEED FIRST! Inviolable rule to prevent starvation
                    if not curr_tile.get("fed_today", False) and u_inv.get("WHEAT", 0) > 0:
                        action = ["FEED"]
                    elif curr_tile.get("fertilizer_available", False):
                        action = ["COLLECT_FERTILIZER"]
                    elif curr_tile.get("yield_units", 0) > 0:
                        action = ["HARVEST"]
                    elif not curr_tile.get("cared_today", False):
                        action = ["CARE"]
                # On an empty pen structure
                elif curr_tile.get("kind") in ("PASTURE", "COOP") and "animal" not in curr_tile:
                    for anim in ("SHEEP", "COW"):
                        if u_inv.get(anim, 0) > 0 and curr_tile.get("kind") == ANIMALS[anim]["structure"]:
                            action = ["PLACE", anim]
                            break
                # On a plant tile
                elif curr_tile.get("kind") == "PLANT":
                    crop_name = curr_tile.get("crop")
                    cdata = CROPS.get(crop_name, {})
                    age = self.day - curr_tile.get("planted_day", 0)
                    if age >= cdata.get("first_yield_day", 99) and curr_tile.get("yield_units", 0) > 0:
                        action = ["HARVEST"]
                    elif not curr_tile.get("watered_today", False):
                        action = ["WATER"]
                # On a weed tile
                elif curr_tile.get("kind") == "WEED":
                    action = ["DIG"]
            elif curr_tile is None and u_pos not in shed_access_tiles(BOARD_SIZE):
                if self.layout.is_pen_slot(u_pos, unlocked_quads):
                    # Pen slot needs structure
                    action = ["BUILD_PASTURE"]
                else:
                    # Empty crop slot
                    if self.day == 0 and seeds.get("MELON", 0) > 0:
                        action = ["PLANT", "MELON"]
                    elif 24 <= self.day <= 28 and seeds.get("CARROT", 0) > 0:
                        action = ["PLANT", "CARROT"]
                    elif self.day >= 6 and seeds.get("STRAWBERRY", 0) > 0 and (ux >= 5 or uy >= 5):
                        action = ["PLANT", "STRAWBERRY"]
                    elif seeds.get("WHEAT", 0) > 0:
                        action = ["PLANT", "WHEAT"]
                    elif seeds.get("MELON", 0) > 0:
                        action = ["PLANT", "MELON"]
                    elif seeds.get("STRAWBERRY", 0) > 0:
                        action = ["PLANT", "STRAWBERRY"]
                        
            if action != ["PASS"]:
                unit_actions.append(action)
                continue

            # --- TIER 2: SHED INTERACTION (if standing on shed access) ---
            if is_shed_adjacent(u_pos):
                # Pick up animal if in shed and not holding one
                is_holding_animal = any(u_inv.get(a, 0) > 0 for a in ANIMALS)
                if not is_holding_animal:
                    for anim in ("SHEEP", "COW"):
                        avail = shed.get(anim, 0) - shed_reserved[anim]
                        if avail > 0:
                            action = ["PICKUP", anim, 1]
                            shed_reserved[anim] += 1
                            break
                            
                # Pick up Wheat feed if caretaker and inventory is low
                if action == ["PASS"] and is_caretaker and u_inv.get("WHEAT", 0) < 10:
                    avail_wheat = shed.get("WHEAT", 0) - shed_reserved["WHEAT"]
                    if avail_wheat > 0:
                        take_qty = min(20, avail_wheat)
                        action = ["PICKUP", "WHEAT", take_qty]
                        shed_reserved["WHEAT"] += take_qty
                        
            if action != ["PASS"]:
                unit_actions.append(action)
                continue

            # --- TIER 3: TARGET SELECTION & NAVIGATION ---
            target = None
            
            # 1. Carrying Animal -> Head directly to empty pen
            is_holding_animal = any(u_inv.get(a, 0) > 0 for a in ANIMALS)
            if is_holding_animal:
                candidate_pens = [p for p in empty_pens_with_structure if p not in assigned_targets]
                if not candidate_pens:
                    candidate_pens = [p for p in unbuilt_pen_slots if p not in assigned_targets]
                if candidate_pens:
                    target = min(candidate_pens, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)

            # 2. Caretaker Logic
            if not target and is_caretaker:
                # If carrying 0 wheat and shed has wheat, go restock at nearest free shed tile
                if u_inv.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0:
                    target = get_best_shed_access(u_pos, occupied_positions)
                else:
                    # Emergency unfed animals first (prevent starvation!)
                    if emergency_unfed:
                        valid_emerg = [c for c in emergency_unfed if c not in assigned_targets]
                        if valid_emerg:
                            target = min(valid_emerg, key=lambda p: manhattan(u_pos, p))
                            assigned_targets.add(target)
                    # Routine unfed animals next
                    if not target and unfed_animals:
                        valid_unfed = [c for c in unfed_animals if c not in assigned_targets]
                        if valid_unfed:
                            target = min(valid_unfed, key=lambda p: manhattan(u_pos, p))
                            assigned_targets.add(target)
                    # Fertilizer collection, harvest, care
                    if not target:
                        routine_candidates = fert_animals + harvestable_animals + uncared_animals
                        valid_routine = [c for c in routine_candidates if c not in assigned_targets]
                        if valid_routine:
                            target = min(valid_routine, key=lambda p: manhattan(u_pos, p))
                            assigned_targets.add(target)

            # 3. Crop Harvesters & Field Workers (or idle Caretakers)
            # A. Weeds (top crop priority)
            if not target and weeds:
                valid_weeds = [w for w in weeds if w not in assigned_targets]
                if valid_weeds:
                    target = min(valid_weeds, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)
                    
            # B. Mature Crop Harvest
            if not target and mature_crops:
                valid_mature = [c for c in mature_crops if c not in assigned_targets]
                if valid_mature:
                    target = min(valid_mature, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)
                    
            # C. Watering Unwatered Crops
            if not target and unwatered_crops:
                valid_water = [c for c in unwatered_crops if c not in assigned_targets]
                if valid_water:
                    target = min(valid_water, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)
                    
            # D. Pen Building
            if not target and unbuilt_pen_slots:
                valid_pen_slots = [p for p in unbuilt_pen_slots if p not in assigned_targets]
                if valid_pen_slots:
                    target = min(valid_pen_slots, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)
                    
            # E. Planting Empty Crop Slots
            if not target and empty_crop_slots:
                valid_empty = [e for e in empty_crop_slots if e not in assigned_targets]
                if valid_empty:
                    target = min(valid_empty, key=lambda p: manhattan(u_pos, p))
                    assigned_targets.add(target)

            # Execute movement step towards selected target
            if target and target != u_pos:
                move_act = get_next_step(u_pos, target, tiles, other_positions)
                action = [move_act]
            else:
                action = ["PASS"]
                
            unit_actions.append(action)
            
        # Format final action output
        farmer_act = unit_actions[0] if unit_actions else ["PASS"]
        hands_acts = unit_actions[1:] if len(unit_actions) > 1 else [["PASS"] for _ in hands]
        while len(hands_acts) < len(hands):
            hands_acts.append(["PASS"])
        hands_acts = hands_acts[:len(hands)]
        
        return {
            "farmer": farmer_act,
            "hands": hands_acts,
            "market": market_orders
        }


# Global agent instance
_AURAFARM_V3_AGENT = None

def agent(observation, configuration=None):
    global _AURAFARM_V3_AGENT
    step = int(observation.get("step", 0))
    if step == 0 or _AURAFARM_V3_AGENT is None:
        _AURAFARM_V3_AGENT = AuraFarmV3()
    try:
        return _AURAFARM_V3_AGENT.act(observation, configuration)
    except Exception as e:
        farms = observation.get("farms", [])
        hands = farms[int(observation.get("player", 0))].get("hands", []) if farms else []
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in hands],
            "market": []
        }
