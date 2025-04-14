import pygame
import random
from core import config
from world.chunks import get_block_at # Import to check for collisions

PARTICLE_GRAVITY = 9.81 * config.PIXEL_SIZE * 2 # Gravity effect, adjust multiplier as needed
PARTICLE_LIFETIME = 1.5 # Seconds
PARTICLE_FRICTION = 0.95 # Slow down horizontal movement on ground
MAX_PARTICLES = 1000 # Limit total particles for performance

class Particle:
    def __init__(self, x, y, vx, vy, color, lifetime=PARTICLE_LIFETIME):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.lifetime = lifetime
        self.on_ground = False

    def update(self, dt):
        self.lifetime -= dt
        if self.lifetime <= 0:
            return False # Indicate particle should be removed

        # Apply gravity if not on ground
        if not self.on_ground:
            self.vy += PARTICLE_GRAVITY * dt

        # Basic collision detection (check block below)
        next_y = self.y + self.vy * dt
        block_x = int(self.x // config.PIXEL_SIZE)
        block_y_below = int((next_y + config.PIXEL_SIZE // 2) // config.PIXEL_SIZE) # Check slightly below center

        block_below_type = get_block_at(block_x, block_y_below)
        is_solid_below = block_below_type in config.BLOCKS and config.BLOCKS[block_below_type]["solid"]

        if is_solid_below and self.vy > 0:
             # Landed on ground
             self.y = block_y_below * config.PIXEL_SIZE - config.PIXEL_SIZE / 2 # Adjust to sit on top
             self.vy = 0
             self.vx *= PARTICLE_FRICTION # Apply friction
             self.on_ground = True
        else:
             self.on_ground = False
             self.y = next_y # Update vertical position

        # Update horizontal position (simple, no side collision for now)
        self.x += self.vx * dt

        return True # Indicate particle is still active

    def draw(self, screen, camera_x, camera_y):
        # Draw particle as a small rectangle
        screen_x = int(self.x - camera_x)
        screen_y = int(self.y - camera_y)
        size = max(1, int(config.PIXEL_SIZE / 8)) # Particle size relative to block size
        # Fade out effect (optional)
        alpha = max(0, min(255, int(255 * (self.lifetime / PARTICLE_LIFETIME))))
        color_with_alpha = (*self.color, alpha)

        try:
            # Use a surface with alpha for proper blending
            particle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
            particle_surf.fill(color_with_alpha)
            screen.blit(particle_surf, (screen_x - size // 2, screen_y - size // 2))
        except ValueError: # Handle potential invalid color format if alpha fails
             pygame.draw.rect(screen, self.color, (screen_x - size // 2, screen_y - size // 2, size, size))


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def add_particle(self, x, y, color):
        if len(self.particles) >= MAX_PARTICLES:
            return # Don't add more if limit is reached

        # Add some randomness to initial velocity
        angle = random.uniform(0, math.pi * 2) # Spread in all directions initially
        speed = random.uniform(config.PIXEL_SIZE * 1, config.PIXEL_SIZE * 4) # Initial speed
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed - config.PIXEL_SIZE * 2 # Slight initial upward boost

        self.particles.append(Particle(x, y, vx, vy, color))

    def update(self, dt):
        # Update particles and remove dead ones
        self.particles = [p for p in self.particles if p.update(dt)]

    def draw(self, screen, camera_x, camera_y):
        for particle in self.particles:
            particle.draw(screen, camera_x, camera_y)

# Need math for angle calculations in add_particle
import math
