"""Module pour la génération de terrain accélérée par GPU."""
import numpy as np
import random
import time
import logging
from core import config
from scipy.ndimage import gaussian_filter

# Import conditionnel des bibliothèques GPU
try:
    import numba
    from numba import cuda, float32, int32, boolean  # type: ignore
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

try:
    import pyopencl as cl  # type: ignore
    import pyopencl.array
    PYOPENCL_AVAILABLE = True
except ImportError:
    PYOPENCL_AVAILABLE = False

# Importer notre détecteur de GPU
from utils.gpu_detection import GPU_AVAILABLE, NUMBA_AVAILABLE, PYOPENCL_AVAILABLE
from world.biomes import get_biome

logger = logging.getLogger(__name__)
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

# Version Numba-accélérée du bruit de Perlin
if NUMBA_AVAILABLE:
    @cuda.jit(device=True)
    def fade_device(t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    @cuda.jit(device=True)
    def lerp_device(t, a, b):
        return a + t * (b - a)

    @cuda.jit(device=True)
    def grad_device(hash, x, y, z):
        h = hash & 15
        u = x if h < 8 else y
        v = y if h < 4 else (x if h == 12 or h == 14 else z)
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    @cuda.jit
    def generate_noise_kernel(noise_array, p_array, x_offset, y_offset, scale_x, scale_y, chunk_size, octaves):
        """Kernel CUDA pour générer du bruit de Perlin."""
        x, y = cuda.grid(2)
        
        if x < chunk_size and y < chunk_size:
            # Coordonnées mondiales
            world_x = x_offset + x
            world_y = y_offset + y
            
            # Coordonnées mise à l'échelle pour le bruit
            nx = world_x * scale_x
            ny = world_y * scale_y
            
            # Implémentation standard du bruit de Perlin
            value = 0.0
            frequency = 1.0
            amplitude = 1.0
            max_amplitude = 0.0
            
            for i in range(octaves):
                X = int(nx * frequency) & 255
                Y = int(ny * frequency) & 255
                
                fx = (nx * frequency) - int(nx * frequency)
                fy = (ny * frequency) - int(ny * frequency)
                
                u = fade_device(fx)
                v = fade_device(fy)
                
                A = p_array[X] + Y
                AA = p_array[A]
                AB = p_array[A + 1]
                B = p_array[X + 1] + Y
                BA = p_array[B]
                BB = p_array[B + 1]
                
                # Calculer la valeur de bruit
                value += lerp_device(v,
                                   lerp_device(u, grad_device(p_array[AA], fx, fy, 0),
                                                 grad_device(p_array[BA], fx-1, fy, 0)),
                                   lerp_device(u, grad_device(p_array[AB], fx, fy-1, 0),
                                                 grad_device(p_array[BB], fx-1, fy-1, 0))) * amplitude
                max_amplitude += amplitude
                amplitude *= 0.5  # Persistence
                frequency *= 2.0  # Lacunarity
            
            # Normaliser
            noise_array[y, x] = (value / max_amplitude + 1) / 2

    @cuda.jit
    def generate_terrain_kernel(chunk_array, heightmap, world_offset_x, world_offset_y, perlin_array, 
                              chunk_size, surface_block, dirt_depth, ore_rarity, large_scale_noise):
        """Kernel CUDA pour générer le terrain basé sur une heightmap."""
        x, y = cuda.grid(2)
        
        if x < chunk_size and y < chunk_size:
            # Position mondiale
            world_x = world_offset_x + x
            world_y = world_offset_y + y
            
            # Hauteur de surface pour cette colonne x
            surface_height = heightmap[x] + int(large_scale_noise[x])  # Add large-scale variation
            
            # Profondeur relative à la surface
            depth = world_y - surface_height
            
            # COUCHES DE TERRAIN
            if depth < 0:
                # Au-dessus de la surface = air
                chunk_array[y, x] = config.EMPTY
            elif depth == 0:
                # Bloc de surface (déterminé par le biome)
                chunk_array[y, x] = surface_block
            elif depth <= dirt_depth:
                # Couche de terre
                chunk_array[y, x] = config.DIRT
            else:
                # Stone layer par défaut
                chunk_array[y, x] = config.STONE
                
                # Utiliser des valeurs de bruit précalculées pour la distribution de minerai
                noise_val = perlin_array[y % chunk_size, x % chunk_size]
                
                # Distribution de minerai basée sur la profondeur
                if depth > 30 and noise_val > 0.75 * ore_rarity:
                    chunk_array[y, x] = config.DIAMOND_ORE
                elif depth > 20 and noise_val > 0.70 * ore_rarity:
                    chunk_array[y, x] = config.IRON_ORE
                elif depth > 5 and noise_val > 0.68 * ore_rarity:
                    chunk_array[y, x] = config.GRAVEL
                elif 3 < depth < 20 and noise_val > 0.80:
                    chunk_array[y, x] = config.SAND

                # Génération des grottes
                cave_noise = perlin_array[y % chunk_size, x % chunk_size]
                if depth > 3 and cave_noise > 0.6:
                    chunk_array[y, x] = config.EMPTY

            # Génération des bassins d'eau
            if depth > 0 and depth < 5 and perlin_array[y % chunk_size, x % chunk_size] > 0.8:
                chunk_array[y, x] = config.WATER

def generate_chunk_gpu(chunk_x, chunk_y, seed):
    """Génère un chunk de terrain avec accélération GPU."""
    logger.debug(f"GPU generation started for chunk ({chunk_x}, {chunk_y}) with seed {seed}")
    start_time = time.time()
    
    # Initialiser le générateur aléatoire avec la seed
    # Ensure seed is within the valid range for random.seed
    seed = config.SEED
    random.seed(seed + chunk_x * 1000 + chunk_y)
    np.random.seed(seed + chunk_x * 1000 + chunk_y)
    
    chunk_array = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.int32)
    
    if not GPU_AVAILABLE or not NUMBA_AVAILABLE:
        # Fallback au CPU si GPU n'est pas disponible
        logger.warning("GPU non disponible pour la génération, fallback au CPU")
        from world.map_generation import generate_chunk
        return generate_chunk(chunk_array, chunk_x, chunk_y, seed)
    
    try:
        # Select biome based on world position
        world_offset_x = chunk_x * config.CHUNK_SIZE
        world_offset_y = chunk_y * config.CHUNK_SIZE
        biome = get_biome(world_offset_x, world_offset_y, seed)
        
        # Get biome properties
        surface_block = biome.surface_block
        dirt_depth = biome.dirt_depth
        base_height = biome.base_height
        height_variation = biome.height_variation
        ore_rarity = biome.ore_rarity
        
        # Créer la table de permutation pour le bruit de Perlin
        p = list(range(256))
        random.shuffle(p)
        p = np.array(p + p, dtype=np.int32)
        
        # Préparer les paramètres de terrain
        
        terrain_scale_x = 0.015
        terrain_scale_y = 0.01
        
        # Transférer la table de permutation au GPU
        d_p = cuda.to_device(p)
        
        # Préparer un tableau pour stocker le bruit de Perlin
        perlin_array = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.float32)
        d_perlin_array = cuda.to_device(perlin_array)
        
        # Définir les dimensions de la grille et des blocs pour CUDA
        threadsperblock = (16, 16)
        blockspergrid_x = (config.CHUNK_SIZE + threadsperblock[0] - 1) // threadsperblock[0]
        blockspergrid_y = (config.CHUNK_SIZE + threadsperblock[1] - 1) // threadsperblock[1]
        blockspergrid = (blockspergrid_x, blockspergrid_y)
        
        # Générer du bruit pour les valeurs d'octaves multiples sur GPU
        octaves = 6
        generate_noise_kernel[blockspergrid, threadsperblock](
            d_perlin_array, d_p, world_offset_x, world_offset_y, 
            terrain_scale_x, terrain_scale_y, config.CHUNK_SIZE, octaves
        )
        
        # Synchroniser pour s'assurer que le calcul est terminé
        cuda.synchronize()
        
        # Récupérer le bruit de Perlin du GPU
        perlin_array = d_perlin_array.copy_to_host()
        
        # Générer la heightmap (toujours sur CPU pour plus de simplicité)
        heightmap = np.zeros(config.CHUNK_SIZE, dtype=np.int32)
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            # Variable base height using noise
            base_offset = octave_noise(PerlinNoise(seed), world_x * 0.005, 0, octaves=2) * 10  # Smaller scale for base variation
            noise_val = perlin_array[x, 0]  # Using pre-calculated noise
            local_surface = base_height + int(base_offset) + int(height_variation * (noise_val * 2 - 1))
            heightmap[x] = local_surface
        
        # Apply smoothing to the heightmap
        heightmap = gaussian_filter(heightmap, sigma=3.0).astype(int)
        d_heightmap = cuda.to_device(heightmap)
        
        # Generate large-scale noise for terrain variation
        large_scale_noise = np.zeros(config.CHUNK_SIZE, dtype=np.float32)
        for x in range(config.CHUNK_SIZE):
            world_x = world_offset_x + x
            large_scale_noise[x] = octave_noise(PerlinNoise(seed), world_x * 0.001, 0, octaves=2) * 15
        d_large_scale_noise = cuda.to_device(large_scale_noise)
        
        # Transférer la heightmap et le tableau de chunk au GPU
        d_chunk_array = cuda.to_device(chunk_array)
        
        # Exécuter le kernel de génération de terrain
        generate_terrain_kernel[blockspergrid, threadsperblock](
            d_chunk_array, d_heightmap, world_offset_x, world_offset_y, d_perlin_array,
            config.CHUNK_SIZE, surface_block, dirt_depth, float(ore_rarity), d_large_scale_noise
        )
        
        # Synchroniser pour s'assurer que le calcul est terminé
        cuda.synchronize()
        
        # Récupérer le chunk du GPU
        chunk_array = d_chunk_array.copy_to_host()
        
        # Ajouter d'autres fonctionnalités (grottes, arbres, eau) sur CPU
        # Ces éléments sont plus complexes et séquentiels, donc restent sur CPU
        from world.map_generation import generate_chunk
        chunk_array = generate_chunk(chunk_array, chunk_x, chunk_y, seed)
        
        logger.info(f"Génération GPU du chunk ({chunk_x}, {chunk_y}) terminée en {time.time() - start_time:.3f}s")
        logger.debug(f"GPU generation finished for chunk ({chunk_x}, {chunk_y})")
        
        return chunk_array
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération GPU: {e}")
        # Fallback au CPU en cas d'erreur
        from world.map_generation import generate_chunk
        return generate_chunk(chunk_array, chunk_x, chunk_y, seed)
