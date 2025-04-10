import pygame
import math
import numpy as np
from core import config

# Constants for background rendering
SKY_COLOR_DAY = (135, 206, 235)    # Light blue for day
SKY_COLOR_NIGHT = (25, 25, 50)     # Dark blue for night
CLOUD_COLOR = (255, 255, 255)      # White clouds
CLOUD_SHADOW = (200, 200, 220)     # Slightly darker for cloud shadows
HILL_COLORS = [
    (70, 125, 70),    # Far hills (darker)
    (100, 155, 100)   # Near hills (lighter)
]
STAR_COLORS = [(255, 255, 220), (220, 220, 255), (255, 220, 220)]  # Star variations

def generate_clouds(width, height, seed):
    """Generate a cloud layer image for parallax scrolling."""
    pygame.init()  # Ensure pygame is initialized
    
    # Create a surface for clouds
    cloud_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    random_gen = np.random.RandomState(seed)
    
    # Generate several cloud formations
    for _ in range(width // 300):
        cloud_x = random_gen.randint(0, width)
        cloud_y = random_gen.randint(20, height // 3)
        cloud_width = random_gen.randint(100, 300)
        cloud_height = random_gen.randint(40, 80)
        
        # Generate a cloud cluster (made of circles)
        for i in range(cloud_width // 20):
            circle_x = cloud_x + random_gen.randint(-cloud_width//2, cloud_width//2)
            circle_y = cloud_y + random_gen.randint(-cloud_height//4, cloud_height//4)
            circle_radius = random_gen.randint(20, 50)
            
            # Randomize between white and shadow
            cloud_shade = CLOUD_COLOR if random_gen.random() > 0.3 else CLOUD_SHADOW
            
            # Draw cloud puff
            pygame.draw.circle(cloud_surface, cloud_shade, (circle_x, circle_y), circle_radius)
    
    return cloud_surface

def generate_hills(width, height, num_layers, seed):
    """Generate hill silhouettes for distant background layers."""
    hill_layers = []
    random_gen = np.random.RandomState(seed)
    
    for layer in range(num_layers):
        hill_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Generate hill points
        hill_height = height // (2 + layer)  # Further layers are taller
        frequency = 0.005 * (1 + layer * 0.5)  # Further layers have more variation
        points = []
        
        for x in range(0, width + 20, 20):
            # Use noise to create natural-looking hills
            y_offset = int(math.sin(x * frequency) * 30 + 
                          math.sin(x * frequency * 2.5) * 15 +
                          random_gen.randint(-10, 10))
            y_pos = height - hill_height + y_offset
            points.append((x, y_pos))
        
        # Add bottom corners to close the polygon
        points.append((width + 20, height))
        points.append((0, height))
        
        # Draw the hills
        pygame.draw.polygon(hill_surface, HILL_COLORS[layer % len(HILL_COLORS)], points)
        
        hill_layers.append(hill_surface)
    
    return hill_layers

def generate_stars(width, height, seed):
    """Generate a starry night background."""
    star_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    random_gen = np.random.RandomState(seed)
    
    # Create stars
    for _ in range(width * height // 500):  # Density of stars
        x = random_gen.randint(0, width)
        y = random_gen.randint(0, height * 2 // 3)  # Stars mainly in upper part
        size = random_gen.randint(1, 4)  # Use randint instead of choice for sizes
        
        # Fix: Use a different method for selecting random colors
        color_index = random_gen.randint(0, len(STAR_COLORS))
        color = STAR_COLORS[color_index % len(STAR_COLORS)]
        
        if size == 1:
            star_surface.set_at((x, y), color)
        else:
            pygame.draw.circle(star_surface, color, (x, y), size // 2)
    
    return star_surface

def get_sky_color(time_of_day):
    """Get sky color based on time of day (0.0 to 1.0)."""
    # Time of day: 0.0 = midnight, 0.25 = sunrise, 0.5 = noon, 0.75 = sunset, 1.0 = midnight
    if time_of_day < 0.25:  # Night to sunrise
        factor = time_of_day / 0.25
        return blend_colors(SKY_COLOR_NIGHT, SKY_COLOR_DAY, factor)
    elif time_of_day < 0.75:  # Day
        return SKY_COLOR_DAY
    else:  # Sunset to night
        factor = (time_of_day - 0.75) / 0.25
        return blend_colors(SKY_COLOR_DAY, SKY_COLOR_NIGHT, factor)

def blend_colors(color1, color2, factor):
    """Blend between two colors by a factor (0.0 to 1.0)."""
    r = int(color1[0] + (color2[0] - color1[0]) * factor)
    g = int(color1[1] + (color2[1] - color1[1]) * factor)
    b = int(color1[2] + (color2[2] - color1[2]) * factor)
    return (r, g, b)

def draw_background(screen, camera_x, camera_y, time_of_day, width, height, cloud_layer, hill_layers, star_layer):
    """Draw the entire background with parallax effect."""
    # Fill the sky
    sky_color = get_sky_color(time_of_day)
    screen.fill(sky_color)
    
    # Draw stars if it's night
    if time_of_day > 0.75 or time_of_day < 0.25:
        star_alpha = 255
        if 0.2 < time_of_day < 0.3:  # Fade out at sunrise
            star_alpha = int(255 * (0.3 - time_of_day) / 0.1)
        elif 0.7 < time_of_day < 0.8:  # Fade in at sunset
            star_alpha = int(255 * (time_of_day - 0.7) / 0.1)
        
        star_layer.set_alpha(star_alpha)
        star_offset_x = int(camera_x * 0.01) % width
        screen.blit(star_layer, (-star_offset_x, 0))
        if star_offset_x > 0:
            screen.blit(star_layer, (width - star_offset_x, 0))
    
    # Draw distant hills with parallax
    for i, hill_layer in enumerate(hill_layers):
        parallax_factor = 0.1 * (i + 1)
        offset_x = int(camera_x * parallax_factor) % width
        screen.blit(hill_layer, (-offset_x, 0))
        if offset_x > 0:
            screen.blit(hill_layer, (width - offset_x, 0))
    
    # Draw clouds with parallax
    cloud_offset_x = int(camera_x * 0.2) % width
    screen.blit(cloud_layer, (-cloud_offset_x, 0))
    if cloud_offset_x > 0:
        screen.blit(cloud_layer, (width - cloud_offset_x, 0))
