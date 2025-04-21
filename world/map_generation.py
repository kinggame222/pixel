import pygame
import numpy as np
import random
import core.config as config
from scipy.ndimage import gaussian_filter
import math
try:
    # Import the new library
    from perlin_noise import PerlinNoise as PerlinNoiseGenerator
except ImportError:
    print("ERREUR: Le module 'perlin-noise' n'est pas installé. Installez-le avec 'pip install perlin-noise'")
    raise

from world.biomes import get_biome

def generate_chunk(chunk_array, chunk_x, chunk_y, seed, get_chunk_seed=None):
    """Generates terrain for a chunk in Terraria style with biomes."""
    # (Debug prints removed)
    
    # Utilise un seed unique par chunk si fourni
    if get_chunk_seed is not None:
        world_seed = get_chunk_seed(seed, chunk_x, chunk_y)
    else:
        world_seed = seed

    # Create noise generator instances with the world seed
    # You might need different instances with different octave counts
    noise_gen_low_freq = PerlinNoiseGenerator(seed=world_seed, octaves=2)
    noise_gen_med_freq = PerlinNoiseGenerator(seed=world_seed, octaves=4)
    noise_gen_high_freq = PerlinNoiseGenerator(seed=world_seed, octaves=1)
    noise_gen_ore_1 = PerlinNoiseGenerator(seed=world_seed, octaves=3)
    noise_gen_ore_2 = PerlinNoiseGenerator(seed=world_seed, octaves=2)
    noise_gen_ore_3 = PerlinNoiseGenerator(seed=world_seed, octaves=4)
    noise_gen_ore_blob = PerlinNoiseGenerator(seed=world_seed, octaves=2)
    noise_gen_hole = PerlinNoiseGenerator(seed=world_seed, octaves=2)

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
        biome = get_biome(world_x, 0, seed)
        
        # Constants from biome properties
        SURFACE_BLOCK = biome.surface_block
        DIRT_DEPTH = biome.dirt_depth
        TREE_DENSITY = biome.tree_density
        ORE_RARITY = biome.ore_rarity
        BASE_HEIGHT = biome.base_height
        HEIGHT_VARIATION = biome.height_variation
        
        # Scale factors for noise (may need adjustment for perlin-noise)
        terrain_scale_x = 0.008
        # terrain_scale_y = 0.01 # Not used for 1D heightmap noise
        cave_scale = 0.045
        ore_scale = 0.035
        plateau_noise_scale = 0.002
        cliff_noise_scale = 0.02 # Renamed for clarity
        large_scale_variation_scale = 0.001
        base_offset_scale = 0.005
        hole_scale = 0.03

        # Use the new noise generators
        # Note: perlin-noise takes a list/tuple of coordinates [x] or [x, y]
        large_scale_variation = noise_gen_low_freq([world_x * large_scale_variation_scale]) * 60

        plateau_val = noise_gen_high_freq([world_x * plateau_noise_scale])
        plateau_offset = 10 if plateau_val > plateau_threshold else 0

        cliff_val = noise_gen_high_freq([world_x * cliff_noise_scale])
        cliff_offset = int((cliff_val - 0.85) * 40) if cliff_val > 0.85 else 0

        noise_val = noise_gen_med_freq([world_x * terrain_scale_x]) # persistence/lacunarity are part of PerlinNoiseGenerator init if needed

        base_offset = noise_gen_low_freq([world_x * base_offset_scale]) * 25

        # Map noise to surface height (adjust multipliers as needed for the new noise range)
        # perlin-noise output range is roughly [-0.7, 0.7] for 1D/2D
        local_surface = BASE_HEIGHT + int(base_offset) + int(HEIGHT_VARIATION * 2.5 * noise_val) + int(large_scale_variation) + plateau_offset + cliff_offset
        heightmap[x] = local_surface
    
    # Ajout de trous/creux de surface
    for x in range(2, config.CHUNK_SIZE-2):
        hole_noise = noise_gen_hole([(world_offset_x + x) * hole_scale])
        if hole_noise > 0.85: # Adjust threshold if needed
            heightmap[x] += 6
    
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
                ore_noise_1 = noise_gen_ore_1([world_x * ore_scale, world_y * ore_scale])
                ore_noise_2 = noise_gen_ore_2([world_x * ore_scale * 1.7, world_y * ore_scale * 1.7])
                ore_noise_3 = noise_gen_ore_3([world_x * ore_scale * 0.5, world_y * ore_scale * 0.5])

                # Adjust thresholds based on the new noise range [-0.7, 0.7] approx
                # Example: old threshold 0.85 might become 0.6? Needs tuning.
                diamond_threshold = 0.6 * ORE_RARITY # Tuned threshold
                iron_threshold = 0.55 * ORE_RARITY # Tuned threshold
                gravel_threshold = 0.5 * ORE_RARITY # Tuned threshold
                sand_threshold = 0.6 # Tuned threshold

                if depth > 40 and ore_noise_1 > diamond_threshold:
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif depth > 25 and ore_noise_2 > iron_threshold:
                    chunk_array[y, x] = config.IRON_ORE
                elif depth > 8 and ore_noise_3 > gravel_threshold:
                    chunk_array[y, x] = config.GRAVEL
                elif 5 < depth < 25 and ore_noise_2 > sand_threshold:
                    chunk_array[y, x] = config.SAND

                ore_blob = noise_gen_ore_blob([world_x * ore_scale * 0.5, world_y * ore_scale * 0.5])
                blob_threshold = 0.65 # Tuned threshold
                if ore_blob > blob_threshold and depth > 15:
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