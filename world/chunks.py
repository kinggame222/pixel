import numpy as np
import threading
import queue
import time
import json
import os
from world.map_generation import generate_chunk as gen_chunk_terrain
from core import config

# Global variables to store world data
loaded_chunks = {}  # Dictionary to store loaded chunks {(chunk_x, chunk_y): numpy_array}
modified_chunks = set()  # Set to track modified chunks for saving
chunk_cache = {}  # Dictionary to store rendered chunks for performance
chunk_generation_queue = queue.Queue()  # Queue for chunk generation tasks
chunk_worker_running = False  # Flag to control worker threads
origin_chunk_backup = None  # Backup for the origin chunk
chunk_lock = threading.RLock()  # Lock for thread-safe dictionary access

def get_chunk_coords(block_x, block_y):
    """Get the chunk coordinates that contain the given block position."""
    chunk_x = block_x // config.CHUNK_SIZE
    chunk_y = block_y // config.CHUNK_SIZE
    return chunk_x, chunk_y

def get_block_at(block_x, block_y):
    """Get the block type at the given position."""
    chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
    with chunk_lock:
        if (chunk_x, chunk_y) not in loaded_chunks:
            # Try to generate the chunk on-demand if needed
            if chunk_x == 0 and chunk_y == 0:
                print(f"Auto-generating origin chunk at ({chunk_x}, {chunk_y}) in get_block_at")
                generate_chunk(chunk_x, chunk_y, 1)  # Use seed 1 by default
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
            
            # Skip if the chunk is already loaded
            with chunk_lock:
                if (chunk_x, chunk_y) in loaded_chunks:
                    chunk_generation_queue.task_done()
                    continue
                    
            # Generate the chunk
            try:
                generate_chunk(chunk_x, chunk_y, seed)
                print(f"Worker generated chunk at ({chunk_x}, {chunk_y})")
            except Exception as e:
                print(f"Error generating chunk ({chunk_x}, {chunk_y}) in worker: {e}")
            
            # Mark task as done
            chunk_generation_queue.task_done()
            
            # Brief pause between generations to avoid freezing the game
            time.sleep(0.05)
            
        except queue.Empty:
            # Queue is empty, continue waiting
            time.sleep(0.1)
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
    print(f"Generating chunk at ({chunk_x}, {chunk_y})")
    
    # Create an empty chunk as a numpy array
    chunk = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.int32)
    chunk.fill(config.EMPTY)
    
    try:
        # Import map generation and generate terrain for this chunk
        chunk = gen_chunk_terrain(chunk, chunk_x, chunk_y, seed)
    except ImportError:
        print(f"Map generation module not found for ({chunk_x}, {chunk_y}). Using empty chunk.")
    except Exception as e:
        print(f"Error generating chunk terrain at ({chunk_x}, {chunk_y}): {e}")
        # Even if there's an error, we'll still create an empty chunk
    
    # Add the chunk to the loaded chunks with lock to prevent race conditions
    with chunk_lock:
        loaded_chunks[(chunk_x, chunk_y)] = chunk
        modified_chunks.add((chunk_x, chunk_y))
        
        # Verify the chunk was actually added
        if (chunk_x, chunk_y) in loaded_chunks:
            print(f"Chunk ({chunk_x}, {chunk_y}) successfully added to loaded_chunks")
            # Make a backup of origin chunk if it's the origin
            if chunk_x == 0 and chunk_y == 0:
                print("Created backup of origin chunk")
                global origin_chunk_backup
                origin_chunk_backup = chunk.copy()
        else:
            print(f"ERROR: Chunk ({chunk_x}, {chunk_y}) FAILED to be added to loaded_chunks")
    
    return chunk

def ensure_chunks_around_point(world_x, world_y, radius):
    """Ensure chunks are loaded around a given point."""
    block_x = int(world_x // config.PIXEL_SIZE)
    block_y = int(world_y // config.PIXEL_SIZE)
    center_chunk_x, center_chunk_y = get_chunk_coords(block_x, block_y)
    
    # Use a spiral pattern to prioritize loading chunks closest to the player first
    max_queued = 30  # Don't queue too many chunks at once
    queued = 0
    
    # Generate chunks in a spiral pattern
    for r in range(1, radius + 1):
        if queued >= max_queued:
            break
            
        # Top and bottom edges
        for dx in range(-r, r + 1):
            for dy in [-r, r]:
                chunk_x, chunk_y = center_chunk_x + dx, center_chunk_y + dy
                if (chunk_x, chunk_y) not in loaded_chunks and not any(item[0] == chunk_x and item[1] == chunk_y for item in list(chunk_generation_queue.queue)):
                    chunk_generation_queue.put((chunk_x, chunk_y, 1))
                    queued += 1
                    if queued >= max_queued:
                        return
        
        # Left and right edges (excluding corners)
        for dy in range(-r + 1, r):
            for dx in [-r, r]:
                chunk_x, chunk_y = center_chunk_x + dx, center_chunk_y + dy
                if (chunk_x, chunk_y) not in loaded_chunks and not any(item[0] == chunk_x and item[1] == chunk_y for item in list(chunk_generation_queue.queue)):
                    chunk_generation_queue.put((chunk_x, chunk_y, 1))
                    queued += 1
                    if queued >= max_queued:
                        return

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
    global loaded_chunks, modified_chunks
    
    try:
        # Determine the directory to save the file in
        data_dir = os.path.dirname(filename)
        if not data_dir:
            data_dir = "."  # Use current directory if filename only has the file name
        
        # Create the directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Prepare chunk data for saving
        chunk_data = {}
        for (chunk_x, chunk_y), chunk in loaded_chunks.items():
            # Convert NumPy array to list for JSON serialization
            chunk_data[f"{chunk_x},{chunk_y}"] = chunk.tolist()
        
        # Prepare world data for saving
        world_data = {
            "chunks": chunk_data,
            "player_x": 0,  # Example player data
            "player_y": 0,
            "seed": 1
        }
        
        # Save the world data to the file
        with open(filename, "w") as f:
            json.dump(world_data, f)
        
        print(f"World saved to {filename}")
    except Exception as e:
        print(f"Error saving world: {e}")

def load_world_from_file(filename, storage_system=None):
    """Load the world state from a file."""
    global loaded_chunks, modified_chunks
    
    print(f"Starting load_world_from_file with {filename}")
    
    if not os.path.exists(filename):
        print(f"No world file found at {filename}")
        print("Ensuring origin chunk exists...")
        generate_chunk(0, 0, 1)
        return False
        
    try:
        with open(filename, "r") as f:
            world_data = json.load(f)
        
        # Clear existing world data
        loaded_chunks = {}
        modified_chunks = set()
        
        # Load chunks
        if "chunks" in world_data:
            for pos_str, chunk_data in world_data["chunks"].items():
                chunk_x, chunk_y = map(int, pos_str.split(","))
                chunk = np.array(chunk_data, dtype=np.int32)
                loaded_chunks[(chunk_x, chunk_y)] = chunk
        
        print(f"World loaded from {filename}")

    except Exception as e:
        print(f"Error loading world: {e}")

    # Ensure the origin chunk exists regardless of load success/failure
    print("Checking for origin chunk...")
    if (0, 0) in loaded_chunks:
        print("Origin chunk found in loaded chunks")
    else:
        print("Origin chunk not found, generating...")
        generate_chunk(0, 0, 1)

    # Load storage data if storage system is provided
    if storage_system:
        storage_system.load_from_file()

    print(f"Loaded chunks keys: {list(loaded_chunks.keys())}")
    return True

def ensure_origin_chunk_exists():
    """Ensure the origin chunk (0,0) exists."""
    with chunk_lock:
        if (0, 0) not in loaded_chunks:
            print("Origin chunk missing, generating...")
            if origin_chunk_backup is not None:
                print("Restoring origin chunk from backup")
                loaded_chunks[(0, 0)] = origin_chunk_backup.copy()
                modified_chunks.add((0, 0))
            else:
                print("Creating new origin chunk")
                # Create a basic chunk with empty top half and dirt/stone bottom half
                chunk = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.int32)
                # Top half is air
                chunk[:config.CHUNK_SIZE//2, :] = config.EMPTY
                # Bottom half is dirt/stone
                chunk[config.CHUNK_SIZE//2:, :] = config.DIRT
                loaded_chunks[(0, 0)] = chunk
                modified_chunks.add((0, 0))
            print("Origin chunk is now present")
        return loaded_chunks[(0, 0)]

# Make sure the function is named so it can be imported
__all__ = [
    'get_chunk_coords', 'get_block_at', 'set_block_at', 'mark_chunk_modified',
    'generate_chunk', 'start_chunk_workers', 'stop_chunk_workers',
    'ensure_chunks_around_point', 'unload_distant_chunks', 'get_active_chunks',
    'save_world_to_file', 'load_world_from_file', 'chunk_lock',
    'ensure_origin_chunk_exists', 'chunk_generation_queue', 'loaded_chunks'  # Add these exports
]
