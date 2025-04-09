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
    """Generates terrain for a single chunk in Terraria style."""
    # Use a fixed seed for the entire world to ensure continuity
    world_seed = seed
    random.seed(world_seed)  # Use the same seed for deterministic generation
    
    # Create a single Perlin noise generator for the entire world
    perlin = PerlinNoise(seed=world_seed)
    
    # Noise scales and parameters
    surface_scale = 0.02     # Surface terrain frequency (smaller = smoother)
    cave_scale = 0.05        # Cave system frequency
    ore_scale = 0.08         # Ore distribution frequency
    
    # Global world position offsets
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # ===== STEP 1: Generate the base terrain heightmap =====
    # This is the key for Terraria-like worlds: we need a consistent heightmap that
    # doesn't change with vertical chunk position
    heightmap = []
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        # Generate the surface heightmap using ONLY x-coordinate (no y)
        # This ensures consistent terrain across all vertical chunks
        noise_val = octave_noise(perlin, 
                                world_x * surface_scale, 
                                0,  # IMPORTANT: Fixed y value for consistent terrain
                                octaves=4, 
                                persistence=0.5, 
                                lacunarity=2.0)
        
        # Map noise to terrain height with a bias toward the middle
        # Set a global height that's independent of chunk_y
        global_base_height = 128  # A fixed global height for the surface
        height_variation = 32     # Allow height variation
        
        # Calculate the absolute surface height in the world
        absolute_surface_height = global_base_height + int((noise_val * 2 - 1) * height_variation)
        
        # Convert to local chunk coordinates
        local_surface_height = absolute_surface_height - world_offset_y
        
        # The heightmap may be outside the chunk bounds
        # But we still track it for consistent world generation
        heightmap.append(local_surface_height)
    
    # ===== STEP 2: Fill the chunk with appropriate blocks =====
    for x in range(config.CHUNK_SIZE):
        surface_height = heightmap[x]
        world_x = world_offset_x + x
        
        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            
            # Determine if this position is below, at, or above the surface
            if surface_height >= 0 and y < surface_height:
                # Below surface
                depth_from_surface = surface_height - y
                if depth_from_surface > 3:
                    chunk_array[y, x] = config.STONE
                else:
                    chunk_array[y, x] = config.DIRT
            elif surface_height >= 0 and y == surface_height:
                # At surface
                chunk_array[y, x] = config.GRASS
            else:
                # Above surface or surface is outside this chunk
                chunk_array[y, x] = config.EMPTY
    
    # ===== STEP 3: Generate cave systems =====
    # Use 3D noise with depth to ensure caves don't duplicate vertically
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            # Only generate caves below the surface
            local_height = heightmap[x]
            if chunk_array[y, x] != config.EMPTY and (local_height < 0 or y < local_height - 2):
                # Use real world depth for consistent caves
                depth = world_y / 256.0  # Normalize depth
                
                # Use different noise frequencies for varied caves
                cave_noise1 = perlin.noise(world_x * cave_scale, world_y * cave_scale)
                cave_noise2 = perlin.noise(world_x * cave_scale * 2, world_y * cave_scale * 2 + 100)
                
                # Combine noise values for more interesting caves
                # Make caves bigger at deeper depths
                cave_threshold = 0.7 - depth * 0.2
                if cave_noise1 > cave_threshold or cave_noise2 > cave_threshold + 0.1:
                    chunk_array[y, x] = config.EMPTY
    
    # ===== STEP 4: Add ore deposits =====
    # Use absolute depth to determine ore distribution
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            # Only add ores in stone
            if chunk_array[y, x] == config.STONE:
                # Use global depth for consistent ore distribution
                absolute_depth = world_y
                normalized_depth = absolute_depth / 256.0  # Normalize to 0-1 range
                
                # Generate ore noise
                ore_noise = perlin.noise(world_x * ore_scale, world_y * ore_scale)
                
                # Distribution by depth like in Terraria
                if normalized_depth > 0.7 and ore_noise > 0.75:
                    # Diamond appears deep underground
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif normalized_depth > 0.4 and ore_noise > 0.7:
                    # Iron appears in the middle layers
                    chunk_array[y, x] = config.IRON_ORE
                elif ore_noise > 0.8:
                    # Occasional gravel pockets
                    chunk_array[y, x] = config.GRAVEL
    
    # ===== STEP 5: Add surface features =====
    # Only add surface features if this chunk contains the surface
    for x in range(config.CHUNK_SIZE):
        local_height = heightmap[x]
        # Skip if surface is outside this chunk
        if local_height < 0 or local_height >= config.CHUNK_SIZE:
            continue
            
        world_x = world_offset_x + x
        
        # Only place trees on grass blocks
        if x > 1 and x < config.CHUNK_SIZE - 2 and chunk_array[local_height, x] == config.GRASS:
            # Deterministic tree placement based on world position
            tree_seed = (world_x * 761) % 1000
            random.seed(tree_seed)
            
            if random.random() < 0.08:  # 8% chance for a tree
                # Tree height: 4-7 blocks
                tree_height = random.randint(4, 7)
                
                # Place tree trunk if it fits in chunk
                for y_offset in range(tree_height):
                    tree_y = local_height - y_offset - 1
                    if 0 <= tree_y < config.CHUNK_SIZE:
                        chunk_array[tree_y, x] = config.WOOD
    
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
            
            if cave_noise > 0.85:
                chunk_array[y, x] = config.EMPTY
                # Carve out a small cave 
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        if 0 <= x + dx < config.CHUNK_SIZE and 0 <= y + dy < config.CHUNK_SIZE:
                            chunk_array[y + dy, x + dx] = config.EMPTY
    return chunk_array

