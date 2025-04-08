import pygame
import numpy as np
import random
import config
from scipy.ndimage import gaussian_filter

def generate_map(grid, seed):
    """Génère une carte procédurale avec un seed donné en utilisant numpy random."""
    random.seed(seed)
    np.random.seed(seed)

    # --- Generate Terrain Height using numpy random ---
    terrain_height = np.zeros(config.GRID_WIDTH, dtype=int)
    base_height = config.GRID_HEIGHT // 2
    amplitude = config.GRID_HEIGHT // 3  # Increased amplitude for more varied terrain

    # Generate a random heightmap
    heightmap = np.random.rand(config.GRID_WIDTH)

    # Smooth the heightmap using a Gaussian filter
    heightmap = gaussian_filter(heightmap, sigma=8)  # Adjust sigma for smoothness

    for x in range(config.GRID_WIDTH):
        # Map heightmap value to terrain height
        terrain_height[x] = base_height + int(amplitude * heightmap[x])

    # --- Generate the Ground ---
    for x in range(config.GRID_WIDTH):
        for y in range(terrain_height[x], config.GRID_HEIGHT):
            grid[y, x] = config.STONE # Ground is stone

            # Add a layer of dirt on top
            if y == terrain_height[x]:
                grid[y, x] = config.DIRT

            # Add gravel pockets
            if y > terrain_height[x] and random.random() < 0.10: # Increased gravel frequency
                grid[y, x] = config.GRAVEL

    # --- Create Caves ---
    for _ in range(config.GRID_WIDTH // 4):  # Generate a number of caves
        start_x = random.randint(0, config.GRID_WIDTH - 1)
        start_y = random.randint(config.GRID_HEIGHT // 4, config.GRID_HEIGHT - 1)
        cave_carver(grid, start_x, start_y)

    # --- Generate Mountains ---
    for x in range(config.GRID_WIDTH):
        if random.random() < 0.01: # Increased mountain frequency
            mountain_height = random.randint(4, 6)  # Reduced mountain height
            mountain_top = terrain_height[x] - mountain_height
            if mountain_top > 0:
                for y in range(mountain_top, terrain_height[x]):
                    grid[y, x] = config.STONE

    # --- Generate Trees ---
    for x in range(config.GRID_WIDTH):
        if random.random() < 0.05: # Increased tree frequency
            tree_height = random.randint(4, 7)
            tree_top = terrain_height[x] - tree_height
            if tree_top > 0 and grid[terrain_height[x], x] != config.EMPTY:  # Check if the ground is solid
                for y in range(tree_top, terrain_height[x]):
                    grid[y, x] = config.WOOD

    # --- Generate Ore ---
    for row in range(config.GRID_HEIGHT // 4, config.GRID_HEIGHT):
        for col in range(config.GRID_WIDTH):
            if grid[row, col] != config.EMPTY and random.random() < 0.005: # Ore frequency
                grid[row, col] = config.IRON_ORE

def cave_carver(grid, start_x, start_y):
    """Carves a cave system using a random walk algorithm."""
    x, y = start_x, start_y
    for _ in range(50):  # Length of the cave
        if 0 <= x < config.GRID_WIDTH and 0 <= y < config.GRID_HEIGHT:
            grid[y, x] = config.EMPTY  # Carve the cave
            # Randomly move to a neighboring block
            x += random.randint(-1, 1)
            y += random.randint(-1, 1)