import pygame
from core import config
from world import chunks  # Import chunks to access the cache and modified chunks
import json
import os
import random

# Placeholder color for missing textures or invalid blocks
MISSING_TEXTURE_COLOR = (255, 0, 255)  # Bright Magenta

def load_block_data():
    """Load block data from blocks.json."""
    with open(os.path.join("blocks.json"), "r") as f:
        return {block["id"]: block for block in json.load(f)}

BLOCK_DATA = load_block_data()

def create_block_surfaces():
    """Create surfaces for each block type."""
    block_surfaces = {}
    texture_cache = {}  # Cache for loaded textures

    for block_id, block_data in BLOCK_DATA.items():
        surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE), pygame.SRCALPHA)
        
        # Check if the block has a texture
        texture_path = block_data.get("texture")
        if (texture_path):
            if texture_path not in texture_cache:
                try:
                    # Load and scale the texture once, store it in the cache
                    texture = pygame.image.load(texture_path).convert_alpha()
                    texture = pygame.transform.scale(texture, (config.PIXEL_SIZE, config.PIXEL_SIZE))
                    texture_cache[texture_path] = texture
                except pygame.error as e:
                    print(f"Error loading texture for block {block_data['name']}: {e}")
                    texture_cache[texture_path] = None
            if texture_cache[texture_path]:
                surface.blit(texture_cache[texture_path], (0, 0))
            else:
                surface.fill(tuple(block_data["color"]))  # Fallback to color
        else:
            # Fallback to color if no texture is provided
            surface.fill(tuple(block_data["color"]))
        
        block_surfaces[block_id] = surface
    return block_surfaces

def render_block(surface, block_type, x, y, block_surfaces):
    """Render a single block."""
    block_surface = block_surfaces[block_type]
    surface.blit(block_surface, (x, y))

def render_chunk(chunk_data, chunk_x, chunk_y, camera_x, camera_y, mining_animation, block_surfaces, machine_system, multi_block_system=None):
    """Render a single chunk to a surface."""
    chunk_surface = pygame.Surface((config.CHUNK_SIZE * config.PIXEL_SIZE, 
                                    config.CHUNK_SIZE * config.PIXEL_SIZE), pygame.SRCALPHA)
    
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            block_type = chunk_data[y, x]
            
            # Skip rendering empty blocks
            if block_type == config.EMPTY:
                continue

            # Calculate block position relative to the chunk surface
            block_rect = pygame.Rect(x * config.PIXEL_SIZE, y * config.PIXEL_SIZE, 
                                    config.PIXEL_SIZE, config.PIXEL_SIZE)

            # Check if block_type and its texture exist
            block_info = config.BLOCKS.get(block_type)
            texture_path = block_info.get("texture") if block_info else None

            if texture_path and block_type in block_surfaces:
                # Use pre-rendered surface if available
                block_surface = block_surfaces[block_type]
                chunk_surface.blit(block_surface, block_rect.topleft)
            elif block_info and "color" in block_info:
                # Fallback to color if texture is missing but color exists
                pygame.draw.rect(chunk_surface, block_info["color"], block_rect)
            else:
                # Fallback to magenta if block info or color is missing
                pygame.draw.rect(chunk_surface, MISSING_TEXTURE_COLOR, block_rect)

            # --- Render Mining Animation ---
            world_x = chunk_x * config.CHUNK_SIZE + x
            world_y = chunk_y * config.CHUNK_SIZE + y
            mining_key = (world_y, world_x)  # Use world coords for mining progress key

            if mining_key in mining_animation:
                progress = mining_animation[mining_key]
                if progress > 0:
                    overlay_alpha = int(150 * (1 - progress))  # Fade out as progress increases
                    overlay_color = (0, 0, 0, overlay_alpha)
                    overlay_surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE), pygame.SRCALPHA)
                    overlay_surface.fill(overlay_color)
                    
                    # Draw cracks (example)
                    crack_color = (50, 50, 50, 200)
                    num_cracks = int(progress * 5)  # More cracks as progress increases
                    for _ in range(num_cracks):
                        start_pos = (random.randint(0, config.PIXEL_SIZE), random.randint(0, config.PIXEL_SIZE))
                        end_pos = (random.randint(0, config.PIXEL_SIZE), random.randint(0, config.PIXEL_SIZE))
                        pygame.draw.line(overlay_surface, crack_color, start_pos, end_pos, 1)

                    chunk_surface.blit(overlay_surface, block_rect.topleft)

    return chunk_surface

def draw_performance_stats(screen, dt, active_chunk_count, cache_size, fps_font):
    """Draw performance statistics on screen."""
    fps = int(1.0 / dt) if dt > 0 else 0
    text_color = (255, 255, 0)  # Yellow
    
    fps_text = f"FPS: {fps}"
    chunks_text = f"Chunks: {active_chunk_count}"
    memory_text = f"Cache: {cache_size} chunks"
    modified_text = f"Modified: {len(chunks.modified_chunks)} chunks"
    
    fps_surface = fps_font.render(fps_text, True, text_color)
    chunks_surface = fps_font.render(chunks_text, True, text_color)
    memory_surface = fps_font.render(memory_text, True, text_color)
    modified_surface = fps_font.render(modified_text, True, text_color)
    
    screen.blit(fps_surface, (10, 10))
    screen.blit(chunks_surface, (10, 30))
    screen.blit(memory_surface, (10, 50))
    screen.blit(modified_surface, (10, 70))
