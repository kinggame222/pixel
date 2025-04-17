import random
import numpy as np
from core import config

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
    # Use custom Perlin noise to smoothly select a biome
    scale = 0.001  # adjust noise frequency
    perlin = PerlinNoise(seed=seed)
    noise_value = (perlin.noise(world_x * scale, world_y * scale) + 1) / 2  # normalize to 0-1
    index = int(noise_value * len(biome_list))
    if index >= len(biome_list):
        index = len(biome_list) - 1
    return biome_list[index]
