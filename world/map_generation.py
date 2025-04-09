import random
from core import config
import numpy as np
from scipy.ndimage import gaussian_filter

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

def generate_chunk_terrain(chunk_array, chunk_x, chunk_y, seed):
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
    dirt_scale = 0.1         # Scale for dirt thickness variation
    
    # Global world position offsets
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # === TERRARIA-STYLE WORLD SETTINGS ===
    SKY_LEVEL = -50           # Where the sky begins
    SURFACE_LEVEL = 80       # Base surface height
    MIN_DIRT_DEPTH = 5       # Minimum dirt depth
    MAX_DIRT_DEPTH = 25      # Maximum dirt depth
    STONE_DEPTH = 50         # Depth of stone below dirt
    BEDROCK_LEVEL = 300      # Where bedrock begins
    
    # ===== STEP 1: Generate the base terrain heightmap with OVERLAP for smooth transitions =====
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
                chunk_array[y, x] = config.EMPTY
            elif world_y < absolute_surface_height:
                chunk_array[y, x] = config.EMPTY
            elif world_y == absolute_surface_height:
                chunk_array[y, x] = config.GRASS
            elif world_y < absolute_surface_height + dirt_depth:
                chunk_array[y, x] = config.DIRT
            elif world_y < absolute_surface_height + dirt_depth + STONE_DEPTH:
                chunk_array[y, x] = config.STONE
            elif world_y >= BEDROCK_LEVEL:
                chunk_array[y, x] = config.BEDROCK
            else:
                chunk_array[y, x] = config.STONE
    
    # ===== STEP 3: Generate cave systems =====
    cave_frequency = 0.05
    cave_threshold = 0.6  # Adjust for more/less caves
    
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            if chunk_array[y, x] == config.EMPTY:
                continue
            
            cave_noise1 = octave_noise(perlin, world_x * cave_frequency, world_y * cave_frequency, octaves=3)
            cave_noise2 = octave_noise(perlin, world_x * cave_frequency * 2 + 100, world_y * cave_frequency * 2, octaves=2)
            cave_noise3 = octave_noise(perlin, world_x * cave_frequency * 5 + 500, world_y * cave_frequency * 5 + 500, octaves=1)
            
            depth_factor = min(1.0, (world_y - absolute_surface_height) / 100.0) * 0.2
            
            main_cave = cave_noise1 > cave_threshold - depth_factor
            secondary_cave = cave_noise2 > cave_threshold + 0.05
            detail_cave = cave_noise3 > 0.65 and (cave_noise1 > 0.4 or cave_noise2 > 0.4)
            
            if main_cave or secondary_cave or detail_cave:
                chunk_array[y, x] = config.EMPTY
    
    # ===== STEP 4: Add ore deposits =====
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            if chunk_array[y, x] != config.STONE:
                continue
                
            depth = world_y - SURFACE_LEVEL
            normalized_depth = min(1.0, depth / 200.0)
            
            iron_noise = octave_noise(perlin, world_x * ore_scale, world_y * ore_scale, octaves=2)
            diamond_noise = octave_noise(perlin, world_x * ore_scale * 0.6 + 200, world_y * ore_scale * 0.6 + 300, octaves=3)
            gravel_noise = octave_noise(perlin, world_x * ore_scale * 1.5 + 400, world_y * ore_scale * 1.5 + 500, octaves=1)
            
            if normalized_depth > 0.7 and diamond_noise > 0.75:
                chunk_array[y, x] = config.DIAMOND_ORE
            elif normalized_depth > 0.4 and iron_noise > 0.7:
                chunk_array[y, x] = config.IRON_ORE
            elif gravel_noise > 0.85:
                chunk_array[y, x] = config.GRAVEL
    
    return chunk_array