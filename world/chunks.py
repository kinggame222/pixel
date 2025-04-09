import numpy as np
from queue import Queue, Empty
import threading
import os
import json
from core import config
import time

# --- Chunk Management ---
loaded_chunks = {}
chunk_cache = {}
modified_chunks = set()

# Thread-safe queue for chunk generation requests
chunk_gen_queue = Queue()
chunk_gen_active = True  # Flag to control chunk generation threads

def get_chunk_coords(x, y):
    """Returns the chunk coordinates for a given block coordinate."""
    # Handle negative coordinates properly
    chunk_x = x // config.CHUNK_SIZE
    if x < 0 and x % config.CHUNK_SIZE != 0:
        chunk_x -= 1
    chunk_y = y // config.CHUNK_SIZE
    if y < 0 and y % config.CHUNK_SIZE != 0:
        chunk_y -= 1
    return chunk_x, chunk_y

def get_local_block_coords(x, y):
    """Returns the local coordinates within a chunk for a given block coordinate."""
    local_x = x % config.CHUNK_SIZE
    if local_x < 0:
        local_x += config.CHUNK_SIZE
    local_y = y % config.CHUNK_SIZE
    if local_y < 0:
        local_y += config.CHUNK_SIZE
    return local_x, local_y

def get_block_at(x, y):
    """Gets the block type at the given world coordinates."""
    chunk_x, chunk_y = get_chunk_coords(x, y)
    local_x, local_y = get_local_block_coords(x, y)
    
    # Make sure the chunk is loaded
    chunk_key = (chunk_x, chunk_y)
    if chunk_key not in loaded_chunks:
        return config.EMPTY  # Return empty for unloaded chunks
    
    return loaded_chunks[chunk_key][local_y, local_x]

def set_block_at(x, y, block_type):
    """Sets the block type at the given world coordinates."""
    chunk_x, chunk_y = get_chunk_coords(x, y)
    local_x, local_y = get_local_block_coords(x, y)
    
    # Make sure the chunk is loaded
    chunk_key = (chunk_x, chunk_y)
    if chunk_key not in loaded_chunks:
        # Import here to avoid circular imports
        from world.map_generation import generate_chunk_terrain
        chunk = np.full((config.CHUNK_SIZE, config.CHUNK_SIZE), config.EMPTY, dtype=np.uint8)
        loaded_chunks[chunk_key] = chunk
    
    loaded_chunks[chunk_key][local_y, local_x] = block_type
    mark_chunk_modified(chunk_x, chunk_y)

def generate_chunk(chunk_x, chunk_y, seed=1):
    """Generates a new chunk at the given chunk coordinates."""
    # Create a new chunk filled with empty blocks
    chunk = np.full((config.CHUNK_SIZE, config.CHUNK_SIZE), config.EMPTY, dtype=np.uint8)
    
    # Import generate_chunk_terrain at runtime to avoid circular imports
    from world.map_generation import generate_chunk_terrain
    
    # Generate terrain using the map_generation module
    generate_chunk_terrain(chunk, chunk_x, chunk_y, seed)
    
    # Store the chunk in loaded_chunks
    loaded_chunks[(chunk_x, chunk_y)] = chunk
    
    # Mark the chunk as modified
    mark_chunk_modified(chunk_x, chunk_y)
    
    return chunk

def chunk_generation_worker(seed=1):
    """Worker function for background chunk generation."""
    global chunk_gen_active
    while chunk_gen_active:
        try:
            # Get a chunk request from the queue with a timeout
            chunk_x, chunk_y = chunk_gen_queue.get(timeout=1.0)
            
            # Skip if the chunk is already loaded
            if (chunk_x, chunk_y) in loaded_chunks:
                chunk_gen_queue.task_done()
                continue
            
            # Generate the chunk
            generate_chunk(chunk_x, chunk_y, seed)
            
            # Mark the task as done
            chunk_gen_queue.task_done()
        except Empty:  # Use the correct Empty exception
            # Queue is empty, just continue
            pass
        except Exception as e:
            print(f"Error in chunk generation: {e}")

def ensure_chunks_around_point(x, y, radius):
    """Ensures that chunks around the given point are loaded or queued for loading."""
    center_chunk_x, center_chunk_y = get_chunk_coords(x // config.PIXEL_SIZE, y // config.PIXEL_SIZE)
    
    # Queue chunks for loading
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            chunk_x = center_chunk_x + dx
            chunk_y = center_chunk_y + dy
            
            if (chunk_x, chunk_y) not in loaded_chunks:
                chunk_gen_queue.put((chunk_x, chunk_y))  # Queue chunk for generation

def unload_distant_chunks(player_x, player_y, unload_distance):
    """Unloads chunks that are too far from the player."""
    player_chunk_x, player_chunk_y = get_chunk_coords(int(player_x // config.PIXEL_SIZE), 
                                                     int(player_y // config.PIXEL_SIZE))
    
    # Find chunks to unload
    chunks_to_unload = []
    for chunk_key in list(loaded_chunks.keys()):
        chunk_x, chunk_y = chunk_key
        distance = max(abs(chunk_x - player_chunk_x), abs(chunk_y - player_chunk_y))
        if distance > unload_distance:
            chunks_to_unload.append(chunk_key)
    
    # Unload the chunks
    for chunk_key in chunks_to_unload:
        # Save modified chunks (if we had persistence)
        if chunk_key in modified_chunks:
            # Remove from modified chunks set
            modified_chunks.remove(chunk_key)
        
        # Remove from loaded chunks
        del loaded_chunks[chunk_key]
        
        # Remove from render cache
        if chunk_key in chunk_cache:
            del chunk_cache[chunk_key]

def get_active_chunks(player_x, player_y, screen_width, screen_height, view_distance_multiplier, max_active_chunks):
    """Returns a set of active chunk coordinates based on the player's position and screen size."""
    # Increase the view distance using the multiplier
    expanded_width = screen_width * view_distance_multiplier
    expanded_height = screen_height * view_distance_multiplier
    
    start_x = int((player_x - expanded_width // 2) // (config.PIXEL_SIZE * config.CHUNK_SIZE))
    start_y = int((player_y - expanded_height // 2) // (config.PIXEL_SIZE * config.CHUNK_SIZE))
    end_x = int((player_x + expanded_width // 2) // (config.PIXEL_SIZE * config.CHUNK_SIZE))
    end_y = int((player_y + expanded_height // 2) // (config.PIXEL_SIZE * config.CHUNK_SIZE))

    active_chunks = set()
    for x in range(start_x - 1, end_x + 2):
        for y in range(start_y - 1, end_y + 2):
            active_chunks.add((x, y))
    
    # Limit the number of active chunks for performance
    if len(active_chunks) > max_active_chunks:
        # Sort chunks by distance from player
        player_chunk_x = player_x // (config.PIXEL_SIZE * config.CHUNK_SIZE)
        player_chunk_y = player_y // (config.PIXEL_SIZE * config.CHUNK_SIZE)
        
        # Get player movement direction for prioritizing chunks
        import pygame
        keys = pygame.key.get_pressed()
        dir_x, dir_y = 0, 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]: dir_x = -1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dir_x = 1
        if keys[pygame.K_UP] or keys[pygame.K_w]: dir_y = -1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: dir_y = 1
        
        # Calculate distance with a bias towards movement direction
        chunks_with_distance = []
        for c in active_chunks:
            # Base distance
            dx = c[0] - player_chunk_x
            dy = c[1] - player_chunk_y
            dist = dx*dx + dy*dy
            
            # Apply direction bias (reduce distance in the direction of movement)
            if dir_x != 0 and np.sign(dx) == np.sign(dir_x):
                dist *= 0.8
            if dir_y != 0 and np.sign(dy) == np.sign(dir_y):
                dist *= 0.8
                
            chunks_with_distance.append((c, dist))
            
        chunks_with_distance.sort(key=lambda x: x[1])  # Sort by distance
        active_chunks = set([c[0] for c in chunks_with_distance[:max_active_chunks]])
    
    return active_chunks

def mark_chunk_modified(chunk_x, chunk_y):
    """Mark a chunk as modified so it will be re-rendered."""
    modified_chunks.add((chunk_x, chunk_y))
    # Also remove from cache so it's rendered again
    if (chunk_x, chunk_y) in chunk_cache:
        del chunk_cache[(chunk_x, chunk_y)]

def save_world_to_file(filename):
    """Saves the current world (loaded chunks) to a JSON file."""
    world_data = []
    for (chunk_x, chunk_y), chunk in loaded_chunks.items():
        chunk_data = {
            "chunk_x": chunk_x,
            "chunk_y": chunk_y,
            "blocks": chunk.tolist()  # Convert numpy array to a list for JSON serialization
        }
        world_data.append(chunk_data)
    
    with open(filename, "w") as f:
        json.dump(world_data, f, indent=4)
    print(f"World saved to {filename}")

def load_world_from_file(filename):
    """Loads the world (chunks) from a JSON file."""
    if not os.path.exists(filename):
        print(f"No save file found at {filename}")
        return
    
    with open(filename, "r") as f:
        world_data = json.load(f)
    
    for chunk_data in world_data:
        chunk_x = chunk_data["chunk_x"]
        chunk_y = chunk_data["chunk_y"]
        blocks = np.array(chunk_data["blocks"], dtype=np.uint8)  # Convert list back to numpy array
        loaded_chunks[(chunk_x, chunk_y)] = blocks
        # Mark as modified to ensure they're re-rendered
        mark_chunk_modified(chunk_x, chunk_y)
    print(f"World loaded from {filename}")

def start_chunk_workers(num_workers, seed=1):
    """Start worker threads for chunk generation."""
    workers = []
    for i in range(num_workers):
        thread = threading.Thread(target=chunk_generation_worker, args=(seed,), daemon=True)
        thread.start()
        workers.append(thread)
    return workers

def stop_chunk_workers(workers):
    """Stop chunk generation worker threads."""
    global chunk_gen_active
    chunk_gen_active = False
    for thread in workers:
        thread.join(timeout=0.5)  # Give threads time to exit
