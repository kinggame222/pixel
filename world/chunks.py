import numpy as np
import threading
import queue
import time
import json
import os

from core import config

# Global variables to store world data
loaded_chunks = {}  # Dictionary to store loaded chunks {(chunk_x, chunk_y): numpy_array}
modified_chunks = set()  # Set to track modified chunks for saving
chunk_cache = {}  # Dictionary to store rendered chunks for performance
chunk_generation_queue = queue.Queue()  # Queue for chunk generation tasks
chunk_worker_running = False  # Flag to control worker threads

def get_chunk_coords(block_x, block_y):
    """Get the chunk coordinates that contain the given block position."""
    chunk_x = block_x // config.CHUNK_SIZE
    chunk_y = block_y // config.CHUNK_SIZE
    return chunk_x, chunk_y

def get_block_at(block_x, block_y):
    """Get the block type at the given position."""
    chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
    if (chunk_x, chunk_y) not in loaded_chunks:
        return config.EMPTY  # Default to empty if chunk not loaded
    
    # Calculate position within chunk
    local_x = block_x % config.CHUNK_SIZE
    local_y = block_y % config.CHUNK_SIZE
    
    return loaded_chunks[(chunk_x, chunk_y)][local_y, local_x]

def set_block_at(block_x, block_y, block_type):
    """Set the block type at the given position."""
    chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
    if (chunk_x, chunk_y) not in loaded_chunks:
        return False  # Chunk not loaded
    
    # Calculate position within chunk
    local_x = block_x % config.CHUNK_SIZE
    local_y = block_y % config.CHUNK_SIZE
    
    # Update the block
    loaded_chunks[(chunk_x, chunk_y)][local_y, local_x] = block_type
    
    # Mark the chunk as modified
    modified_chunks.add((chunk_x, chunk_y))
    
    # Clear the chunk from the rendering cache
    if (chunk_x, chunk_y) in chunk_cache:
        del chunk_cache[(chunk_x, chunk_y)]
    
    return True

def mark_chunk_modified(chunk_x, chunk_y):
    """Mark a chunk as modified."""
    if (chunk_x, chunk_y) in loaded_chunks:
        modified_chunks.add((chunk_x, chunk_y))
        
        # Clear the chunk from the rendering cache
        if (chunk_x, chunk_y) in chunk_cache:
            del chunk_cache[(chunk_x, chunk_y)]

def generate_chunk_worker():
    """Worker function to generate chunks from the queue."""
    global chunk_worker_running
    while chunk_worker_running:
        try:
            # Get a task from the queue with a timeout
            task = chunk_generation_queue.get(timeout=0.5)
            chunk_x, chunk_y, seed = task
            
            # Check if the chunk is already loaded
            if (chunk_x, chunk_y) in loaded_chunks:
                chunk_generation_queue.task_done()
                continue
            
            # Generate the chunk
            generate_chunk(chunk_x, chunk_y, seed)
            
            # Mark task as done
            chunk_generation_queue.task_done()
        except queue.Empty:
            pass  # Queue is empty, continue waiting
        except Exception as e:
            print(f"Error in chunk generation worker: {e}")
            chunk_generation_queue.task_done()  # Mark task as done to avoid stalling

def start_chunk_workers(num_workers, seed):
    """Start worker threads for chunk generation."""
    global chunk_worker_running
    chunk_worker_running = True
    
    workers = []
    for _ in range(num_workers):
        worker = threading.Thread(target=generate_chunk_worker)
        worker.daemon = True
        worker.start()
        workers.append(worker)
    
    return workers

def stop_chunk_workers(workers):
    """Stop worker threads for chunk generation."""
    global chunk_worker_running
    chunk_worker_running = False
    
    # Wait for workers to finish
    for worker in workers:
        if worker.is_alive():
            worker.join(0.5)

def generate_chunk(chunk_x, chunk_y, seed):
    """Generate a new chunk at the given position."""
    # Create an empty chunk as a numpy array
    chunk = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.int32)
    chunk.fill(config.EMPTY)
    
    try:
        # Import map generation and generate terrain for this chunk
        from map_generation import generate_chunk as gen_chunk_terrain
        chunk = gen_chunk_terrain(chunk, chunk_x, chunk_y, seed)
    except ImportError:
        print("Map generation module not found. Using empty chunk.")
    except Exception as e:
        print(f"Error generating chunk terrain: {e}")
    
    # Add the chunk to the loaded chunks
    loaded_chunks[(chunk_x, chunk_y)] = chunk
    modified_chunks.add((chunk_x, chunk_y))
    
    return chunk

def ensure_chunks_around_point(world_x, world_y, radius):
    """Ensure chunks are loaded around a given point."""
    block_x = int(world_x // config.PIXEL_SIZE)
    block_y = int(world_y // config.PIXEL_SIZE)
    center_chunk_x, center_chunk_y = get_chunk_coords(block_x, block_y)
    
    # Queue chunks in a spiral pattern, starting from the center
    for r in range(radius + 1):
        for dx in range(-r, r + 1):
            for dy in [-r, r]:  # Top and bottom edges
                chunk_x, chunk_y = center_chunk_x + dx, center_chunk_y + dy
                if (chunk_x, chunk_y) not in loaded_chunks and (chunk_x, chunk_y) not in chunk_generation_queue.queue:
                    chunk_generation_queue.put((chunk_x, chunk_y, 1))
        
        for dy in range(-r + 1, r):  # Left and right edges
            for dx in [-r, r]:
                chunk_x, chunk_y = center_chunk_x + dx, center_chunk_y + dy
                if (chunk_x, chunk_y) not in loaded_chunks and (chunk_x, chunk_y) not in chunk_generation_queue.queue:
                    chunk_generation_queue.put((chunk_x, chunk_y, 1))

def unload_distant_chunks(world_x, world_y, unload_distance):
    """Unload chunks that are too far from a given position."""
    block_x = int(world_x // config.PIXEL_SIZE)
    block_y = int(world_y // config.PIXEL_SIZE)
    center_chunk_x, center_chunk_y = get_chunk_coords(block_x, block_y)
    
    # Calculate squared unload distance to avoid square root
    squared_unload_distance = unload_distance * unload_distance * config.CHUNK_SIZE * config.CHUNK_SIZE
    
    # Find chunks to unload
    chunks_to_unload = []
    for chunk_pos in loaded_chunks.keys():
        chunk_x, chunk_y = chunk_pos
        dx = (chunk_x - center_chunk_x) * config.CHUNK_SIZE
        dy = (chunk_y - center_chunk_y) * config.CHUNK_SIZE
        squared_distance = dx * dx + dy * dy
        
        if squared_distance > squared_unload_distance:
            chunks_to_unload.append(chunk_pos)
    
    # Unload chunks
    for chunk_pos in chunks_to_unload:
        if chunk_pos in modified_chunks:
            # TODO: Save modified chunks before unloading
            pass
        
        # Remove from loaded chunks and caches
        if chunk_pos in loaded_chunks:
            del loaded_chunks[chunk_pos]
        if chunk_pos in chunk_cache:
            del chunk_cache[chunk_pos]
        if chunk_pos in modified_chunks:
            modified_chunks.remove(chunk_pos)

def get_active_chunks(player_x, player_y, screen_width, screen_height, view_multiplier=1.0, max_chunks=200):
    """Get active chunks that should be rendered based on the player's position."""
    block_x = int(player_x // config.PIXEL_SIZE)
    block_y = int(player_y // config.PIXEL_SIZE)
    center_chunk_x, center_chunk_y = get_chunk_coords(block_x, block_y)
    
    # Calculate the number of chunks visible on screen (with buffer)
    chunks_x = int((screen_width * view_multiplier) // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2
    chunks_y = int((screen_height * view_multiplier) // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2
    
    # Get chunks in the visible area
    active_chunks = []
    for dx in range(-chunks_x, chunks_x + 1):
        for dy in range(-chunks_y, chunks_y + 1):
            chunk_x = center_chunk_x + dx
            chunk_y = center_chunk_y + dy
            
            # Add chunk if it's loaded
            if (chunk_x, chunk_y) in loaded_chunks:
                active_chunks.append((chunk_x, chunk_y))
    
    # Limit the number of active chunks if necessary
    if len(active_chunks) > max_chunks:
        # Sort chunks by distance to player
        active_chunks.sort(key=lambda pos: ((pos[0] - center_chunk_x) ** 2 + (pos[1] - center_chunk_y) ** 2))
        active_chunks = active_chunks[:max_chunks]
    
    return active_chunks

def save_world_to_file(filename, storage_system=None):
    """Save the world state to a file."""
    world_data = {}
    
    # Save chunks
    world_data["chunks"] = {}
    for pos, chunk in loaded_chunks.items():
        chunk_x, chunk_y = pos
        # Convert NumPy array to list for JSON serialization
        chunk_data = chunk.tolist()
        world_data["chunks"][f"{chunk_x},{chunk_y}"] = chunk_data
    
    # Create data directory if it doesn't exist
    data_dir = os.path.dirname(filename)
    os.makedirs(data_dir, exist_ok=True)
    
    try:
        with open(filename, "w") as f:
            json.dump(world_data, f)
        print(f"World saved to {filename}")
        
        # Save storage data separately if storage system is provided
        if storage_system:
            storage_system.save_to_file()
            
        return True
    except Exception as e:
        print(f"Error saving world: {e}")
        return False

def load_world_from_file(filename, storage_system=None):
    """Load the world state from a file."""
    global loaded_chunks, modified_chunks
    
    try:
        if not os.path.exists(filename):
            print(f"No world file found at {filename}")
            # Generate default chunk at (0,0) if no world file exists
            generate_chunk(0, 0, 1)
            return False
            
        with open(filename, "r") as f:
            world_data = json.load(f)
        
        # Clear existing world data
        loaded_chunks = {}
        modified_chunks = set()
        
        # Load chunks
        if "chunks" in world_data:
            for pos_str, chunk_data in world_data["chunks"].items():
                chunk_x, chunk_y = map(int, pos_str.split(","))
                # Convert list back to NumPy array
                chunk = np.array(chunk_data, dtype=np.int32)
                loaded_chunks[(chunk_x, chunk_y)] = chunk
        
        # Ensure the origin chunk exists
        if (0, 0) not in loaded_chunks:
            generate_chunk(0, 0, 1)
            
        # Load storage data if storage system is provided
        if storage_system:
            storage_system.load_from_file()
        
        print(f"World loaded from {filename}")
        return True
    except Exception as e:
        print(f"Error loading world: {e}")
        # Generate default chunk if loading fails
        if (0, 0) not in loaded_chunks:
            generate_chunk(0, 0, 1)
        return False
