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
    """Generates terrain for a single chunk in Terraria style with smooth transitions between chunks."""
    # Use a fixed seed for the entire world to ensure continuity
    world_seed = seed
    random.seed(world_seed)  # Use the same seed for deterministic generation
    
    # Create a single Perlin noise generator for the entire world
    perlin = PerlinNoise(seed=world_seed)
    
    # Noise scales and parameters
    surface_scale = 0.02     # Surface terrain frequency (smaller = smoother)
    cave_scale = 0.05        # Cave system frequency
    ore_scale = 0.08         # Ore distribution frequency
    dirt_scale = 0.1        # Scale for dirt thickness variation
    
    # Global world position offsets
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # === TERRARIA-STYLE WORLD SETTINGS ===
    SKY_LEVEL = -50           # Where the sky begins
    SURFACE_LEVEL = 80       # Base surface height
    MIN_DIRT_DEPTH = 5       # Minimum dirt depth
    MAX_DIRT_DEPTH = 25      # Maximum dirt depth
    STONE_DEPTH = 50        # Depth of stone below dirt
    BEDROCK_LEVEL = 300      # Where bedrock begins
    
    # ===== STEP 1: Generate the base terrain heightmap with OVERLAP for smooth transitions =====
    # Generate heightmap with padding on both sides to ensure continuous transitions
    PADDING = 4  # Number of blocks to pad on each side for smooth interpolation
    extended_width = config.CHUNK_SIZE + PADDING * 2
    
    extended_heightmap = []
    extended_dirt_thickness = []  # Store dirt thickness for each column
    
    for x in range(-PADDING, config.CHUNK_SIZE + PADDING):
        world_x = world_offset_x + x
        
        # Generate the main surface heightmap - using world coordinates ensures continuity
        noise_val1 = octave_noise(perlin, 
                                world_x * surface_scale, 
                                0,  # Fixed y for consistent terrain
                                octaves=4, 
                                persistence=0.5, 
                                lacunarity=2.0)
        
        # Add a second frequency for more interesting terrain
        noise_val2 = octave_noise(perlin, 
                                world_x * surface_scale * 2, 
                                100,  # Different phase
                                octaves=2, 
                                persistence=0.25, 
                                lacunarity=2.0)
        
        # Combine the noise values
        combined_noise = (noise_val1 * 0.7) + (noise_val2 * 0.3)
        
        # Calculate the absolute surface height in the world
        height_variation = 30     # Greater height variation
        
        # IMPORTANT: Ensure this is an integer
        absolute_surface_height = int(SURFACE_LEVEL - int((combined_noise * 2 - 1) * height_variation))
        
        # Generate dirt thickness using different noise
        dirt_noise = octave_noise(perlin, world_x * dirt_scale, 500, octaves=2)
        dirt_thickness = MIN_DIRT_DEPTH + int(dirt_noise * (MAX_DIRT_DEPTH - MIN_DIRT_DEPTH))
        
        # Store in extended heightmap
        extended_heightmap.append(absolute_surface_height)
        extended_dirt_thickness.append(dirt_thickness)
    
    # Extract the actual heightmap for this chunk (converted to local coordinates)
    heightmap = []
    dirt_thickness = []
    for i in range(PADDING, PADDING + config.CHUNK_SIZE):
        absolute_height = extended_heightmap[i]
        local_height = int(absolute_height - world_offset_y)
        heightmap.append(local_height)
        dirt_thickness.append(extended_dirt_thickness[i])
    
    # ===== STEP 2: Fill the chunk with appropriate layers =====
    for x in range(config.CHUNK_SIZE):
        # Get the surface height for this column
        surface_height = heightmap[x]
        absolute_surface_height = world_offset_y + surface_height if surface_height >= 0 else 0
        
        # Get the dirt thickness for this column
        dirt_depth = dirt_thickness[x]
        
        for y in range(config.CHUNK_SIZE):
            # Calculate absolute world position
            world_y = world_offset_y + y
            
            # Determine block type based on depth and layers (Terraria-style)
            if world_y < SKY_LEVEL:
                # Sky (clouds could be added here)
                chunk_array[y, x] = config.EMPTY
            elif world_y < absolute_surface_height:
                # Above ground
                chunk_array[y, x] = config.EMPTY
            elif world_y == absolute_surface_height:
                # Surface layer - grass
                chunk_array[y, x] = config.GRASS
            elif world_y < absolute_surface_height + dirt_depth:
                # Dirt layer with variable thickness
                chunk_array[y, x] = config.DIRT
            elif world_y < absolute_surface_height + dirt_depth + STONE_DEPTH:
                # Stone layer
                chunk_array[y, x] = config.STONE
            elif world_y >= BEDROCK_LEVEL:
                # Bedrock at the bottom of the world
                chunk_array[y, x] = config.BEDROCK
            else:
                # Deep stone
                chunk_array[y, x] = config.STONE
    
    # ===== STEP 3: Generate cave systems - USING LARGE-SCALE COHERENT NOISE =====
    cave_frequency = 0.05
    cave_threshold = 0.6  # Adjust for more/less caves
    
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            # Skip if above surface or already empty
            if chunk_array[y, x] == config.EMPTY:
                continue
            
            # Use multiple scales of noise for more natural caves
            # Use 3D noise to create connected cave systems
            cave_noise1 = octave_noise(perlin, world_x * cave_frequency, world_y * cave_frequency, octaves=3)
            cave_noise2 = octave_noise(perlin, world_x * cave_frequency * 2 + 100, world_y * cave_frequency * 2, octaves=2)
            
            # Add a third noise layer for smaller cave features
            cave_noise3 = octave_noise(perlin, world_x * cave_frequency * 5 + 500, world_y * cave_frequency * 5 + 500, octaves=1)
            
            # Make caves larger as depth increases
            depth_factor = min(1.0, (world_y - absolute_surface_height) / 100.0) * 0.2
            
            # Complex cave generation system with multiple noise functions
            main_cave = cave_noise1 > cave_threshold - depth_factor
            secondary_cave = cave_noise2 > cave_threshold + 0.05
            detail_cave = cave_noise3 > 0.65 and (cave_noise1 > 0.4 or cave_noise2 > 0.4)
            
            if main_cave or secondary_cave or detail_cave:
                chunk_array[y, x] = config.EMPTY
    
    # ===== STEP 4: Add ore deposits with ore veins that cross chunk boundaries =====
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            # Skip if not stone or already empty
            if chunk_array[y, x] != config.STONE:
                continue
                
            # Calculate world depth (negative = deeper)
            depth = world_y - SURFACE_LEVEL
            normalized_depth = min(1.0, depth / 200.0)
            
            # Generate ore noise - using different scales for different ore types
            iron_noise = octave_noise(perlin, world_x * ore_scale, world_y * ore_scale, octaves=2)
            diamond_noise = octave_noise(perlin, world_x * ore_scale * 0.6 + 200, world_y * ore_scale * 0.6 + 300, octaves=3)
            gravel_noise = octave_noise(perlin, world_x * ore_scale * 1.5 + 400, world_y * ore_scale * 1.5 + 500, octaves=1)
            
            # Terraria-style ore distribution by depth with coherent veins
            if normalized_depth > 0.7 and diamond_noise > 0.75:
                # Diamond appears deep underground
                chunk_array[y, x] = config.DIAMOND_ORE
            elif normalized_depth > 0.4 and iron_noise > 0.7:
                # Iron appears in the middle layers
                chunk_array[y, x] = config.IRON_ORE
            elif gravel_noise > 0.85:
                # Occasional gravel pockets
                chunk_array[y, x] = config.GRAVEL
    
    # ===== STEP 5: Add surface features (trees, etc.) =====
    for x in range(config.CHUNK_SIZE):
        # Find where the surface is in this column
        surface_block_y = None
        for y in range(config.CHUNK_SIZE):
            if y < config.CHUNK_SIZE - 1 and chunk_array[y, x] == config.EMPTY and chunk_array[y+1, x] == config.GRASS:
                surface_block_y = y + 1
                break
        
        if surface_block_y is None:
            continue  # No surface in this column
        
        # Deterministic tree placement - use absolute world coordinates for consistency
        world_x = world_offset_x + x
        # Make tree placement deterministic but naturally distributed
        # Use a larger scale noise to decide tree placement
        tree_noise = octave_noise(perlin, world_x * 0.1, 0, octaves=1)
        
        # Place trees based on noise value - creates natural clusters and spacing
        if tree_noise > 0.7 and x > 1 and x < config.CHUNK_SIZE - 2:
            # Ensure enough space for tree
            if surface_block_y > 5:  # Need room for the tree
                tree_height = 5 + int(tree_noise * 3)  # Tree height varies based on noise
                
                # Generate tree trunk
                for h in range(1, tree_height + 1):
                    tree_y = surface_block_y - h
                    if 0 <= tree_y < config.CHUNK_SIZE:
                        chunk_array[tree_y, x] = config.WOOD
                
                # Generate leaves (simple version)
                leaf_radius = 2
                for ly in range(-leaf_radius, 1):
                    for lx in range(-leaf_radius, leaf_radius + 1):
                        leaf_y = surface_block_y - tree_height + ly
                        leaf_x = x + lx
                        if (0 <= leaf_y < config.CHUNK_SIZE and 
                            0 <= leaf_x < config.CHUNK_SIZE and
                            chunk_array[leaf_y, leaf_x] == config.EMPTY):
                            # Could add leaves here if you have a leaf block type
                            pass
    
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

