import pygame
import numpy as np
import random
import core.config as config
from scipy.ndimage import gaussian_filter
import math

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

def generate_chunk(chunk_array, chunk_x, chunk_y, seed):
    """Generates terrain for a chunk in Terraria style with consistent layering."""
    # Use a fixed seed for the entire world
    world_seed = seed
    perlin = PerlinNoise(seed=world_seed)
    
    # Global world coordinates
    world_offset_x = chunk_x * config.CHUNK_SIZE
    world_offset_y = chunk_y * config.CHUNK_SIZE
    
    # Constants for world generation
    SURFACE_LEVEL = 30  # Global surface level (constant across all chunks)
    SURFACE_VARIATION = 10  # Maximum height variation of surface
    DIRT_DEPTH = 5  # Depth of dirt layer below surface
    
    # Scale factors for noise
    terrain_scale_x = 0.02  # Large number = more frequent hills
    terrain_scale_y = 0.01  # Variation of chunks vertically
    cave_scale = 0.07  # Scale for cave system (bigger = smaller caves)
    ore_scale = 0.04  # Scale for ore distribution
    
    # Calculate absolute vertical position of this chunk in the world
    absolute_y = chunk_y * config.CHUNK_SIZE
    
    # STEP 1: Generate the basic terrain heightmap
    # For chunks below the surface, we still calculate the surface height
    # but use it just for reference
    heightmap = np.zeros(config.CHUNK_SIZE, dtype=int)
    
    # Generate coherent heightmap across chunks
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        
        # Calculate surface height using 1D noise for the x-coordinate
        # This ensures consistent terrain across the x-axis
        noise_val = octave_noise(perlin, world_x * terrain_scale_x, 0, octaves=4)
        
        # Map noise to surface height
        local_surface = SURFACE_LEVEL + int(SURFACE_VARIATION * (noise_val * 2 - 1))
        heightmap[x] = local_surface
    
    # Apply slight smoothing to the heightmap
    heightmap = gaussian_filter(heightmap, sigma=1.5).astype(int)
    
    # STEP 2: Fill the chunk with appropriate blocks based on its depth
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]
        
        # Use 2D Perlin noise for each (x,y) position
        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            absolute_world_y = world_y
            
            # Position relative to surface (negative = above surface, positive = below)
            depth = absolute_world_y - surface_height
            
            # TERRAIN LAYERS
            if depth < 0:
                # Above surface = air
                chunk_array[y, x] = config.EMPTY
            elif depth == 0:
                # Surface block (dirt/grass)
                chunk_array[y, x] = config.DIRT
            elif depth <= DIRT_DEPTH:
                # Dirt layer
                chunk_array[y, x] = config.DIRT
            else:
                # Stone layer by default
                chunk_array[y, x] = config.STONE
                
                # Add ores based on depth and noise
                ore_noise = octave_noise(perlin,
                                     world_x * ore_scale,
                                     world_y * ore_scale,
                                     octaves=3)
                
                if depth > 40 and ore_noise > 0.8:  # Deep ores (diamond)
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif depth > 20 and ore_noise > 0.75:  # Medium depth ores (iron)
                    chunk_array[y, x] = config.IRON_ORE
                elif depth > 10 and ore_noise > 0.7:  # Shallow ores (gravel)
                    chunk_array[y, x] = config.GRAVEL
    
    # STEP 3: Generate caves
    for x in range(config.CHUNK_SIZE):
        world_x = world_offset_x + x
        surface_height = heightmap[x]
        
        for y in range(config.CHUNK_SIZE):
            world_y = world_offset_y + y
            absolute_world_y = world_y
            depth = absolute_world_y - surface_height
            
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
                cave_threshold = min(0.6, 0.45 + depth * 0.001)
                
                if combined_cave > cave_threshold:
                    chunk_array[y, x] = config.EMPTY
    
    # STEP 4: Generate trees (only on surface chunks)
    if absolute_y <= SURFACE_LEVEL + SURFACE_VARIATION:
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            surface_height = heightmap[x]
            
            # Check if this x-coordinate is within the chunk's y-range
            if SURFACE_LEVEL <= surface_height < SURFACE_LEVEL + config.CHUNK_SIZE:
                # Local y-coordinate of the surface in this chunk
                local_surface_y = surface_height - absolute_y
                
                # Trees only spawn on flat or nearly flat areas
                if local_surface_y >= 0 and local_surface_y < config.CHUNK_SIZE - 5:
                    # Tree distribution is based on world x-coordinate
                    tree_chance = octave_noise(perlin, world_x * 0.02, seed * 0.1, octaves=1)
                    
                    # About 15% chance for a tree if spacing is right
                    if tree_chance > 0.85 and world_x % 7 == 0:  # Simple spacing formula
                        tree_height = 4 + int(tree_chance * 3)  # 4-6 blocks tall
                        
                        # Ensure the tree fits in the chunk
                        for ty in range(tree_height):
                            tree_y = local_surface_y - ty - 1  # -1 to start above ground
                            if 0 <= tree_y < config.CHUNK_SIZE:
                                chunk_array[tree_y, x] = config.WOOD
    
    return chunk_array