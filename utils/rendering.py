import pygame
from core import config
from world import chunks  # Import chunks to access the cache and modified chunks
from systems import conveyor_system, machine_system

def create_block_surfaces():
    """Create surfaces for each block type."""
    block_surfaces = {}
    for block_id, block_data in config.BLOCKS.items():
        # Create a surface for this block type
        surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE), pygame.SRCALPHA)
        
        # If it's an empty block, make it completely transparent
        if block_id == config.EMPTY:
            # Make the surface fully transparent
            surface.fill((0, 0, 0, 0))
        else:
            # Otherwise use the block's color
            color = block_data.get("color", (255, 0, 255))  # Default to magenta for missing colors
            surface.fill(color)
        
        block_surfaces[block_id] = surface
    return block_surfaces

def render_chunk(chunk, chunk_x, chunk_y, camera_x, camera_y, 
                mining_animation, block_surfaces, machine_system, multi_block_system=None):
    """Renders a chunk to a surface."""
    # Check if the chunk is in cache and not modified
    cache_key = (chunk_x, chunk_y)
    if cache_key in chunks.chunk_cache and cache_key not in chunks.modified_chunks:
        return chunks.chunk_cache[cache_key]
    
    # Create a new surface for rendering
    surface = pygame.Surface((config.CHUNK_SIZE * config.PIXEL_SIZE, config.CHUNK_SIZE * config.PIXEL_SIZE), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))  # Fully transparent background
    
    # Optimization: Draw blocks in batches by type
    blocks_by_type = {}
    
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            block_type = chunk[y, x]
            
            if block_type == config.EMPTY:
                continue
            
            # Convert chunk-local coordinates to world coordinates
            block_x = x * config.PIXEL_SIZE
            block_y = y * config.PIXEL_SIZE
            
            world_x = chunk_x * config.CHUNK_SIZE + x
            world_y = chunk_y * config.CHUNK_SIZE + y
            
            # Check for special rendering based on block type
            if block_type == machine_system.ore_processor_id and machine_system.is_machine_position(world_x, world_y):
                # Skip if not the origin point of the machine
                if not (world_x, world_y) in machine_system.machines:
                    continue
                
                # Get machine dimensions
                width, height = machine_system.get_machine_size(machine_system.ore_processor_id)
                
                # Create a special surface for the machine
                machine_surface = pygame.Surface((width * config.PIXEL_SIZE, height * config.PIXEL_SIZE))
                machine_color = config.BLOCKS[block_type]["color"]
                machine_surface.fill(machine_color)
                
                # Add visual details to the machine
                pygame.draw.rect(machine_surface, (100, 60, 140), (2, 2, width * config.PIXEL_SIZE - 4, height * config.PIXEL_SIZE // 3))
                pygame.draw.rect(machine_surface, (80, 80, 80), (width * config.PIXEL_SIZE // 4, height * config.PIXEL_SIZE // 2, 
                                                         width * config.PIXEL_SIZE // 2, height * config.PIXEL_SIZE // 3))
                
                # Only render the part of the machine that fits in this chunk
                visible_width = min(width, config.CHUNK_SIZE - x) * config.PIXEL_SIZE
                visible_height = min(height, config.CHUNK_SIZE - y) * config.PIXEL_SIZE
                
                if visible_width > 0 and visible_height > 0:
                    surface.blit(machine_surface, (block_x, block_y), (0, 0, visible_width, visible_height))
                continue
            
            # Check for multi-block structures
            if multi_block_system and multi_block_system.is_multi_block(world_x, world_y):
                origin = multi_block_system.get_multi_block_origin(world_x, world_y)
                if origin and origin[0] == world_x and origin[1] == world_y:
                    # This is the origin of a multi-block, render it specially
                    block_data = multi_block_system.multi_blocks.get(origin)
                    if block_data:
                        width, height = block_data["size"]
                        block_id = block_data["type"]
                        
                        # Create a special surface for the multi-block
                        special_surface = pygame.Surface((width * config.PIXEL_SIZE, height * config.PIXEL_SIZE))
                        block_color = config.BLOCKS[block_id]["color"]
                        special_surface.fill(block_color)
                        
                        # Add visual details based on block type
                        if block_id == config.STORAGE_CHEST:
                            # Draw chest details
                            pygame.draw.rect(special_surface, (120, 70, 20), (5, 5, width * config.PIXEL_SIZE - 10, height * config.PIXEL_SIZE - 10))
                            pygame.draw.rect(special_surface, (90, 50, 10), (width * config.PIXEL_SIZE // 3, height * config.PIXEL_SIZE // 2, 
                                                            width * config.PIXEL_SIZE // 3, height * config.PIXEL_SIZE // 6))
                        elif block_id == config.CONVEYOR_BELT:
                            # Draw conveyor details - direction arrows
                            direction = conveyor_system.conveyors.get(origin, {}).get("direction", 0)
                            arrow_color = (50, 50, 50)
                            
                            if direction == 0:  # Right
                                points = [(width * config.PIXEL_SIZE // 4, height * config.PIXEL_SIZE // 2),
                                         (width * config.PIXEL_SIZE * 3 // 4, height * config.PIXEL_SIZE // 2),
                                         (width * config.PIXEL_SIZE * 2 // 3, height * config.PIXEL_SIZE // 3)]
                                pygame.draw.polygon(special_surface, arrow_color, points)
                            elif direction == 1:  # Down
                                points = [(width * config.PIXEL_SIZE // 2, height * config.PIXEL_SIZE // 4),
                                         (width * config.PIXEL_SIZE // 2, height * config.PIXEL_SIZE * 3 // 4),
                                         (width * config.PIXEL_SIZE // 3, height * config.PIXEL_SIZE * 2 // 3)]
                                pygame.draw.polygon(special_surface, arrow_color, points)
                            elif direction == 2:  # Left
                                points = [(width * config.PIXEL_SIZE * 3 // 4, height * config.PIXEL_SIZE // 2),
                                         (width * config.PIXEL_SIZE // 4, height * config.PIXEL_SIZE // 2),
                                         (width * config.PIXEL_SIZE // 3, height * config.PIXEL_SIZE // 3)]
                                pygame.draw.polygon(special_surface, arrow_color, points)
                            elif direction == 3:  # Up
                                points = [(width * config.PIXEL_SIZE // 2, height * config.PIXEL_SIZE * 3 // 4),
                                         (width * config.PIXEL_SIZE // 2, height * config.PIXEL_SIZE // 4),
                                         (width * config.PIXEL_SIZE // 3, height * config.PIXEL_SIZE // 3)]
                                pygame.draw.polygon(special_surface, arrow_color, points)

                        # Only render the part that fits in this chunk
                        visible_width = min(width, config.CHUNK_SIZE - x) * config.PIXEL_SIZE
                        visible_height = min(height, config.CHUNK_SIZE - y) * config.PIXEL_SIZE
                        
                        if visible_width > 0 and visible_height > 0:
                            surface.blit(special_surface, (block_x, block_y), (0, 0, visible_width, visible_height))
                    continue
                else:
                    # This is a child block of a multi-block, skip rendering as it's handled by the origin
                    continue
            
            # Group blocks by type for batch rendering
            if (world_y, world_x) in mining_animation:
                # Mining animation blocks need individual rendering
                animation_progress = mining_animation[(world_y, world_x)]
                red_intensity = int(255 * animation_progress)
                animated_surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE))
                block_color = config.BLOCKS[block_type]["color"]
                animated_color = (min(block_color[0] + red_intensity, 255),
                                max(block_color[1] - int(red_intensity * 0.5), 0),
                                max(block_color[2] - int(red_intensity * 0.5), 0))
                animated_surface.fill(animated_color)
                surface.blit(animated_surface, (block_x, block_y))
            else:
                # Group normal blocks by type
                if block_type not in blocks_by_type:
                    blocks_by_type[block_type] = []
                blocks_by_type[block_type].append((block_x, block_y))
    
    # Batch render blocks by type
    for block_type, positions in blocks_by_type.items():
        if block_type in block_surfaces:
            block_surface = block_surfaces[block_type]
            for pos in positions:
                surface.blit(block_surface, pos)
    
    # Cache the rendered chunk
    chunks.chunk_cache[cache_key] = surface
    
    # Mark as no longer modified
    if cache_key in chunks.modified_chunks:
        chunks.modified_chunks.remove(cache_key)
    
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
