import pygame

def apply_shadow(surface, intensity=100):
    """Apply a shadow effect to a surface."""
    shadow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, intensity))  # Semi-transparent black
    surface.blit(shadow, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return surface

def apply_gradient(surface, color=(255, 255, 255), direction="vertical"):
    """Apply a gradient effect to a surface."""
    gradient = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    width, height = surface.get_size()
    for y in range(height):
        alpha = int((y / height) * 255) if direction == "vertical" else int((y / width) * 255)
        pygame.draw.line(gradient, (*color, alpha), (0, y), (width, y))
    surface.blit(gradient, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return surface
