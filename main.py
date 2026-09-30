"""
AuraFarm V5: Industrial Throughput Agent
Built from three independent M & M & P & Q Kaggriculture replays.

Observed macro policy reproduced:
- near-zero-cash Day-0 bootstrap: 2 cows + 3 sheep + feed + melon
- 4 -> 5 -> 6 -> 9 -> 8/9 -> 10/11 -> 12 daily hands
- first land expansion around day 6, all four quadrants by ~day 10
- 20+ livestock with mixed species and dedicated pens
- melons as early capital spike
- continuous wheat production as the high-throughput backbone
- tomato/carrot/strawberry as secondary production lines
- daily feed/care/fertilizer collection
- fertilizer used on imminent-yield crops, especially wheat
- small/frequent commodity sales early and larger sales late
- final two days focus on harvest + liquidation

This is an independent implementation; no opponent code or route tape is copied.
Standard library only.
"""

import math
import collections
from typing import List, Tuple, Dict, Any


# =============================================================================
# GAME CONSTANTS
# =============================================================================

BOARD_SIZE = 10
HALF = 5
TURNS_PER_DAY = 24
TOTAL_STEPS = 720
LAST_ACT_STEP = 718
MAX_ORDERS = 10
FLOOR = 1
HINGE_GAIN = 8.0

CROPS = {
    "WHEAT":      {"seed": 10,  "first": 2,  "max": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20,  "first": 2,  "max": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50,  "first": 8,  "max": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "max": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80,  "first": 10, "max": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first": 4, "interval": 1, "max": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "max": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "max": 6, "product": "WOOL"},
}

PRODUCTS = [
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
    "EGG", "MILK", "WOOL", "FERTILIZER"
]

MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "I0": 10000, "T": 400, "below": "sqrt",  "below_target": 0.80, "above": "log",   "above_target": 0.20},
    "CARROT":     {"base": 35,  "I0": 10000, "T": 450, "below": "hinge", "below_target": 1.00, "above": "sqrt",  "above_target": 0.70},
    "TOMATO":     {"base": 60,  "I0": 10000, "T": 200, "below": "hinge", "below_target": 0.40, "above": "sqrt",  "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "below": "sqrt",  "below_target": 0.70, "above": "linear","above_target": 1.60},
    "MELON":      {"base": 250, "I0": 10000, "T": 300, "below": "log",   "below_target": 0.20, "above": "sq",    "above_target": 3.60},
    "EGG":        {"base": 50,  "I0": 10000, "T": 332, "below": "hinge", "below_target": 0.40, "above": "log",   "above_target": 0.20},
    "MILK":       {"base": 160, "I0": 10000, "T": 122, "below": "sqrt",  "below_target": 0.60, "above": "linear","above_target": 1.60},
    "WOOL":       {"base": 200, "I0": 10000, "T": 105, "below": "log",   "below_target": 0.20, "above": "sq",    "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "below": "linear","below_target": 0.40, "above": "linear","above_target": 0.40},
}


def shape(name: str, x: float, T: float) -> float:
    x = max(0.0, float(x))
    if name == "linear":
        return x
    if name == "sq":
        return x * x
    if name == "sqrt":
        return math.sqrt(x)
    if name == "log":
        return math.log(1.0 + x)
    if name == "hinge":
        u = x / T if T > 0 else x
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x


def market_price(item: str, inventory: float) -> int:
    p = MARKET_PARAMS.get(item)
    if not p:
        return 1
    base, I0, T = p["base"], p["I0"], p["T"]
    diff = inventory - I0
    if diff <= 0:
        sign, fn, target = 1.0, p["below"], p["below_target"]
    else:
        sign, fn, target = -1.0, p["above"], p["above_target"]
    denom = shape(fn, T, T)
    amp = target * base / denom if denom > 0 else 0.0
    return max(FLOOR, math.floor(base + sign * amp * shape(fn, abs(diff), T)))


def hire_cost(n_already_today: int) -> int:
    a, b = 1, 1
    for _ in range(n_already_today):
        a, b = b, a + b
    return a


def shed_tiles() -> List[Tuple[int, int]]:
    return [(4, 4), (5, 4), (4, 5), (5, 5)]


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# =============================================================================
# LAYOUT
# =============================================================================

class Layout:
    """
    Reserve a compact livestock block around the central shed and leave the
    rest as crop/work zones. The exact coordinates are intentionally different
    from any opponent implementation.
    """

    pasture = [
        (2, 3), (3, 3), (2, 2), (3, 2),      # NW
        (5, 3), (6, 3), (7, 3), (5, 2), (6, 2), (7, 2),  # NE
        (2, 5), (3, 5), (2, 6), (3, 6), (2, 7), (3, 7),  # SW
    ]

    coop = [
        (8, 3), (9, 3), (8, 2), (9, 2),      # NE
        (6, 5), (7, 5), (8, 5), (9, 5),      # SE
    ]

    def pen_kind(self, pos):
        t = tuple(pos)
        if t in self.pasture:
            return "PASTURE"
        if t in self.coop:
            return "COOP"
        return None

    def pens(self, unlocked):
        result = []
        for p in self.pasture:
            x, y = p
            if x < 5 and y < 5:
                result.append(p)
            elif x >= 5 and y < 5 and "NE" in unlocked:
                result.append(p)
            elif x < 5 and y >= 5 and "SW" in unlocked:
                result.append(p)
            elif x >= 5 and y >= 5 and "SE" in unlocked:
                result.append(p)
        for p in self.coop:
            x, y = p
            if x < 5 and y < 5:
                result.append(p)
            elif x >= 5 and y < 5 and "NE" in unlocked:
                result.append(p)
            elif x < 5 and y >= 5 and "SW" in unlocked:
                result.append(p)
            elif x >= 5 and y >= 5 and "SE" in unlocked:
                result.append(p)
        return result

    def owned(self, x, y, unlocked):
        if not (0 <= x < 10 and 0 <= y < 10):
            return False
        if x < 5 and y < 5:
            return True
        if x >= 5 and y < 5:
            return "NE" in unlocked
        if x < 5 and y >= 5:
            return "SW" in unlocked
        return "SE" in unlocked


# =============================================================================
# PATHING
# =============================================================================

def next_step(start, target, tiles, occupied):
    if start == target:
        return ["PASS"]
    sx, sy = start
    tx, ty = target
    q = collections.deque([(sx, sy)])
    parent = {(sx, sy): None}
    move_from = {}
    dirs = [
        ((0, -1), "NORTH"),
        ((0, 1), "SOUTH"),
        ((1, 0), "EAST"),
        ((-1, 0), "WEST"),
    ]

    while q:
        x, y = q.popleft()
        if (x, y) == (tx, ty):
            cur = (x, y)
            while parent[cur] is not None and parent[cur] != (sx, sy):
                cur = parent[cur]
            return [move_from[cur]]
        for (dx, dy), act in dirs:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < 10 and 0 <= ny < 10):
                continue
            if (nx, ny) in parent:
                continue
            if tiles[ny][nx] == "LOCKED":
                continue
            if (nx, ny) in occupied and (nx, ny) != (tx, ty):
                continue
            parent[(nx, ny)] = (x, y)
            move_from[(nx, ny)] = act
            q.append((nx, ny))

    # Greedy fallback
    best = ["PASS"]
    best_d = 10**9
    for (dx, dy), act in dirs:
        nx, ny = sx + dx, sy + dy
        if 0 <= nx < 10 and 0 <= ny < 10 and tiles[ny][nx] != "LOCKED":
            if (nx, ny) not in occupied or (nx, ny) == (tx, ty):
                d = manhattan((nx, ny), (tx, ty))
                if d < best_d:
                    best_d, best = d, [act]
    return best


# =============================================================================
# AGENT
# =============================================================================

class AuraFarmV5:
    def __init__(self):
        self.layout = Layout()
        self.day = 0
        self.hour = 0
        self.step = 0

    # --- empirical labor curve observed across all 3 replays -----------------
    @staticmethod
    def hand_target(day: int) -> int:
        if day == 0:
            return 4
        if day == 1:
            return 4
        if day == 2:
            return 5
        if day in (3, 4, 5):
            return 6
        if day == 6:
            return 9
        if day == 7:
            return 8
        if day == 8:
            return 9
        if day == 9:
            return 11
        if 10 <= day <= 27:
            return 12
        return 10

    # --- classify crops -------------------------------------------------------
    def scan(self, tiles, unlocked, day):
        crops = collections.Counter()
        animals = collections.Counter()
        live_plants = []
        mature_plants = []
        fert_targets = []
        unwatered = []
        fresh = []
        weeds = []
        empty = []
        animal_tiles = []
        fert_animals = []
        harvest_animals = []
        unfed = []
        emergency_unfed = []
        uncared = []
        empty_pens = []
        empty_slots = []

        pen_positions = set(self.layout.pens(unlocked))
        for y in range(10):
            for x in range(10):
                tile = tiles[y][x]
                pos = (x, y)
                if tile == "LOCKED":
                    continue

                pk = self.layout.pen_kind(pos)
                if pk:
                    if tile is None:
                        empty_pens.append(pos)
                        continue
                    if isinstance(tile, dict) and tile.get("kind") in ("PASTURE", "COOP"):
                        animal = tile.get("animal")
                        if animal:
                            animal_tiles.append(pos)
                            animals[animal] += 1
                            if tile.get("fertilizer_available", False):
                                fert_animals.append(pos)
                            if tile.get("yield_units", 0) > 0:
                                harvest_animals.append(pos)
                            if not tile.get("fed_today", False):
                                if tile.get("consecutive_unfed", 0) >= 1:
                                    emergency_unfed.append(pos)
                                else:
                                    unfed.append(pos)
                            if not tile.get("cared_today", False):
                                uncared.append(pos)
                        continue

                if pos in shed_tiles():
                    continue

                if tile is None:
                    empty.append(pos)
                    continue

                if isinstance(tile, dict):
                    if tile.get("kind") == "WEED":
                        weeds.append(pos)
                        continue
                    if tile.get("kind") != "PLANT":
                        continue
                    crop = tile.get("crop")
                    if crop:
                        crops[crop] += 1
                    live_plants.append((pos, crop, tile))
                    if not tile.get("watered_today", False):
                        unwatered.append(pos)
                        if tile.get("planted_day", -1) == day:
                            fresh.append(pos)

                    age = day - tile.get("planted_day", day)
                    c = CROPS.get(crop, {})
                    ready = age >= c.get("first", 99) and tile.get("yield_units", 0) > 0
                    if ready:
                        mature_plants.append(pos)

                    # Empirical fertilization ages from replays:
                    # wheat 1-3 (mostly 2), carrots 1-3, tomato 6-10,
                    # strawberry 9-16, melon 6-7.
                    fert_age = (
                        (crop == "WHEAT" and 1 <= age <= 3)
                        or (crop == "CARROT" and 1 <= age <= 3)
                        or (crop == "TOMATO" and 6 <= age <= 10)
                        or (crop == "STRAWBERRY" and 9 <= age <= 16)
                        or (crop == "MELON" and 6 <= age <= 7)
                    )
                    if fert_age and tile.get("fertilized_until_day", -1) < day:
                        fert_targets.append((pos, crop, age))

        all_pen_slots = set(self.layout.pens(unlocked))
        for p in all_pen_slots:
            if p not in pen_positions:
                empty_slots.append(p)

        return {
            "crops": crops, "animals": animals, "live_plants": live_plants,
            "mature": mature_plants, "fert_targets": fert_targets,
            "unwatered": unwatered, "fresh": fresh, "weeds": weeds,
            "empty": empty, "animal_tiles": animal_tiles,
            "fert_animals": fert_animals, "harvest_animals": harvest_animals,
            "unfed": unfed, "emergency_unfed": emergency_unfed,
            "uncared": uncared, "empty_pens": empty_pens,
        }

    def opening_orders(self):
        """
        Exact opening skeleton common to all three analyzed replays.
        The action order is intentionally preserved.
        """
        table = {
            1: [["BUY_ANIMAL", "COW", 1], ["BUY_PRODUCT", "WHEAT", 5]],
            2: [["SELL", "WHEAT", 1], ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"],
                ["BUY_ANIMAL", "COW", 1], ["BUY_ANIMAL", "SHEEP", 3]],
            3: [["SELL", "WHEAT", 1]],
            4: [["SELL", "WHEAT", 1], ["BUY_PRODUCT", "WHEAT", 1]],
            5: [["BUY_PRODUCT", "WHEAT", 1]],
            6: [["SELL", "WHEAT", 1], ["BUY_PRODUCT", "WHEAT", 1]],
            7: [["BUY_SEED", "MELON", 2], ["BUY_PRODUCT", "WHEAT", 1]],
            8: [["BUY_SEED", "MELON", 2]],
            11: [["BUY_SEED", "WHEAT", 3]],
        }
        return table.get(self.step, [])

    def strategic_market(self, obs, scan):
        farm = obs["farms"][obs["player"]]
        private = obs.get("private", {})
        shed = private.get("shed", {})
        seeds = private.get("seeds", {})
        market = obs.get("market", {})
        prices = market.get("prices", {})
        money = float(farm.get("money", 0.0))
        day = self.day
        hour = self.hour

        # The exact first 9 non-terminal steps are highly stable in all 3 replays.
        if self.step in (1, 2, 3, 4, 5, 6, 7, 8, 11):
            return self.opening_orders()[:MAX_ORDERS]

        orders = []

        # ---------------------------------------------------------------------
        # Labor: reproduce the observed 4/4/5/6/6/6/9/8/9/11/12... curve.
        # Rehire every day because hands are daily resources.
        # ---------------------------------------------------------------------
        desired = self.hand_target(day)
        if self.hour == 1 and len(farm.get("hands", [])) < desired:
            need = desired - len(farm.get("hands", []))
            hires_today = int(farm.get("hires_today", 0))
            for i in range(need):
                cost = hire_cost(hires_today + i)
                # Keep enough liquidity to buy seed/feed and avoid the dead-cash
                # state once the opening bootstrap is over.
                reserve = 80 if day < 10 else 150
                if money >= cost + reserve and len(orders) < MAX_ORDERS:
                    orders.append(["HIRE"])

        # ---------------------------------------------------------------------
        # Land: push to all four quadrants as soon as the replay-like cash
        # milestones are reached.
        # ---------------------------------------------------------------------
        unlocked = farm.get("unlocked_quadrants", ["NW"])
        if "NE" not in unlocked and day >= 6 and money >= 1050 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_LAND"])
        elif "SW" not in unlocked and "NE" in unlocked and day >= 8 and money >= 2050 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_LAND"])
        elif "SE" not in unlocked and "SW" in unlocked and day >= 10 and money >= 4050 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_LAND"])

        # ---------------------------------------------------------------------
        # Seed discipline.
        # Melon is a fixed early bootstrap (22 seeds in the 3 replays).
        # Wheat is purchased almost one at a time, just-in-time.
        # Other crops are kept as secondary production lines.
        # ---------------------------------------------------------------------
        melon_purchased_window = (day == 0 and hour in (7, 8, 12)) or (day == 1 and 8 <= hour <= 15)
        if melon_purchased_window and seeds.get("MELON", 0) < 22 and money >= 160 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_SEED", "MELON", 2])

        # one extra pair around the first land expansion, matching the common replay total
        if day == 6 and hour in (12, 13, 14) and seeds.get("MELON", 0) < 6 and money >= 160 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_SEED", "MELON", 2])

        # Wheat: maintain a tiny seed buffer instead of large speculative stock.
        if day <= 27 and seeds.get("WHEAT", 0) <= 1 and money >= 10 and len(orders) < MAX_ORDERS:
            # once money is comfortable, allow small replenishment bursts
            n = 3 if day >= 9 and money >= 2000 and hour in (6, 11, 16) else 1
            orders.append(["BUY_SEED", "WHEAT", n])

        # Tomato begins after its production line appears in the replays.
        if 8 <= day <= 19 and seeds.get("TOMATO", 0) <= 0 and money >= 50 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_SEED", "TOMATO", 1])

        # Strawberry is intentionally small: 16-29 total planted, not 60+.
        active_straw = scan["crops"].get("STRAWBERRY", 0)
        if 2 <= day <= 16 and active_straw < 20 and seeds.get("STRAWBERRY", 0) <= 0 and money >= 100 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_SEED", "STRAWBERRY", 1])

        # Carrot becomes the late short-cycle crop. Buy in the same six-seed
        # bundles that appear repeatedly in the replays.
        active_carrot = scan["crops"].get("CARROT", 0)
        if 11 <= day <= 26 and active_carrot < 24 and seeds.get("CARROT", 0) < 2 and money >= 120 and len(orders) < MAX_ORDERS:
            orders.append(["BUY_SEED", "CARROT", 6])

        # ---------------------------------------------------------------------
        # Feed economy. M&M&P&Q continuously buys wheat product in small
        # quantities rather than hoarding it, primarily to avoid animal stalls.
        # ---------------------------------------------------------------------
        animal_count = sum(scan["animals"].values())
        wheat = int(shed.get("WHEAT", 0))
        held_wheat = sum(int(inv.get("WHEAT", 0)) for inv in private.get("inventories", []) if isinstance(inv, dict))
        feed_need = max(4, animal_count + 4)
        if day < 10 and wheat + held_wheat < feed_need and money >= 30 and len(orders) < MAX_ORDERS:
            qty = min(5, max(1, feed_need - wheat - held_wheat))
            orders.append(["BUY_PRODUCT", "WHEAT", qty])
        elif day < 28 and wheat + held_wheat < max(8, animal_count // 2) and money >= 30 and len(orders) < MAX_ORDERS:
            qty = min(8, max(1, animal_count - wheat - held_wheat + 2))
            orders.append(["BUY_PRODUCT", "WHEAT", qty])

        # ---------------------------------------------------------------------
        # Sales. Livestock output is sold promptly. Fertilizer is split between
        # crop amplification and cash flow. Wheat is sold in small/medium
        # batches midgame, then liquidated in bulk.
        # ---------------------------------------------------------------------
        for item in ("WOOL", "MILK", "EGG"):
            qty = int(shed.get(item, 0))
            if qty > 0 and len(orders) < MAX_ORDERS:
                orders.append(["SELL", item, qty])

        fert = int(shed.get("FERTILIZER", 0))
        fprice = int(prices.get("FERTILIZER", 100))
        fert_reserve = 8 if day < 18 else 4
        if fert > fert_reserve and len(orders) < MAX_ORDERS:
            if day >= 27:
                sell = fert - fert_reserve
            else:
                # observed behavior: repeated small sales of 1-8 units
                sell = min(8, fert - fert_reserve)
                if fprice < 70 and day < 10:
                    sell = min(2, fert - fert_reserve)
            if sell > 0:
                orders.append(["SELL", "FERTILIZER", sell])

        # Melon: monetize the early spike immediately.
        melon = int(shed.get("MELON", 0))
        if melon > 0 and len(orders) < MAX_ORDERS:
            orders.append(["SELL", "MELON", melon])

        for item in ("STRAWBERRY", "TOMATO", "CARROT"):
            qty = int(shed.get(item, 0))
            if qty > 0 and len(orders) < MAX_ORDERS:
                orders.append(["SELL", item, qty])

        # Wheat: keep the shared market depleted by town, but avoid a giant early
        # price crash. Later in the season the replay bot sells 60-155 in a day.
        wheat = int(shed.get("WHEAT", 0))
        wprice = int(prices.get("WHEAT", 25))
        reserve = 6 if day < 27 else 0
        surplus = max(0, wheat - reserve)
        if surplus > 0 and len(orders) < MAX_ORDERS:
            if day < 5:
                sell = min(1, surplus)
            elif day < 10:
                sell = min(6, surplus)
            elif day < 18:
                sell = min(15 if wprice < 35 else 25, surplus)
            elif day < 27:
                sell = min(25 if wprice < 40 else 40, surplus)
            else:
                sell = surplus
            if sell > 0:
                orders.append(["SELL", "WHEAT", sell])

        # Terminal liquidation: sell all remaining shed inventory.
        if day >= 28:
            orders = []
            for item in PRODUCTS:
                qty = int(shed.get(item, 0))
                if qty > 0:
                    orders.append(["SELL", item, qty])
                    if len(orders) >= MAX_ORDERS:
                        break

        return orders[:MAX_ORDERS]

    def desired_fertilizer_crop(self, crop, age):
        if crop == "WHEAT":
            return 1 <= age <= 3
        if crop == "CARROT":
            return 1 <= age <= 3
        if crop == "TOMATO":
            return 6 <= age <= 10
        if crop == "STRAWBERRY":
            return 9 <= age <= 16
        if crop == "MELON":
            return 6 <= age <= 7
        return False

    def act(self, observation, configuration=None):
        self.step = int(observation.get("step", 0))
        self.day = int(observation.get("day", self.step // 24))
        self.hour = int(observation.get("hour", self.step % 24))
        player = int(observation.get("player", 0))

        farms = observation.get("farms", [])
        if not farms or player >= len(farms):
            return {"farmer": ["PASS"], "hands": [], "market": []}

        farm = farms[player]
        private = observation.get("private", {})
        tiles = farm.get("tiles", [])
        unlocked = farm.get("unlocked_quadrants", ["NW"])
        hands = farm.get("hands", [])
        inventories = private.get("inventories", [])
        shed = private.get("shed", {})

        if self.step >= LAST_ACT_STEP:
            terminal = []
            for item in PRODUCTS:
                qty = int(shed.get(item, 0))
                if qty > 0 and len(terminal) < MAX_ORDERS:
                    terminal.append(["SELL", item, qty])
            return {
                "farmer": ["PASS"],
                "hands": [["PASS"] for _ in hands],
                "market": terminal,
            }

        # Scan current farm state.
        sc = self.scan(tiles, unlocked, self.day)

        market_orders = self.strategic_market(observation, sc)

        # Current units (farmer + hands).
        unit_positions = [tuple(farm.get("farmer", [4, 4]))] + [tuple(h) for h in hands]
        unit_actions = [["PASS"] for _ in unit_positions]
        occupied = set(unit_positions)
        assigned = set()

        # Classify units with small pools rather than permanently pinning all
        # workers to one role. This mirrors the replay throughput pattern:
        # everyone helps with the currently scarce task.
        for i, pos in enumerate(unit_positions):
            if i < len(inventories):
                inv = inventories[i] if isinstance(inventories[i], dict) else {}
            else:
                inv = {}

            x, y = pos
            tile = tiles[y][x]
            acted = False

            # ---------------------------------------------------------------
            # TIER 1: work on the current tile
            # ---------------------------------------------------------------
            if isinstance(tile, dict):
                kind = tile.get("kind")

                if kind in ("PASTURE", "COOP") and tile.get("animal"):
                    # Feeding is always first.
                    if not tile.get("fed_today", False) and inv.get("WHEAT", 0) > 0:
                        unit_actions[i] = ["FEED"]; acted = True
                    elif not tile.get("cared_today", False):
                        unit_actions[i] = ["CARE"]; acted = True
                    elif tile.get("fertilizer_available", False):
                        unit_actions[i] = ["COLLECT_FERTILIZER"]; acted = True
                    elif tile.get("yield_units", 0) > 0:
                        unit_actions[i] = ["HARVEST"]; acted = True

                elif kind == "PLANT":
                    crop = tile.get("crop")
                    age = self.day - tile.get("planted_day", self.day)
                    if (
                        inv.get("FERTILIZER", 0) > 0
                        and tile.get("fertilized_until_day", -1) < self.day
                        and self.desired_fertilizer_crop(crop, age)
                    ):
                        unit_actions[i] = ["FERTILIZE"]; acted = True
                    elif not tile.get("watered_today", False):
                        unit_actions[i] = ["WATER"]; acted = True
                    elif tile.get("yield_units", 0) > 0 and age >= CROPS.get(crop, {}).get("first", 99):
                        unit_actions[i] = ["HARVEST"]; acted = True

                elif kind == "WEED":
                    unit_actions[i] = ["DIG"]; acted = True

            if acted:
                continue

            # ---------------------------------------------------------------
            # TIER 2: shed pickups when standing at the center
            # ---------------------------------------------------------------
            if pos in shed_tiles():
                # Animal pickup has high priority because purchases are waiting.
                for animal in ("SHEEP", "COW", "GOOSE"):
                    if inv.get(animal, 0) <= 0 and int(shed.get(animal, 0)) > 0:
                        unit_actions[i] = ["PICKUP", animal, 1]
                        acted = True
                        break

                if not acted and inv.get("WHEAT", 0) < 5 and int(shed.get("WHEAT", 0)) > 0:
                    qty = min(8, int(shed.get("WHEAT", 0)))
                    unit_actions[i] = ["PICKUP", "WHEAT", qty]
                    acted = True

                if not acted and inv.get("FERTILIZER", 0) < 2 and int(shed.get("FERTILIZER", 0)) > 0:
                    qty = min(4, int(shed.get("FERTILIZER", 0)))
                    unit_actions[i] = ["PICKUP", "FERTILIZER", qty]
                    acted = True

            if acted:
                continue

            # ---------------------------------------------------------------
            # TIER 3: carrying an animal -> nearest compatible empty structure
            # ---------------------------------------------------------------
            holding = next((a for a in ANIMALS if inv.get(a, 0) > 0), None)
            if holding:
                compatible = []
                wanted_kind = ANIMALS[holding]["structure"]
                for p in sc["empty_pens"]:
                    pk = self.layout.pen_kind(p)
                    if pk == wanted_kind and p not in assigned:
                        compatible.append(p)
                if compatible:
                    target = min(compatible, key=lambda p: manhattan(pos, p))
                    assigned.add(target)
                    if target != pos:
                        unit_actions[i] = next_step(pos, target, tiles, occupied)
                    else:
                        unit_actions[i] = ["PLACE", holding]
                    continue

            # ---------------------------------------------------------------
            # TIER 4: priority targets
            # ---------------------------------------------------------------
            target = None

            # Emergency animal feed
            for pool in (sc["emergency_unfed"], sc["unfed"]):
                candidates = [p for p in pool if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)
                    break

            # Freshly planted crops MUST be watered before day refresh.
            if target is None:
                candidates = [p for p in sc["fresh"] if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            # Animal fertilizer + harvest + care.
            if target is None:
                animal_tasks = []
                for p in sc["fert_animals"]:
                    animal_tasks.append((0, p))
                for p in sc["harvest_animals"]:
                    animal_tasks.append((1, p))
                for p in sc["uncared"]:
                    animal_tasks.append((2, p))
                candidates = [p for _, p in sorted(animal_tasks) if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            # Plant fertilizer: wheat and other imminent-yield crops first.
            if target is None and inv.get("FERTILIZER", 0) > 0:
                candidates = [
                    p for p, crop, age in sc["fert_targets"]
                    if p not in assigned
                ]
                if candidates:
                    # Prioritize wheat because the replay bot spends the most
                    # fertilizer actions there, then the other crop lines.
                    def fert_key(p):
                        for pp, crop, age in sc["fert_targets"]:
                            if pp == p:
                                weight = {"WHEAT": 0, "CARROT": 1, "TOMATO": 2, "STRAWBERRY": 3, "MELON": 4}.get(crop, 5)
                                return weight, age, manhattan(pos, p)
                        return 9, 9, manhattan(pos, p)
                    target = min(candidates, key=fert_key)
                    assigned.add(target)

            # Mature crops.
            if target is None:
                candidates = [p for p in sc["mature"] if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            # Remaining watering.
            if target is None:
                candidates = [p for p in sc["unwatered"] if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            # Build a pen structure.
            if target is None:
                candidates = [p for p in sc["empty_pens"] if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            # Planting.
            if target is None:
                candidates = [p for p in sc["empty"] if p not in assigned]
                if candidates:
                    target = min(candidates, key=lambda p: manhattan(pos, p))
                    assigned.add(target)

            if target is not None:
                if target == pos:
                    pk = self.layout.pen_kind(target)
                    if pk == "PASTURE":
                        unit_actions[i] = ["BUILD_PASTURE"]
                    elif pk == "COOP":
                        unit_actions[i] = ["BUILD_COOP"]
                    else:
                        # Pick a production seed.
                        seed_choice = None
                        seed_counts = {k: int(private.get("seeds", {}).get(k, 0)) for k in CROPS}
                        active = sc["crops"]
                        # Early melon, then wheat backbone, then tomato/carrot,
                        # with a small strawberry lane.
                        if self.day <= 1 and seed_counts["MELON"] > 0:
                            seed_choice = "MELON"
                        elif seed_counts["WHEAT"] > 0 and active.get("WHEAT", 0) < 30:
                            seed_choice = "WHEAT"
                        elif 8 <= self.day <= 20 and seed_counts["TOMATO"] > 0 and active.get("TOMATO", 0) < 36:
                            seed_choice = "TOMATO"
                        elif 11 <= self.day <= 27 and seed_counts["CARROT"] > 0 and active.get("CARROT", 0) < 24:
                            seed_choice = "CARROT"
                        elif 2 <= self.day <= 16 and seed_counts["STRAWBERRY"] > 0 and active.get("STRAWBERRY", 0) < 20:
                            seed_choice = "STRAWBERRY"
                        elif seed_counts["WHEAT"] > 0:
                            seed_choice = "WHEAT"
                        if seed_choice:
                            unit_actions[i] = ["PLANT", seed_choice]
                else:
                    unit_actions[i] = next_step(pos, target, tiles, occupied)

        farmer_action = unit_actions[0]
        hand_actions = unit_actions[1:]
        while len(hand_actions) < len(hands):
            hand_actions.append(["PASS"])
        hand_actions = hand_actions[:len(hands)]

        return {
            "farmer": farmer_action,
            "hands": hand_actions,
            "market": market_orders,
        }


_LAYOUT = AuraFarmV5()


def agent(observation, configuration=None):
    global _LAYOUT
    step = int(observation.get("step", 0))
    if step == 0 or _LAYOUT is None:
        _LAYOUT = AuraFarmV5()
    try:
        return _LAYOUT.act(observation, configuration)
    except Exception:
        farms = observation.get("farms", [])
        player = int(observation.get("player", 0))
        hands = farms[player].get("hands", []) if farms and player < len(farms) else []
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in hands],
            "market": [],
        }
