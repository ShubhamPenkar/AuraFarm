"""
Prototype for AuraFarm V3.
Implements the full livestock engine, industrial workforce, wheat production planner,
town shop demand model, and clustered worker dispatch.
"""
import sys, os, math, collections, heapq
from kaggle_environments import make

# Simulator constants
BOARD_SIZE = 10
QUADRANT_SIZE = 5
MAX_ORDERS = 10
FARM_HAND_COST_MULT = 1

CROPS = {
    "CARROT": {"seed_cost": 5, "growth_days": 4, "yield": 2, "first_yield_day": 4, "interval": 4, "ongoing": False},
    "WHEAT": {"seed_cost": 10, "growth_days": 5, "yield": 3, "first_yield_day": 5, "interval": 5, "ongoing": False},
    "POTATO": {"seed_cost": 15, "growth_days": 6, "yield": 3, "first_yield_day": 6, "interval": 6, "ongoing": False},
    "TOMATO": {"seed_cost": 15, "growth_days": 6, "yield": 2, "first_yield_day": 6, "interval": 3, "ongoing": True},
    "STRAWBERRY": {"seed_cost": 20, "growth_days": 7, "yield": 3, "first_yield_day": 7, "interval": 4, "ongoing": True},
    "CORN": {"seed_cost": 18, "growth_days": 8, "yield": 4, "first_yield_day": 8, "interval": 4, "ongoing": True},
    "MELON": {"seed_cost": 20, "growth_days": 10, "yield": 4, "first_yield_day": 10, "interval": 10, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ("CARROT", "WHEAT", "POTATO", "TOMATO", "STRAWBERRY", "CORN", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")

MARKET_PARAMS = {
    "CARROT":     {"base": 20, "T": 150, "below_func": "sqrt", "above_func": "linear"},
    "WHEAT":      {"base": 25, "T": 400, "below_func": "sqrt", "above_func": "linear"},
    "POTATO":     {"base": 35, "T": 250, "below_func": "sqrt", "above_func": "linear"},
    "TOMATO":     {"base": 40, "T": 300, "below_func": "sqrt", "above_func": "linear"},
    "STRAWBERRY": {"base": 80, "T": 150, "below_func": "linear", "above_func": "linear"},
    "CORN":       {"base": 50, "T": 300, "below_func": "sqrt", "above_func": "linear"},
    "MELON":      {"base": 120, "T": 100, "below_func": "linear", "above_func": "linear"},
    "EGG":        {"base": 45, "T": 120, "below_func": "sqrt", "above_func": "linear"},
    "MILK":       {"base": 70, "T": 120, "below_func": "sqrt", "above_func": "linear"},
    "WOOL":       {"base": 160, "T": 80, "below_func": "linear", "above_func": "linear"},
    "FERTILIZER": {"base": 80, "T": 100, "below_func": "linear", "above_func": "linear"},
}

SHOPS = {
    "BAKERY": ("WHEAT", "MILK", "EGG"),
    "BRUNCH_SPOT": ("WHEAT", "EGG", "MILK", "STRAWBERRY"),
    "FARMERS_MARKET": ("CARROT", "POTATO", "TOMATO", "CORN", "MELON", "WHEAT"),
    "ICE_CREAM_SHOP": ("MILK", "STRAWBERRY", "WHEAT"),
    "PET_CAFE": ("MILK", "EGG"),
    "PIZZA_SHOP": ("WHEAT", "TOMATO"),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MELON"),
    "YARN_STORE": ("WOOL",),
}

def official_market_price(item, inventory):
    params = MARKET_PARAMS.get(item)
    if not params:
        return 1
    base = params["base"]
    T = params["T"]
    diff = 10000 - inventory
    if diff >= 0:
        fn = params["below_func"]
        factor = (diff / T) ** 0.5 if fn == "sqrt" else (diff / T)
        return max(1, math.floor(base * (1 + factor)))
    else:
        surplus = inventory - 10000
        return max(1, math.floor(base * math.exp(-surplus / T)))

def hire_cost(n_already_today):
    a, b = 1, 1
    for _ in range(n_already_today):
        a, b = b, a + b
    return a

print("Constants verified!")
