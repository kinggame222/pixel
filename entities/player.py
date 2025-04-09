import pygame
from core import config
from world.chunks import get_chunk_coords

class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = config.PLAYER_WIDTH
        self.height = config.PLAYER_HEIGHT
        self.velocity_x = 0
        self.velocity_y = 0
        self.speed = config.PLAYER_SPEED
        self.jetpack_speed = 200
        self.color = (255, 255, 255)  # White player
        
        # Collision settings
        self.collision_enabled = True
    
    def update(self, dt, keys, check_collision_func):
        """Update player position based on input and collisions."""
        move_x = 0
        move_y = 0
        
        # Handle horizontal movement
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: move_x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move_x += self.speed
        
        # Handle vertical movement (jetpack)
        if keys[pygame.K_UP] or keys[pygame.K_w]: move_y -= self.jetpack_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: move_y += self.jetpack_speed
        
        # Apply movement with collision detection
        if self.collision_enabled:
            # Check horizontal collision
            if not check_collision_func(self.x, self.y, move_x * dt, 0):
                self.x += move_x * dt  # Horizontal movement
            
            # Check vertical collision
            if not check_collision_func(self.x, self.y, 0, move_y * dt):
                self.y += move_y * dt  # Vertical movement
        else:
            # No collision check
            self.x += move_x * dt
            self.y += move_y * dt
    
    def draw(self, screen, camera_x, camera_y):
        """Draw the player on the screen."""
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y
        pygame.draw.rect(screen, self.color, (screen_x, screen_y, self.width, self.height))
    
    def get_chunk_position(self):
        """Get the chunk coordinates of the player's position."""
        return get_chunk_coords(int(self.x // config.PIXEL_SIZE), int(self.y // config.PIXEL_SIZE))
    
    def toggle_collision(self):
        """Toggle player collision detection."""
        self.collision_enabled = not self.collision_enabled
        return self.collision_enabled
