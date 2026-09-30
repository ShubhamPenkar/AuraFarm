"""
Prototype test script for AuraFarm development and benchmarking.
"""
import time
import math
from kaggle_environments import make

# Exact market constants from kaggriculture.py
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

SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]

def bfs_next_step(start_pos, target_pos, board_size=10):
    """Finds next move towards target_pos using BFS."""
    sx, sy = start_pos
    tx, ty = target_pos
    if sx == tx and sy == ty:
        return "PASS"
    
    queue = [(sx, sy, None)]
    visited = {(sx, sy)}
    moves = [("NORTH", 0, -1), ("SOUTH", 0, 1), ("EAST", 1, 0), ("WEST", -1, 0)]
    
    while queue:
        cx, cy, first_move = queue.pop(0)
        if cx == tx and cy == ty:
            return first_move
        for move_name, dx, dy in moves:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < board_size and 0 <= ny < board_size and (nx, ny) not in visited:
                visited.add((nx, ny))
                fm = first_move if first_move is not None else move_name
                queue.append((nx, ny, fm))
    return "PASS"

print("Prototype module loaded successfully.")
