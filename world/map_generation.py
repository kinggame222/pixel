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

def generate_chunk(chunk_array, chunk_x, chunk_y, seed, get_chunk_seed=None):
    """Generates terrain for a chunk in Terraria style with biomes."""
    # --- DEBUG: Confirm function execution ---
    # (Debug prints removed)
    
    # Utilise un seed unique par chunk si fourni
    if get_chunk_seed is not None:
        world_seed = get_chunk_seed(seed, chunk_x, chunk_y)
    else:
        world_seed = seed
    perlin = PerlinNoise(seed=world_seed)
    
    # Global world coordinates
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # Calculate absolute vertical position of this chunk in the world
    absolute_y = world_offset_y
    
    # STEP 1: Generate the basic terrain heightmap
    # For chunks below the surface, we still calculate the surface height
    # but use it just for reference
    heightmap = np.zeros(config.CHUNK_SIZE, dtype=int)
    
    # Generate heightmap using biome properties per column
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        # Get the biome for this column using advanced noise selection
        biome = get_biome(world_x, 0, seed)
        
        # Constants from biome properties
        SURFACE_BLOCK = biome.surface_block
        DIRT_DEPTH = biome.dirt_depth
        TREE_DENSITY = biome.tree_density
        ORE_RARITY = biome.ore_rarity
        BASE_HEIGHT = biome.base_height
        HEIGHT_VARIATION = biome.height_variation
        
        # Scale factors for noise
        terrain_scale_x = 0.008  # Encore plus petites = collines plus larges et douces
        terrain_scale_y = 0.01
        cave_scale = 0.045  # Caves plus irrégulières
        ore_scale = 0.035  # Ores plus irréguliers

        # Ajout de plateaux et de falaises
        plateau_noise_scale = 0.002
        plateau_threshold = 0.8 # Moins de plateaux

        # Add low-frequency noise for large-scale terrain variation
        large_scale_variation = octave_noise(perlin, world_x * 0.001, 0, octaves=2) * 60  # Significantly increased multiplier for more dramatic large scale variation
        
        # Plateaux plats
        plateau_val = octave_noise(perlin, world_x * plateau_noise_scale, 0, octaves=1)
        if plateau_val > plateau_threshold:
            plateau_offset = 10 # Plateaux un peu plus hauts
        else:
            plateau_offset = 0

        # Falaise abrupte
        cliff_val = octave_noise(perlin, world_x * 0.02, 0, octaves=1)
        cliff_offset = 0
        if cliff_val > 0.85: # Falaises moins fréquentes
            cliff_offset = int((cliff_val -  0.85) * 40) # Falaises plus hautes
        
        # Calculate surface height using 1D noise for the x-coordinate
        # This ensures consistent terrain across the x-axis
        noise_val = octave_noise(perlin, world_x * terrain_scale_x, 0, octaves=4, persistence=0.6) # Fewer octaves, higher persistence for smoother hills
        # --- SAFETY CLAMP --- Limit noise_val to expected range
        noise_val = max(-1.0, min(noise_val, 1.0))
        
        # Variable base height using noise
        base_offset = octave_noise(perlin, world_x * 0.005, 0, octaves=2) * 25  # Increased base variation multiplier
        
        # Map noise to surface height
        # Significantly increase the impact of HEIGHT_VARIATION and noise_val
        # Reduce the multiplier significantly to avoid extreme amplification
        local_surface = BASE_HEIGHT + int(base_offset) + int(HEIGHT_VARIATION * 2.5 * (noise_val * 2 - 1)) + int(large_scale_variation) + plateau_offset + cliff_offset
        heightmap[x] = local_surface
    
    # Ajout de trous/creux de surface
    for x in range(2, config.CHUNK_SIZE-2):
        hole_noise = octave_noise(perlin, (world_offset_x + x) * 0.03, 0, octaves=2)
        if hole_noise > 0.85:
            heightmap[x] += 6  # Creuse un trou
    
    # Apply more aggressive smoothing to the heightmap
    heightmap = gaussian_filter(heightmap, sigma=3.5).astype(int)  # Slightly reduced sigma to retain some of the new variation
    
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
                
                # ENHANCED ORE DISTRIBUTION - REDUCED ORE GENERATION
                # Use different noise patterns for different ore types
                ore_noise_1 = octave_noise(perlin, world_x * ore_scale, world_y * ore_scale, octaves=3)
                ore_noise_2 = octave_noise(perlin, world_x * ore_scale * 1.7, world_y * ore_scale * 1.7, octaves=2)
                ore_noise_3 = octave_noise(perlin, world_x * ore_scale * 0.5, world_y * ore_scale * 0.5, octaves=4)
                
                # Depth-based ore distribution - REDUCED ORE GENERATION
                if depth > 40 and ore_noise_1 > 0.85 * ORE_RARITY:  # Deeper and rarer diamond
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif depth > 25 and ore_noise_2 > 0.80 * ORE_RARITY:  # Rarer iron
                    chunk_array[y, x] = config.IRON_ORE
                elif depth > 8 and ore_noise_3 > 0.78 * ORE_RARITY:  # Rarer gravel
                    chunk_array[y, x] = config.GRAVEL
                # Add sand patches using noise
                elif 5 < depth < 25 and ore_noise_2 > 0.85: # Rarer sand patches
                    chunk_array[y, x] = config.SAND

                # Grosse poche de minerais
                ore_blob = octave_noise(perlin, world_x * ore_scale * 0.5, world_y * ore_scale * 0.5, octaves=2)
                if ore_blob > 0.92 and depth > 15: # Much rarer ore blobs
                    chunk_array[y, x] = config.IRON_ORE
    
    # --- DEBUG: Force a specific block to be empty after terrain fill ---
    force_empty_x, force_empty_y = 10, 25 # Coordinates within the chunk
    if chunk_x == 0 and chunk_y == 0:
        if 0 <= force_empty_y < config.CHUNK_SIZE and 0 <= force_empty_x < config.CHUNK_SIZE:
            # print(f"[Chunk ({chunk_x},{chunk_y})] Forcing block ({force_empty_x},{force_empty_y}) to EMPTY.") # Keep commented unless needed
            chunk_array[force_empty_y, force_empty_x] = config.EMPTY
        else:
            pass # print(f"[Chunk ({chunk_x},{chunk_y})] ERROR: Force empty coordinates ({force_empty_x},{force_empty_y}) out of bounds.")
    
    # STEP 3: Generate caves
    """
    # Define cave scales here for clarity
    main_cave_scale = 0.045
    blockhead_cave_scale = 0.08
    mini_cave_scale = 0.09
    deep_cave_scale = 0.025 # Even lower frequency for potentially larger cave systems

    # --- DEBUG: Flag to print only once per chunk for a specific coordinate ---
    debug_printed_for_coord = False
    debug_x, debug_y = 10, 15 # Coordinates within the chunk to debug
    debug_surface_height_printed = False # Flag for surface height print

    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]
        
        # --- DEBUG: Print surface height for the debug column ---
        # if x == debug_x and not debug_surface_height_printed:
        #     print(f"[Chunk ({chunk_x},{chunk_y}) Column {x}] Calculated Surface Height: {surface_height}")
        #     debug_surface_height_printed = True

        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            depth = world_y - surface_height

            # --- DEBUG: Basic loop check for the target coordinate ---
            # if x == debug_x and y == debug_y:
            #     print(f"[Chunk ({chunk_x},{chunk_y}) Coord ({x},{y})] Loop Reached. WorldY={world_y}, SurfaceHeight={surface_height}, Calculated Depth={depth}")

            # --- DEBUG: Print values for the target coordinate ---
            is_debug_coord = (x == debug_x and y == debug_y)
            
            # --- Main Cave Layer --- (Slightly less frequent, smaller clearings)
            if depth > 2:
                cave_noise1 = octave_noise(perlin, world_x * main_cave_scale, world_y * main_cave_scale, octaves=3)
                cave_noise2 = octave_noise(perlin, world_y * main_cave_scale * 0.5, world_x * main_cave_scale * 0.5, octaves=2)
                combined_cave = cave_noise1 * 0.7 + cave_noise2 * 0.3
                cave_threshold = 0.6 # Adjusted threshold
                
                # --- DEBUG ---
                # if is_debug_coord:
                #     print(f"[Chunk ({chunk_x},{chunk_y}) Coord ({x},{y})] MainCave: Depth={depth}, Noise={combined_cave:.3f}, Threshold={cave_threshold:.3f}, ConditionMet={combined_cave > cave_threshold}")

                if combined_cave > cave_threshold:
                    # Clear only the current block for this layer
                    chunk_array[y, x] = config.EMPTY

            # --- Additional Blockhead/Terraria style caves --- (Less frequent)
            if depth > 5:
                blockhead_noise = octave_noise(perlin, world_x * blockhead_cave_scale, world_y * blockhead_cave_scale, octaves=2)
                blockhead_threshold = 0.75 # Increased threshold
                
                # --- DEBUG ---
                # if is_debug_coord:
                #     print(f"[Chunk ({chunk_x},{chunk_y}) Coord ({x},{y})] BlockheadCave: Depth={depth}, Noise={blockhead_noise:.3f}, Threshold={blockhead_threshold:.3f}, ConditionMet={blockhead_noise > blockhead_threshold}")

                if blockhead_noise > blockhead_threshold: 
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            xx = x + dx
                            yy = y + dy
                            if 0 <= xx < config.CHUNK_SIZE and 0 <= yy < config.CHUNK_SIZE:
                                chunk_array[yy, xx] = config.EMPTY
            
            # Mini-cavernes proches de la surface (Less frequent)
            if 2 < depth < 8:
                mini_cave = octave_noise(perlin, world_x * mini_cave_scale, world_y * mini_cave_scale, octaves=1)
                mini_threshold = 0.9 # Increased threshold
                
                # --- DEBUG ---
                # if is_debug_coord:
                #      print(f"[Chunk ({chunk_x},{chunk_y}) Coord ({x},{y})] MiniCave: Depth={depth}, Noise={mini_cave:.3f}, Threshold={mini_threshold:.3f}, ConditionMet={mini_cave > mini_threshold}")

                if mini_cave > mini_threshold: 
                    chunk_array[y, x] = config.EMPTY

            # --- Deep Underground Cave System (Continuous across chunks) ---
            # This noise check happens regardless of other cave types
            if depth > 10: # Only start deep caves below a certain depth
                # Use a lower frequency noise for larger, more connected systems
                deep_cave_noise = octave_noise(perlin, world_x * deep_cave_scale, world_y * deep_cave_scale, octaves=4, persistence=0.6)
                # Adjust threshold based on depth - caves become more likely deeper down
                deep_threshold = 0.60 - (depth * 0.0006) # Lower base threshold, slightly faster decrease with depth
                
                # --- DEBUG ---
                # if is_debug_coord:
                #     print(f"[Chunk ({chunk_x},{chunk_y}) Coord ({x},{y})] DeepCave: Depth={depth}, Noise={deep_cave_noise:.3f}, Threshold={deep_threshold:.3f}, ConditionMet={deep_cave_noise > deep_threshold}")
                    # debug_printed_for_coord = True # Keep this commented out for now to see all prints for the coord

                if deep_cave_noise > deep_threshold:
                    # Clear a slightly larger area for more open deep caves
                    # Increase clearing range for potentially larger open caves
                    for dx in range(-2, 3):
                        for dy in range(-2, 3):
                            # Check bounds before accessing chunk_array
                            check_x, check_y = x + dx, y + dy
                            if 0 <= check_x < config.CHUNK_SIZE and 0 <= check_y < config.CHUNK_SIZE:
                                # Ensure we don't overwrite bedrock
                                if chunk_array[check_y, check_x] != config.BEDROCK:
                                    chunk_array[check_y, check_x] = config.EMPTY
    """
    # Force additional cave formation near spawn in the origin chunk (0,0)
    # Keep this for a guaranteed open area at spawn
    if chunk_x == 0 and chunk_y == 0:
        center = config.CHUNK_SIZE // 2
        for i in range(config.CHUNK_SIZE):
            for j in range(config.CHUNK_SIZE):
                if math.hypot(i - center, j - center) < 2:
                    chunk_array[j, i] = config.EMPTY
    
    # STEP 4: Generate trees and biome-specific decorations
    for x in range(config.CHUNK_SIZE):
        surface_height = heightmap[x]
        local_surface_y = surface_height - world_offset_y

        if 0 <= local_surface_y < config.CHUNK_SIZE:
            # Add biome-specific decorations
            # Groupes de fleurs/cactus
            if biome.name == "Plains" and random.random() < 0.08:
                for fx in range(-1, 2):
                    if 0 <= x+fx < config.CHUNK_SIZE and local_surface_y-1 >= 0:
                        chunk_array[local_surface_y-1, x+fx] = config.FLOWER
            elif biome.name == "Desert" and random.random() < 0.04:
                for fx in range(-1, 2):
                    if 0 <= x+fx < config.CHUNK_SIZE and local_surface_y-1 >= 0:
                        chunk_array[local_surface_y-1, x+fx] = config.CACTUS
            elif biome.name == "Snow" and random.random() < 0.08:
                chunk_array[local_surface_y, x] = config.SNOW_LAYER

            # Generate trees with varied shapes with reduced density
            if random.random() < TREE_DENSITY * 0.5:  # Reduced tree probability by 50%
                tree_height = random.randint(3, 10)
                for ty in range(tree_height):
                    if 0 <= local_surface_y - ty < config.CHUNK_SIZE:
                        chunk_array[local_surface_y - ty, x] = config.WOOD
                for ly in range(tree_height - 2, tree_height + 2):
                    leaf_width = random.randint(2, 4)
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
                    water_depth = np.random.randint(2, 5)  # Random water depth between 2-4 blocks
                    
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