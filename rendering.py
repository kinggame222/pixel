import pygame
import config # Importe les constantes

# Create a dictionary to cache block colors
BLOCK_COLORS = {block_id: config.BLOCKS[block_id]["color"] for block_id in config.BLOCKS}

def draw_grid(screen, grid, camera_x, camera_y):
    """Dessine la grille visible (Pierre et Gravier)."""
    # Calcule la plage visible de la grille
    start_col = max(0, int(camera_x // config.PIXEL_SIZE))
    start_row = max(0, int(camera_y // config.PIXEL_SIZE))
    end_col = min(config.GRID_WIDTH, int((camera_x + screen.get_width()) // config.PIXEL_SIZE) + 1)
    end_row = min(config.GRID_HEIGHT, int((camera_y + screen.get_height()) // config.PIXEL_SIZE) + 1)

    # Lock the surface for direct pixel access
    screen.lock()

    # Dessine les blocs statiques dans la grille
    for r in range(start_row, end_row):
        for c in range(start_col, end_col):
            block_id = grid[r, c]
            # Dessine seulement les blocs non vides
            if block_id != config.EMPTY:
                color = BLOCK_COLORS[block_id] # Get color from cache
                # Calcule les coordonnées à l'écran
                screen_x = c * config.PIXEL_SIZE - camera_x
                screen_y = r * config.PIXEL_SIZE - camera_y
                pygame.draw.rect(screen, color, (screen_x, screen_y, config.PIXEL_SIZE, config.PIXEL_SIZE))

    # Unlock the surface
    screen.unlock()

def draw_animations(screen, falling_animations, camera_x, camera_y, current_time_ms):
    """Dessine les blocs de gravier en cours d'animation."""
    for anim in falling_animations:
        progress = min(1.0, max(0.0, (current_time_ms - anim["start_time"]) / anim["duration"]))
        src_row, src_col = anim["src"]; dst_row, dst_col = anim["dest"]
        # Interpole la position pour une animation fluide
        current_row = src_row + (dst_row - src_row) * progress
        current_col = src_col + (dst_col - src_col) * progress
        # Calcule les coordonnées à l'écran
        screen_x = current_col * config.PIXEL_SIZE - camera_x
        screen_y = current_row * config.PIXEL_SIZE - camera_y
        # Les blocs qui tombent sont toujours du Gravier
        gravel_color = config.BLOCKS[config.GRAVEL]["color"]
        pygame.draw.rect(screen, gravel_color, (screen_x, screen_y, config.PIXEL_SIZE, config.PIXEL_SIZE))

def draw_player(screen, player_x, player_y, camera_x, camera_y):
    """Dessine le joueur."""
    player_screen_x = player_x - camera_x
    player_screen_y = player_y - camera_y
    player_rect_screen = pygame.Rect(player_screen_x, player_screen_y, config.PLAYER_WIDTH, config.PLAYER_HEIGHT) # Utilise les nouvelles dimensions
    pygame.draw.rect(screen, config.COLOR_PLAYER, player_rect_screen)

def draw_fps(screen, fps_font, clock):
    """Affiche le compteur FPS."""
    fps = clock.get_fps()
    fps_text = fps_font.render(f"FPS: {int(fps)}", True, config.COLOR_FPS)
    screen.blit(fps_text, (10, 10))

def draw_game(screen, grid, falling_animations, player_x, player_y, camera_x, camera_y, fps_font, clock, current_time_ms):
    """Fonction principale de rendu qui appelle toutes les autres fonctions de dessin."""
    screen.fill(config.BLOCKS[config.EMPTY]["color"]) # Efface l'écran
    draw_grid(screen, grid, camera_x, camera_y)
    draw_animations(screen, falling_animations, camera_x, camera_y, current_time_ms)
    draw_player(screen, player_x, player_y, camera_x, camera_y)
    draw_fps(screen, fps_font, clock)
    pygame.display.flip() # Met à jour l'affichage complet
