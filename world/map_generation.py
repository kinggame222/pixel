import pygame
import numpy as np
import random
import core.config as config
from scipy.ndimage import gaussian_filter
import math

from world.biomes import get_biome

# Create a simple Perlin noise implementation
class PerlinNoise:
    def __init__(self, seed=config.SEED):
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

def generate_chunk(chunk_array, chunk_x, chunk_y, seed):
    """Generates terrain for a chunk in Terraria style with biomes."""
    # Use a fixed seed for the entire world
    world_seed = seed
    perlin = PerlinNoise(seed=world_seed)
    
    # Global world coordinates
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # Select biome based on world position
    biome = get_biome(world_offset_x, world_offset_y, seed)
    
    # Constants from biome properties
    SURFACE_BLOCK = biome.surface_block
    DIRT_DEPTH = biome.dirt_depth
    TREE_DENSITY = biome.tree_density
    ORE_RARITY = biome.ore_rarity
    BASE_HEIGHT = biome.base_height
    HEIGHT_VARIATION = biome.height_variation
    
    # Scale factors for noise
    terrain_scale_x = 0.015  # Reduced for wider hills
    terrain_scale_y = 0.01  # Variation of chunks vertically
    cave_scale = 0.05  # Scale for cave system (bigger = smaller caves)
    ore_scale = 0.04  # Scale for ore distribution
    
    # Calculate absolute vertical position of this chunk in the world
    absolute_y = world_offset_y
    
    # STEP 1: Generate the basic terrain heightmap
    # For chunks below the surface, we still calculate the surface height
    # but use it just for reference
    heightmap = np.zeros(config.CHUNK_SIZE, dtype=int)
    
    # Generate coherent heightmap across chunks
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        
        # Add low-frequency noise for large-scale terrain variation
        large_scale_variation = octave_noise(perlin, world_x * 0.001, 0, octaves=2) * 15  # Low-frequency noise
        
        # Calculate surface height using 1D noise for the x-coordinate
        # This ensures consistent terrain across the x-axis
        noise_val = octave_noise(perlin, world_x * terrain_scale_x, 0, octaves=6)  # Increased octaves
        
        # Variable base height using noise
        base_offset = octave_noise(perlin, world_x * 0.005, 0, octaves=2) * 10  # Smaller scale for base variation
        
        # Map noise to surface height
        local_surface = BASE_HEIGHT + int(base_offset) + int(HEIGHT_VARIATION * (noise_val * 2 - 1)) + int(large_scale_variation)
        heightmap[x] = local_surface
    
    # Apply more aggressive smoothing to the heightmap
    heightmap = gaussian_filter(heightmap, sigma=3.0).astype(int)  # Increased sigma
    
    # STEP 2: Fill the chunk with appropriate blocks based on its depth
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]
        
        # Use 2D Perlin noise for each (x,y) position
        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            
            # Position relative to surface (negative = above surface, positive = below)
            depth = world_y - surface_height
            
            # TERRAIN LAYERS
            if depth < 0:
                # Above surface = air
                chunk_array[y, x] = config.EMPTY
            elif depth == 0:
                # Surface block (grass instead of dirt)
                chunk_array[y, x] = SURFACE_BLOCK
            elif depth <= DIRT_DEPTH:
                # Dirt layer
                chunk_array[y, x] = config.DIRT
            else:
                # Stone layer by default
                chunk_array[y, x] = config.STONE
                
                # ENHANCED ORE DISTRIBUTION
                # Use different noise patterns for different ore types
                ore_noise_1 = octave_noise(perlin, world_x * ore_scale, world_y * ore_scale, octaves=3)
                ore_noise_2 = octave_noise(perlin, world_x * ore_scale * 1.7, world_y * ore_scale * 1.7, octaves=2)
                ore_noise_3 = octave_noise(perlin, world_x * ore_scale * 0.5, world_y * ore_scale * 0.5, octaves=4)
                
                # Depth-based ore distribution - INCREASED ORE GENERATION
                if depth > 30 and ore_noise_1 > 0.75 * ORE_RARITY:  # Deep ores (diamond) - more common now
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif depth > 20 and ore_noise_2 > 0.70 * ORE_RARITY:  # Medium depth ores (iron) - more common
                    chunk_array[y, x] = config.IRON_ORE
                elif depth > 5 and ore_noise_3 > 0.68 * ORE_RARITY:  # More common shallow ores
                    chunk_array[y, x] = config.GRAVEL
                # Add sand patches using noise
                elif 3 < depth < 20 and ore_noise_2 > 0.80:
                    chunk_array[y, x] = config.SAND
    
    # STEP 3: Generate caves
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]
        
        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            depth = world_y - surface_height
            
            # Only generate caves below the surface
            if depth > 3:  # Start caves a bit below the dirt layer
                # Get noise value for cave generation (true 3D noise)
                cave_noise1 = octave_noise(perlin,
                                      world_x * cave_scale,
                                      world_y * cave_scale,
                                      octaves=3)
                
                # Additional noise sample for more varied caves
                cave_noise2 = octave_noise(perlin,
                                      world_y * cave_scale * 0.5,
                                      world_x * cave_scale * 0.5,
                                      octaves=2)
                
                # Combine noise samples
                combined_cave = cave_noise1 * 0.7 + cave_noise2 * 0.3
                
                # Cave threshold increases with depth (bigger caves deeper down)
                # but with a maximum size
                cave_threshold = min(0.7, 0.55 + depth * 0.001)  # Adjusted threshold
                
                if combined_cave > cave_threshold:
                    chunk_array[y, x] = config.EMPTY
    
    # STEP 4: Generate trees and biome-specific decorations
    for x in range(config.CHUNK_SIZE):
        surface_height = heightmap[x]
        local_surface_y = surface_height - world_offset_y

        if 0 <= local_surface_y < config.CHUNK_SIZE:
            # Add biome-specific decorations
            if biome.name == "Plains" and random.random() < 0.1:
                chunk_array[local_surface_y - 1, x] = config.FLOWER  # Add flowers
            elif biome.name == "Desert" and random.random() < 0.05:
                chunk_array[local_surface_y - 1, x] = config.CACTUS  # Add cacti
            elif biome.name == "Snow" and random.random() < 0.1:
                chunk_array[local_surface_y, x] = config.SNOW_LAYER  # Add snow layers

            # Generate trees with varied shapes
            if random.random() < TREE_DENSITY:
                tree_height = random.randint(4, 8)
                for ty in range(tree_height):
                    if 0 <= local_surface_y - ty < config.CHUNK_SIZE:
                        chunk_array[local_surface_y - ty, x] = config.WOOD
                for ly in range(tree_height - 2, tree_height + 1):
                    leaf_width = 2 if ly == tree_height else 3
                    for lx in range(-leaf_width, leaf_width + 1):
                        if 0 <= x + lx < config.CHUNK_SIZE and 0 <= local_surface_y - ly < config.CHUNK_SIZE:
                            if chunk_array[local_surface_y - ly, x + lx] == config.EMPTY:
                                chunk_array[local_surface_y - ly, x + lx] = config.LEAVES

    # STEP 5: Generate water pools - IMPROVED WATER GENERATION
    water_placed = False  # Track if water has been placed in this chunk
    
    for x in range(config.CHUNK_SIZE):
        surface_height = heightmap[x]
        local_surface_y = surface_height - world_offset_y
        
        # Only process if the surface is in this chunk
        if 0 <= local_surface_y < config.CHUNK_SIZE:
            # Check for depressions or flat areas for water
            if x > 1 and x < config.CHUNK_SIZE - 2:
                # More lenient water placement - any small depression or flat area
                left_height = heightmap[x-1]
                right_height = heightmap[x+1]
                
                # Place water in depressions OR with small random chance in flat areas
                is_depression = (left_height > surface_height or right_height > surface_height)
                is_flat = (abs(left_height - surface_height) <= 1 and abs(right_height - surface_height) <= 1)
                random_pool = np.random.random() < 0.1 and is_flat  # 10% chance for pools on flat ground
                
                if is_depression or random_pool:
                    water_depth = np.random.randint(1, 4)  # Random water depth between 1-3 blocks
                    
                    for wy in range(1, water_depth + 1):
                        water_y = local_surface_y + wy
                        if 0 <= water_y < config.CHUNK_SIZE and chunk_array[water_y, x] == config.EMPTY:
                            chunk_array[water_y, x] = config.WATER
                            water_placed = True
                            
                            # Add water to adjacent blocks if they're empty, for wider pools
                            for dx in [-1, 1]:
                                if 0 <= x + dx < config.CHUNK_SIZE:
                                    if chunk_array[water_y, x + dx] == config.EMPTY:
                                        if water_y + 1 >= config.CHUNK_SIZE or chunk_array[water_y+1, x+dx] != config.EMPTY:
                                            chunk_array[water_y, x + dx] = config.WATER
    
    # STEP 6: Add bedrock at the very bottom of the world
    if world_offset_y + config.CHUNK_SIZE > 200:  # At depth 200+
        for x in range(config.CHUNK_SIZE):
            for y in range(config.CHUNK_SIZE):
                if world_offset_y + y > 200:
                    chunk_array[y, x] = config.BEDROCK
    
    return chunk_array