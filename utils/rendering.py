import pygame
from core import config
from world import chunks  # Import chunks to access the cache and modified chunks
import json
import os

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

def render_chunk(chunk, chunk_x, chunk_y, camera_x, camera_y, 
                mining_animation, block_surfaces, machine_system, multi_block_system=None):
    """Renders a chunk to a surface."""
    # Create a new surface for rendering
    surface = pygame.Surface((config.CHUNK_SIZE * config.PIXEL_SIZE, config.CHUNK_SIZE * config.PIXEL_SIZE), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))  # Fully transparent background
    
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            block_type = chunk[y, x]
            if block_type == config.ORE_PROCESSOR:
                # Vérifiez si c'est l'origine de l'ore_processor
                origin_x, origin_y = chunk_x * config.CHUNK_SIZE + x, chunk_y * config.CHUNK_SIZE + y
                machine_origin = machine_system.get_machine_origin(origin_x, origin_y)
                if machine_origin == (origin_x, origin_y):  # Vérifiez si c'est l'origine
                    width, height = config.BLOCKS[block_type].get("size", (1, 1))
                    
                    # Chargez et redimensionnez la texture pour couvrir tout le multi-bloc
                    texture = pygame.image.load(config.BLOCKS[block_type]["texture"]).convert_alpha()
                    texture = pygame.transform.scale(texture, (width * config.PIXEL_SIZE, height * config.PIXEL_SIZE))
                    
                    # Blit la texture redimensionnée sur la surface principale
                    screen_x = (origin_x - chunk_x * config.CHUNK_SIZE) * config.PIXEL_SIZE
                    screen_y = (origin_y - chunk_y * config.CHUNK_SIZE) * config.PIXEL_SIZE
                    surface.blit(texture, (screen_x, screen_y))
            elif block_type != config.EMPTY:
                block_x = x * config.PIXEL_SIZE
                block_y = y * config.PIXEL_SIZE
                render_block(surface, block_type, block_x, block_y, block_surfaces)
                # Debug print (Commented out for performance)
                # print(f"[DEBUG render_chunk] Rendering block type {block_type} at chunk ({chunk_x},{chunk_y}) position ({x},{y})")
    
    return surface

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
