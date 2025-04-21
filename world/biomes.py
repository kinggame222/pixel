import random
import numpy as np
from core import config
try:
    # Import the new library
    from perlin_noise import PerlinNoise as PerlinNoiseGenerator
except ImportError:
    print("ERREUR: Le module 'perlin-noise' n'est pas installé. Installez-le avec 'pip install perlin-noise'")
    raise

class Biome:
    def __init__(self, name, surface_block, base_height, height_variation, dirt_depth, tree_density, ore_rarity):
        self.name = name
        self.surface_block = surface_block
        self.base_height = base_height
        self.height_variation = height_variation
        self.dirt_depth = dirt_depth
        self.tree_density = tree_density
        self.ore_rarity = ore_rarity

# Define several varied biomes
biome_list = [
    Biome("Plains", config.GRASS, 10, 3, 5, 0.2, 0.1),
    Biome("Swamp", getattr(config, "SLIME", config.GRASS), 8, 2, 7, 0.1, 0.05),
    Biome("Jungle", getattr(config, "LEAVES", config.GRASS), 12, 5, 4, 0.8, 0.2),
    Biome("Savanna", config.SAND, 9, 2, 3, 0.05, 0.15),
    Biome("Volcano", getattr(config, "LAVA", config.STONE), 15, 7, 8, 0.0, 0.25),
    Biome("Ocean", config.WATER, 6, 1, 10, 0.0, 0.05),
]
  
def get_biome(world_x, world_y, seed):
    try:
        # Create a noise generator instance for biomes
        biome_noise_generator = PerlinNoiseGenerator(seed=seed, octaves=2) # Example octaves

        # Use the noise library to smoothly select a biome
        scale = 0.001  # adjust noise frequency

        noise_value = 0.5 # Default value in case noise fails
        try:
            # Use the new library's noise function
            raw_noise = biome_noise_generator([world_x * scale, world_y * scale])
            noise_value = (raw_noise + 0.707) / 1.414 # Normalize approx range to [0, 1]
            noise_value = max(0.0, min(1.0, noise_value)) # Clamp to [0, 1] just in case
        except Exception as noise_error:
            print(f"[ERROR] perlin_noise failed: {noise_error}")
            import traceback
            traceback.print_exc()
            # Continue with default noise_value to see if the rest works

        index = int(noise_value * len(biome_list))

        if index >= len(biome_list):
            index = len(biome_list) - 1
        elif index < 0:
             index = 0

        biome = biome_list[index]
        return biome

    except Exception as e:
        print(f"[ERROR] get_biome failed unexpectedly for world_x={world_x}, world_y={world_y}, seed={seed}: {e}")
        import traceback
        traceback.print_exc()
        # Fallback: return Plains biome
        return biome_list[0]
