import math
import random

class PerlinNoise:
    def __init__(self, seed=None):
        # Initialize the permutation array
        if seed is not None:
            random.seed(seed)
        
        # Create a permutation list with values 0...255
        self.permutation = list(range(256))
        random.shuffle(self.permutation)
        # Double it to avoid buffer overflow when computing indices
        self.permutation = self.permutation * 2

    def fade(self, t):
        """Fade function as defined by Ken Perlin"""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, a, b, x):
        """Linear interpolation function"""
        return a + x * (b - a)

    def grad(self, hash_value, x, y):
        """Gradient function"""
        h = hash_value & 15
        grad_x = 1 + (h & 7) if (h & 8) == 0 else -1 - (h & 7)
        grad_y = grad_x if (h & 1) == 0 else -grad_x
        return grad_x * x + grad_y * y

    def noise(self, x, y):
        """Generate 2D Perlin noise"""
        # Find unit grid cell containing point
        X = int(math.floor(x)) & 255
        Y = int(math.floor(y)) & 255
        
        # Get relative coordinates within grid cell
        x -= math.floor(x)
        y -= math.floor(y)
        
        # Compute fade curves
        u = self.fade(x)
        v = self.fade(y)
        
        # Hash coordinates of the 4 corners
        A = self.permutation[X] + Y
        B = self.permutation[X + 1] + Y
        
        # And add blended results from the corners
        return self.lerp(
            self.lerp(self.grad(self.permutation[A], x, y),
                      self.grad(self.permutation[B], x - 1, y),
                      u),
            self.lerp(self.grad(self.permutation[A + 1], x, y - 1),
                      self.grad(self.permutation[B + 1], x - 1, y - 1),
                      u),
            v
        ) * 0.5 + 0.5  # Transform from -1..1 to 0..1

def octave_noise(perlin, x, y, octaves=1, persistence=0.5, lacunarity=2.0):
    """Generate fractal noise with multiple octaves"""
    total = 0
    frequency = 1
    amplitude = 1
    max_value = 0  # Used for normalizing result to 0.0 - 1.0
    
    for i in range(octaves):
        total += perlin.noise(x * frequency, y * frequency) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= lacunarity
        
    return total / max_value
