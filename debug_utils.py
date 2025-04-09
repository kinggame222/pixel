import pygame
import config

def draw_chunk_grid(screen, camera_x, camera_y, chunk_size):
    """Draw a grid showing chunk boundaries for debugging."""
    # Calculate visible area
    min_x = int(camera_x // (chunk_size * config.PIXEL_SIZE))
    min_y = int(camera_y // (chunk_size * config.PIXEL_SIZE))
    max_x = int((camera_x + screen.get_width()) // (chunk_size * config.PIXEL_SIZE) + 1)
    max_y = int((camera_y + screen.get_height()) // (chunk_size * config.PIXEL_SIZE) + 1)
    
    # Draw grid
    for x in range(min_x, max_x + 1):
        screen_x = x * chunk_size * config.PIXEL_SIZE - camera_x
        pygame.draw.line(screen, (80, 80, 80), (screen_x, 0), 
                         (screen_x, screen.get_height()))
                         
    for y in range(min_y, max_y + 1):
        screen_y = y * chunk_size * config.PIXEL_SIZE - camera_y
        pygame.draw.line(screen, (80, 80, 80), (0, screen_y), 
                         (screen.get_width(), screen_y))
    
    # Draw coordinate text for each chunk
    font = pygame.font.SysFont("Arial", 12)
    for x in range(min_x, max_x):
        for y in range(min_y, max_y):
            text = f"({x}, {y})"
            text_surface = font.render(text, True, (255, 255, 255))
            screen_x = x * chunk_size * config.PIXEL_SIZE - camera_x + 5
            screen_y = y * chunk_size * config.PIXEL_SIZE - camera_y + 5
            screen.blit(text_surface, (screen_x, screen_y))
