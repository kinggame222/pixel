import pygame
import numpy as np
import random
import config
from scipy.ndimage import gaussian_filter

# Create a simple Perlin noise implementation
class PerlinNoise:
    def __init__(self, seed=0):
        random.seed(seed)
        self.p = list(range(256))
        random.shuffle(self.p)
        self.p += self.p

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, t, a, b):
        return a + t * (b - a)

    def grad(self, hash, x, y, z):
        h = hash & 15
        u = x if h < 8 else y
        v = y if h < 4 else (x if h == 12 or h == 14 else z)
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    def noise(self, x, y, z=0):
        X = int(x) & 255
        Y = int(y) & 255
        Z = int(z) & 255
        
        x -= int(x)
        y -= int(y)
        z -= int(z)
        
        u = self.fade(x)
        v = self.fade(y)
        w = self.fade(z)
        
        A = self.p[X] + Y
        AA = self.p[A] + Z
        AB = self.p[A + 1] + Z
        B = self.p[X + 1] + Y
        BA = self.p[B] + Z
        BB = self.p[B + 1] + Z
        
        return self.lerp(w, self.lerp(v, self.lerp(u, self.grad(self.p[AA], x, y, z),
                                                 self.grad(self.p[BA], x - 1, y, z)),
                                     self.lerp(u, self.grad(self.p[AB], x, y - 1, z),
                                             self.grad(self.p[BB], x - 1, y - 1, z))),
                         self.lerp(v, self.lerp(u, self.grad(self.p[AA + 1], x, y, z - 1),
                                              self.grad(self.p[BA + 1], x - 1, y, z - 1)),
                                  self.lerp(u, self.grad(self.p[AB + 1], x, y - 1, z - 1),
                                          self.grad(self.p[BB + 1], x - 1, y - 1, z - 1))))

def octave_noise(perlin, x, y, octaves=1, persistence=0.5, lacunarity=2.0):
    total = 0
    frequency = 1
    amplitude = 1
    max_value = 0
    for i in range(octaves):
        total += perlin.noise(x * frequency, y * frequency) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return total / max_value if max_value > 0 else 0

def generate_map(grid, seed):
    """Legacy function to generate a map for the finite world."""
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

def generate_chunk(chunk_array, chunk_x, chunk_y, seed):
    """Generates terrain for a single chunk."""
    # Use a fixed seed for the entire world to ensure continuity
    world_seed = seed
    random.seed(world_seed + hash((chunk_x, chunk_y)) % 100000)  # Only use chunk seed for random features
    
    # Create a single perlin noise generator for the entire world
    perlin = PerlinNoise(seed=world_seed)
    
    # Use very small scale for smooth transitions
    terrain_scale = 0.005  # Reduced from 0.01 for smoother terrain
    cave_scale = 0.02     # Scale for cave generation
    ore_scale = 0.03      # Scale for ore distribution
    
    # Global parameters for world generation
    base_height = 8       # Base terrain height
    amplitude = 5         # Height variation
    
    # Global world position offsets
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # Generate a continuous heightmap across all chunks
    for x in range(config.CHUNK_SIZE):
        # Get real world coordinates
        world_x = world_offset_x + x
        
        # Generate base terrain (use 2D noise for consistent heightmap)
        noise_val = octave_noise(perlin, 
                               world_x * terrain_scale, 
                               0,  # Use a fixed y for the heightmap generation
                               octaves=6,
                               persistence=0.5,
                               lacunarity=2.0)
        
        # Map noise to terrain height (consistent across all chunks)
        height = int(base_height + (noise_val * 2 - 1) * amplitude)
        
        # Ensure height is within chunk bounds (important for continuous terrain)
        height = min(config.CHUNK_SIZE - 1, max(0, height))
        
        # Fill the column with blocks based on height
        for y in range(config.CHUNK_SIZE):
            # Get absolute world y coordinate
            world_y = world_offset_y + y
            
            # Determine if this block is below the terrain surface
            if y >= height:
                # Use 3D noise for cave generation (continuous across chunks)
                cave_noise = octave_noise(perlin, 
                                       world_x * cave_scale,
                                       world_y * cave_scale,
                                       octaves=3)
                
                # Create caves in deeper areas
                if cave_noise > 0.65 and y > height + 2:
                    chunk_array[y, x] = config.EMPTY
                else:
                    # Surface layer is dirt
                    if y == height:
                        chunk_array[y, x] = config.DIRT
                    else:
                        # Generate ores using 3D noise (continuous across chunks)
                        ore_noise = octave_noise(perlin, 
                                             world_x * ore_scale,
                                             world_y * ore_scale,
                                             0.7,  # Different z for ore variation
                                             octaves=2)
                        
                        depth = y - height
                        # Deeper = more valuable ores
                        if ore_noise > 0.8 and depth > 8:
                            chunk_array[y, x] = config.DIAMOND_ORE
                        elif ore_noise > 0.7 and depth > 4:
                            chunk_array[y, x] = config.IRON_ORE
                        elif ore_noise > 0.6 and depth > 2:
                            chunk_array[y, x] = config.GRAVEL
                        else:
                            chunk_array[y, x] = config.STONE
            else:
                # Above ground is air
                chunk_array[y, x] = config.EMPTY
    
    # Generate trees with a continuous pattern
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        
        # Find the surface height for this x coordinate
        surface_y = -1
        for y in range(config.CHUNK_SIZE):
            if chunk_array[y, x] != config.EMPTY:
                surface_y = y - 1  # The block above the first non-air block
                break
        
        # Only place trees on valid surfaces with a deterministic but distributed pattern
        if surface_y >= 0 and world_x % 11 == 0:  # Use prime number for natural distribution
            # Deterministic random based on world position (not chunk position)
            r_val = (world_x * 19373 + world_seed) % 100
            if r_val < 30:  # 30% chance for a tree
                tree_height = 3 + (r_val % 3)  # Height of 3-5 blocks
                
                # Check if tree fits in this chunk
                if surface_y - tree_height >= 0:
                    for y in range(surface_y - tree_height, surface_y + 1):
                        if 0 <= y < config.CHUNK_SIZE:
                            chunk_array[y, x] = config.WOOD
    
    return chunk_array

def add_features(chunk_array, chunk_x, chunk_y, terrain_height):
    """Add features like trees, caves, etc. to a chunk."""
    # Use consistent seed for features based on chunk position
    feature_seed = hash((chunk_x, chunk_y, "features")) % 1000000
    random.seed(feature_seed)
    
    # Add trees - but only if chunk contains surface terrain
    for x in range(config.CHUNK_SIZE):
        # Make tree placement deterministic but varied
        if (chunk_x * config.CHUNK_SIZE + x) % 7 == 0 and random.random() < 0.7:
            tree_height = random.randint(3, 6)
            top_y = terrain_height[x] - 1
            
            # Make sure tree fits in chunk
            if top_y - tree_height >= 0:
                # Place tree trunk
                for y in range(top_y - tree_height, top_y + 1):
                    if 0 <= y < config.CHUNK_SIZE:
                        chunk_array[y, x] = config.WOOD

    # Add small caves based on deterministic 3D noise
    perlin = PerlinNoise(seed=feature_seed)
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            # Skip air blocks and surface layers
            if chunk_array[y, x] == config.EMPTY or y <= terrain_height[x]:
                continue
                
            # Use 3D noise for caves
            world_x = chunk_x * config.CHUNK_SIZE + x
            world_y = chunk_y * config.CHUNK_SIZE + y
            cave_noise = octave_noise(perlin, world_x * 0.05, world_y * 0.05, octaves=2)
            
            # Create caves where noise value is high
            if cave_noise > 0.75:
                chunk_array[y, x] = config.EMPTY