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
        self.on_ground = False
        self.collision_enabled = True

    def update(self, dt, keys, check_collision_func):
        move_x = 0
        move_y = 0

        # Déplacement horizontal
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x += self.speed

        # Saut (Terraria style)
        if keys[pygame.K_SPACE] and self.on_ground:
            self.velocity_y = config.JUMP_SPEED
            self.on_ground = False

        # Gravité (Terraria style)
        if not self.on_ground:
            self.velocity_y += config.GRAVITY * dt

        # Appliquer la vitesse verticale
        move_y += self.velocity_y

        if self.collision_enabled:
            # Mouvement vertical d'abord, pour mettre à jour on_ground correctement
            if not check_collision_func(self.x, self.y, 0, move_y * dt):
                self.y += move_y * dt
                self.on_ground = False
            else:
                if move_y > 0:  # Tombe sur le sol
                    self.on_ground = True
                    self.velocity_y = 0
                elif move_y < 0:  # Frappe le plafond
                    self.velocity_y = 0
            # Mouvement horizontal séparé, toujours autorisé si pas de collision
            if not check_collision_func(self.x, self.y, move_x * dt, 0):
                self.x += move_x * dt
        else:
            self.x += move_x * dt
            self.y += move_y * dt

    def draw(self, screen, camera_x, camera_y):
        screen_x = self.x - camera_x
        screen_y = self.y - camera_y
        pygame.draw.rect(screen, self.color, (screen_x, screen_y, self.width, self.height))

    def get_chunk_position(self):
        return get_chunk_coords(int(self.x // config.PIXEL_SIZE), int(self.y // config.PIXEL_SIZE))

    def toggle_collision(self):
        self.collision_enabled = not self.collision_enabled
        return self.collision_enabled
