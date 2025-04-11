import core.config as config
import random

class Biome:
    def __init__(self, name, surface_block, dirt_depth, tree_density, ore_rarity, base_height, height_variation, temperature, humidity):
        self.name = name
        self.surface_block = surface_block
        self.dirt_depth = dirt_depth
        self.tree_density = tree_density
        self.ore_rarity = ore_rarity
        self.base_height = base_height
        self.height_variation = height_variation
        self.temperature = temperature
        self.humidity = humidity

# Define different biomes
PLAINS = Biome(
    name="Plains",
    surface_block=config.GRASS,
    dirt_depth=20,
    tree_density=0.2,
    ore_rarity=1.0,
    base_height=20,
    height_variation=5,
    temperature=0.7,
    humidity=0.5
)

FOREST = Biome(
    name="Forest",
    surface_block=config.GRASS,
    dirt_depth=5,
    tree_density=0.7,
    ore_rarity=0.9,
    base_height=22,
    height_variation=7,
    temperature=0.6,
    humidity=0.6
)

DESERT = Biome(
    name="Desert",
    surface_block=config.SAND,
    dirt_depth=8,
    tree_density=0.05,
    ore_rarity=1.2,
    base_height=25,
    height_variation=10,
    temperature=0.9,
    humidity=0.1
)

SNOW = Biome(
    name="Snow",
    surface_block=config.SNOW_BLOCK,
    dirt_depth=4,
    tree_density=0.1,
    ore_rarity=0.8,
    base_height=18,
    height_variation=4,
    temperature=0.1,
    humidity=0.8
)

MOUNTAIN = Biome(
    name="Mountain",
    surface_block=config.STONE,
    dirt_depth=2,
    tree_density=0.01,
    ore_rarity=1.5,
    base_height=60,  # Increased base height
    height_variation=30,  # Increased height variation
    temperature=0.3,
    humidity=0.2
)

def get_biome(x, y, seed):
    """Simple biome selection based on coordinates."""
    random.seed(x * 1000 + y + seed)
    
    # Very basic biome selection logic
    if y > 50:  # Adjusted mountain threshold
        return MOUNTAIN
    elif x % 100 > 70:
        return DESERT
    elif x % 50 < 10:
        return SNOW
    else:
        return PLAINS if random.random() < 0.5 else FOREST
