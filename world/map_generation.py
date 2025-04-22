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

def generate_chunk(chunk_array, chunk_x, chunk_y, world_seed, get_chunk_seed=None):
    """Generates terrain for a chunk in Terraria style with biomes."""
    # Utilise un seed unique par chunk si fourni
    chunk_specific_seed = world_seed
    if get_chunk_seed is not None:
        chunk_specific_seed = get_chunk_seed(chunk_x, chunk_y, world_seed)
    else:
        print(f"Warning: get_chunk_seed not provided for chunk ({chunk_x}, {chunk_y}). Using world seed.")

    # Create a random number generator specific to this chunk
    chunk_random = random.Random(chunk_specific_seed)

    # Create noise generator instances with the world seed
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
    heightmap = np.zeros(config.CHUNK_SIZE, dtype=int)

    # Generate heightmap using biome properties per column
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        biome = get_biome(world_x, 0, world_seed)

        # Constants from biome properties
        SURFACE_BLOCK = biome.surface_block
        DIRT_DEPTH = biome.dirt_depth
        TREE_DENSITY = biome.tree_density
        ORE_RARITY = biome.ore_rarity
        BASE_HEIGHT = biome.base_height
        HEIGHT_VARIATION = biome.height_variation

        # Scale factors for noise
        terrain_scale_x = 0.008
        cave_scale = 0.045
        ore_scale = 0.035
        plateau_noise_scale = 0.002
        cliff_noise_scale = 0.02
        large_scale_variation_scale = 0.001
        base_offset_scale = 0.005
        hole_scale = 0.03

        # Use the new noise generators
        large_scale_variation = noise_gen_low_freq([world_x * large_scale_variation_scale]) * 60

        plateau_threshold = 0.5
        plateau_val = noise_gen_high_freq([world_x * plateau_noise_scale])
        plateau_offset = 10 if plateau_val > plateau_threshold else 0

        cliff_val = noise_gen_high_freq([world_x * cliff_noise_scale])
        cliff_offset = int((cliff_val - 0.85) * 40) if cliff_val > 0.85 else 0

        noise_val = noise_gen_med_freq([world_x * terrain_scale_x])

        base_offset = noise_gen_low_freq([world_x * base_offset_scale]) * 25

        local_surface = BASE_HEIGHT + int(base_offset) + int(HEIGHT_VARIATION * 2.5 * noise_val) + int(large_scale_variation) + plateau_offset + cliff_offset
        heightmap[x] = local_surface

    # Ajout de trous/creux de surface
    for x in range(2, config.CHUNK_SIZE-2):
        hole_noise = noise_gen_hole([(world_offset_x + x) * hole_scale])
        if hole_noise > 0.85:
            dip_depth = chunk_random.randint(1, 3)
            heightmap[x] += dip_depth
            heightmap[x-1] += chunk_random.randint(0, dip_depth // 2)
            heightmap[x+1] += chunk_random.randint(0, dip_depth // 2)

    # Apply more aggressive smoothing to the heightmap
    heightmap = gaussian_filter(heightmap, sigma=3.5).astype(int)

    # STEP 2: Fill the chunk with appropriate blocks based on its depth
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]

        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            depth = world_y - surface_height

            if depth < 0:
                chunk_array[y, x] = config.EMPTY
            elif depth == 0:
                chunk_array[y, x] = SURFACE_BLOCK
                if SURFACE_BLOCK == config.GRASS and chunk_random.random() < TREE_DENSITY:
                    if x > 1 and x < config.CHUNK_SIZE - 2:
                        if y > 0 and chunk_array[y-1, x] == config.EMPTY:
                            chunk_array[y-1, x] = config.TREE_TRUNK
                            leaf_height = chunk_random.randint(2, 4)
                            leaf_width = chunk_random.randint(1, 2)
                            for ly in range(1, leaf_height + 1):
                                for lx in range(-leaf_width, leaf_width + 1):
                                    tree_part_y = y - 1 - ly
                                    tree_part_x = x + lx
                                    if 0 <= tree_part_y < config.CHUNK_SIZE and 0 <= tree_part_x < config.CHUNK_SIZE:
                                        if chunk_array[tree_part_y, tree_part_x] == config.EMPTY:
                                            chunk_array[tree_part_y, tree_part_x] = config.LEAVES
            elif depth <= DIRT_DEPTH:
                chunk_array[y, x] = config.DIRT
            else:
                chunk_array[y, x] = config.STONE
                ore_noise_1 = noise_gen_ore_1([world_x * ore_scale, world_y * ore_scale])
                ore_noise_2 = noise_gen_ore_2([world_x * ore_scale * 1.7, world_y * ore_scale * 1.7])
                ore_noise_3 = noise_gen_ore_3([world_x * ore_scale * 0.5, world_y * ore_scale * 0.5])

                if ore_noise_1 > 0.4 and depth > 10 and chunk_random.random() < 0.1:
                    chunk_array[y, x] = config.COPPER_ORE
                elif ore_noise_2 > 0.5 and depth > 25 and chunk_random.random() < 0.08:
                    chunk_array[y, x] = config.IRON_ORE
                elif ore_noise_3 > 0.6 and depth > 50 and chunk_random.random() < 0.05:
                    chunk_array[y, x] = config.GOLD_ORE

    # --- Cave Generation ---
    cave_noise_gen = PerlinNoiseGenerator(seed=world_seed, octaves=3)
    for x in range(config.CHUNK_SIZE):
        for y in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            if world_y > heightmap[x] + config.BLOCKS[config.DIRT].get("layer_depth", 5):
                cave_val = cave_noise_gen([world_x * 0.04, world_y * 0.04])
                if cave_val > 0.3 + (chunk_random.random() * 0.1 - 0.05):
                    chunk_array[y, x] = config.EMPTY

    # Force additional cave formation near spawn in the origin chunk (0,0)
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
            if biome.name == "Plains" and chunk_random.random() < 0.08:
                for fx in range(-1, 2):
                    if 0 <= x+fx < config.CHUNK_SIZE and local_surface_y-1 >= 0:
                        chunk_array[local_surface_y-1, x+fx] = config.FLOWER
            elif biome.name == "Desert" and chunk_random.random() < 0.04:
                for fx in range(-1, 2):
                    if 0 <= x+fx < config.CHUNK_SIZE and local_surface_y-1 >= 0:
                        chunk_array[local_surface_y-1, x+fx] = config.CACTUS
            elif biome.name == "Snow" and chunk_random.random() < 0.08:
                chunk_array[local_surface_y, x] = config.SNOW_LAYER

    # STEP 5: Generate water pools
    water_placed = False
    for x in range(config.CHUNK_SIZE):
        surface_height = heightmap[x]
        local_surface_y = surface_height - world_offset_y

        if 0 <= local_surface_y < config.CHUNK_SIZE:
            if x > 1 and x < config.CHUNK_SIZE - 2:
                left_height = heightmap[x-1]
                right_height = heightmap[x+1]
                is_depression = (left_height > surface_height or right_height > surface_height)
                is_flat = (abs(left_height - surface_height) <= 1 and abs(right_height - surface_height) <= 1)
                random_pool = chunk_random.random() < 0.1 and is_flat

                if is_depression or random_pool:
                    water_depth = chunk_random.randint(2, 5)
                    for wy in range(1, water_depth + 1):
                        water_y = local_surface_y + wy
                        if 0 <= water_y < config.CHUNK_SIZE and chunk_array[water_y, x] == config.EMPTY:
                            chunk_array[water_y, x] = config.WATER
                            water_placed = True
                            for dx in [-1, 1]:
                                if 0 <= x + dx < config.CHUNK_SIZE:
                                    if chunk_array[water_y, x + dx] == config.EMPTY:
                                        if water_y + 1 >= config.CHUNK_SIZE or chunk_array[water_y+1, x+dx] != config.EMPTY:
                                            chunk_array[water_y, x + dx] = config.WATER

    # STEP 6: Add bedrock at the very bottom of the world
    if world_offset_y + config.CHUNK_SIZE > 200:
        for x in range(config.CHUNK_SIZE):
            for y in range(config.CHUNK_SIZE):
                if world_offset_y + y > 200:
                    chunk_array[y, x] = config.BEDROCK

    return chunk_array