import numpy as np
import threading
import queue
import time
import json
import os
import traceback
from world.map_generation import generate_chunk as generate_chunk_terrain_cpu
from core import config

from utils.gpu_detection import GPU_AVAILABLE, detect_gpu

GPU_GENERATION_ENABLED = False
generate_chunk_gpu = None
try:
    from world.gpu_map_generation import generate_chunk_gpu
    if GPU_AVAILABLE:
        GPU_GENERATION_ENABLED = True
except ImportError:
    GPU_GENERATION_ENABLED = False
    print("GPU map generation module not found or GPU not available.")

if GPU_GENERATION_ENABLED:
    print("GPU detected! Using GPU acceleration for terrain generation.")
else:
    print("No compatible GPU detected or GPU module not found. Using CPU for terrain generation.")

loaded_chunks = {}
modified_chunks = set()
chunk_generation_queue = queue.Queue()
chunk_worker_running = threading.Event()
chunk_lock = threading.RLock()
generating_chunks = set()

def get_chunk_coords(block_x, block_y):
    chunk_x = int(block_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    chunk_y = int(block_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    return chunk_x, chunk_y

def get_block_coords_in_chunk(block_world_x, block_world_y):
    local_x = int(block_world_x // config.PIXEL_SIZE) % config.CHUNK_SIZE
    local_y = int(block_world_y // config.PIXEL_SIZE) % config.CHUNK_SIZE
    return local_x, local_y

def get_block_at(world_x, world_y):
    """Gets the block type at the given world coordinates."""
    chunk_x, chunk_y = get_chunk_coords(world_x, world_y)
    local_x, local_y = world_x % config.CHUNK_SIZE, world_y % config.CHUNK_SIZE

    with chunk_lock:
        if (chunk_x, chunk_y) in loaded_chunks:
            block_type = loaded_chunks[(chunk_x, chunk_y)][local_y, local_x]
            # --- DEBUG PRINT (Commented out for performance) ---
            # print(f"[DEBUG get_block_at] Coords ({world_x},{world_y}) -> Chunk ({chunk_x},{chunk_y}), Local ({local_x},{local_y}) -> Type: {block_type}")
            # --- END DEBUG ---
            return block_type
        else:
            # --- DEBUG PRINT (Commented out for performance) ---
            # print(f"[DEBUG get_block_at] Coords ({world_x},{world_y}) -> Chunk ({chunk_x},{chunk_y}) NOT LOADED")
            # --- END DEBUG ---
            return config.EMPTY

def set_block_at(world_x, world_y, block_type):
    """Sets the block type at the given world coordinates."""
    chunk_x, chunk_y = get_chunk_coords(world_x, world_y)
    local_x, local_y = world_x % config.CHUNK_SIZE, world_y % config.CHUNK_SIZE

    with chunk_lock:
        if (chunk_x, chunk_y) in loaded_chunks:
            try:
                # --- DEBUG PRINT (Commented out for performance) ---
                # old_type = loaded_chunks[(chunk_x, chunk_y)][local_y, local_x]
                # print(f"[DEBUG set_block_at] Setting block at ({world_x},{world_y}) [Chunk ({chunk_x},{chunk_y}), Local ({local_x},{local_y})] from {old_type} to {block_type}")
                # --- END DEBUG ---

                loaded_chunks[(chunk_x, chunk_y)][local_y, local_x] = block_type
                mark_chunk_modified(chunk_x, chunk_y) # Ensure modification is marked

                # --- DEBUG PRINT (Commented out for performance) ---
                # Verify immediately after setting
                # new_type = loaded_chunks[(chunk_x, chunk_y)][local_y, local_x]
                # print(f"[DEBUG set_block_at] Verification: Block at ({local_y},{local_x}) in chunk ({chunk_x},{chunk_y}) is now {new_type}")
                # if (chunk_x, chunk_y) in modified_chunks:
                #     print(f"[DEBUG set_block_at] Chunk ({chunk_x},{chunk_y}) is marked as modified.")
                # else:
                #     print(f"[DEBUG set_block_at] WARNING: Chunk ({chunk_x},{chunk_y}) was NOT marked as modified.")
                # --- END DEBUG ---

                return True # Indicate success
            except IndexError:
                print(f"Error: Local coordinates ({local_x}, {local_y}) out of bounds for chunk ({chunk_x}, {chunk_y}).")
                return False
            except Exception as e:
                print(f"Error setting block at ({world_x}, {world_y}): {e}")
                traceback.print_exc()
                return False
        else:
            # --- DEBUG PRINT (Commented out for performance) ---
            # print(f"[DEBUG set_block_at] Attempted to set block in unloaded chunk ({chunk_x}, {chunk_y}) at ({world_x},{world_y})")
            # --- END DEBUG ---
            return False # Indicate failure

def mark_chunk_modified(chunk_x, chunk_y):
    """Marks a chunk as modified."""
    with chunk_lock:
        if (chunk_x, chunk_y) in loaded_chunks: # Only mark if it's actually loaded
             modified_chunks.add((chunk_x, chunk_y))
             # print(f"Chunk ({chunk_x}, {chunk_y}) marked as modified.") # Optional debug

def generate_chunk_data(chunk_x, chunk_y, seed):
    if GPU_GENERATION_ENABLED and generate_chunk_gpu:
        try:
            chunk_data = generate_chunk_gpu(chunk_x, chunk_y, seed)
            if chunk_data is None or chunk_data.shape != (config.CHUNK_SIZE, config.CHUNK_SIZE):
                raise ValueError(f"GPU generation returned invalid data: {chunk_data}")
            return chunk_data
        except Exception as e:
            print(f"GPU generation failed for chunk ({chunk_x}, {chunk_y}): {e}. Falling back to CPU.")

    chunk_data = np.zeros((config.CHUNK_SIZE, config.CHUNK_SIZE), dtype=np.int32)
    chunk_data.fill(config.EMPTY)
    try:
        chunk_data = generate_chunk_terrain_cpu(chunk_data, chunk_x, chunk_y, seed)
        invalid_blocks = np.isin(chunk_data, list(config.BLOCKS.keys()), invert=True)
        if np.any(invalid_blocks):
            print(f"Warning: CPU generation created invalid block IDs in chunk ({chunk_x}, {chunk_y}). Replacing with EMPTY.")
            chunk_data[invalid_blocks] = config.EMPTY
        return chunk_data
    except Exception as e:
        print(f"CPU generation failed for chunk ({chunk_x}, {chunk_y}): {e}")
        traceback.print_exc()
        return np.full((config.CHUNK_SIZE, config.CHUNK_SIZE), config.EMPTY, dtype=np.int32)

def generate_chunk_worker():
    while chunk_worker_running.is_set():
        try:
            chunk_x, chunk_y, seed = chunk_generation_queue.get(timeout=0.1)

            should_generate = False
            with chunk_lock:
                if (chunk_x, chunk_y) not in loaded_chunks and (chunk_x, chunk_y) not in generating_chunks:
                    generating_chunks.add((chunk_x, chunk_y))
                    should_generate = True

            if should_generate:
                new_chunk_data = None
                try:
                    new_chunk_data = generate_chunk_data(chunk_x, chunk_y, seed)

                    with chunk_lock:
                        if (chunk_x, chunk_y) not in loaded_chunks:
                            if new_chunk_data is not None:
                                loaded_chunks[(chunk_x, chunk_y)] = new_chunk_data
                                modified_chunks.add((chunk_x, chunk_y))
                        generating_chunks.discard((chunk_x, chunk_y))
                except Exception as e:
                    print(f"Error processing chunk ({chunk_x}, {chunk_y}) in worker: {e}")
                    traceback.print_exc()
                    with chunk_lock:
                        generating_chunks.discard((chunk_x, chunk_y))
                finally:
                    chunk_generation_queue.task_done()
            else:
                chunk_generation_queue.task_done()

        except queue.Empty:
            time.sleep(0.1)
        except Exception as e:
            print(f"Error in chunk worker loop: {e}")
            traceback.print_exc()
            time.sleep(0.5)

def start_chunk_workers(num_workers, seed):
    if chunk_worker_running.is_set():
        print("Chunk workers already running.")
        return []

    chunk_worker_running.set()
    workers = []
    for i in range(num_workers):
        worker = threading.Thread(target=generate_chunk_worker, name=f"ChunkWorker-{i}", daemon=True)
        worker.start()
        workers.append(worker)
    print(f"Started {num_workers} chunk generation workers.")
    return workers

def stop_chunk_workers(workers):
    if not chunk_worker_running.is_set():
        print("Chunk workers already stopped.")
        return

    print("Stopping chunk workers...")
    chunk_worker_running.clear()

    q_size = chunk_generation_queue.qsize()
    if q_size > 0:
        print(f"Waiting for {q_size} chunks in queue to be processed or workers to time out...")
        chunk_generation_queue.join()

    for worker in workers:
        worker.join(timeout=1.0)
        if worker.is_alive():
            print(f"Warning: Worker {worker.name} did not stop gracefully.")
    print("Chunk workers stopped.")

def ensure_chunks_around_point(x, y, radius):
    center_chunk_x = int(x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    chunks_to_queue = []
    with chunk_lock:
        loaded_coords = set(loaded_chunks.keys())
        generating_coords = set(generating_chunks)

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                cx, cy = center_chunk_x + dx, center_chunk_y + dy
                if (cx, cy) not in loaded_coords and (cx, cy) not in generating_coords:
                    chunks_to_queue.append((cx, cy))

    chunks_to_queue.sort(key=lambda coords: abs(coords[0] - center_chunk_x) + abs(coords[1] - center_chunk_y))

    queued_count = 0
    for cx, cy in chunks_to_queue:
        chunk_generation_queue.put((cx, cy, config.SEED))
        queued_count += 1

def unload_distant_chunks(world_x, world_y, unload_distance_chunks):
    center_chunk_x = int(world_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(world_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    chunks_to_unload = []
    with chunk_lock:
        current_chunk_keys = list(loaded_chunks.keys())
        for chunk_x, chunk_y in current_chunk_keys:
            dist_x = abs(chunk_x - center_chunk_x)
            dist_y = abs(chunk_y - center_chunk_y)
            if max(dist_x, dist_y) > unload_distance_chunks:
                if chunk_x == 0 and chunk_y == 0:
                    continue
                chunks_to_unload.append((chunk_x, chunk_y))

    unloaded_count = 0
    if chunks_to_unload:
        with chunk_lock:
            for chunk_pos in chunks_to_unload:
                if chunk_pos in loaded_chunks:
                    del loaded_chunks[chunk_pos]
                    modified_chunks.discard(chunk_pos)
                    unloaded_count += 1

def get_active_chunks(world_x, world_y, screen_width, screen_height, view_multiplier, max_chunks):
    center_chunk_x = int(world_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(world_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    view_dist_pixels_x = (screen_width * view_multiplier) / 2
    view_dist_pixels_y = (screen_height * view_multiplier) / 2
    chunk_span_x = int(view_dist_pixels_x // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2
    chunk_span_y = int(view_dist_pixels_y // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2

    active_chunks_list = []
    with chunk_lock:
        for dx in range(-chunk_span_x, chunk_span_x + 1):
            for dy in range(-chunk_span_y, chunk_span_y + 1):
                chunk_coords = (center_chunk_x + dx, center_chunk_y + dy)
                if chunk_coords in loaded_chunks:
                    active_chunks_list.append(chunk_coords)

    if len(active_chunks_list) > max_chunks:
        active_chunks_list.sort(key=lambda pos: max(abs(pos[0] - center_chunk_x), abs(pos[1] - center_chunk_y)))
        active_chunks_list = active_chunks_list[:max_chunks]

    return active_chunks_list

def save_world_to_file(filename, storage_system, player_pos):
    """Saves the current world state (loaded chunks, modified chunks, player position, storage) to a file."""
    print(f"Attempting to save world to: {filename}")
    try:
        # Ensure the directory exists only if filename includes a path
        dir_name = os.path.dirname(filename)
        if dir_name: # Only call makedirs if dir_name is not empty
            os.makedirs(dir_name, exist_ok=True)
            print(f"Ensured directory exists: {dir_name}")
        else:
            print("Saving to current directory, no need to create path.")

        world_data = {
            "seed": config.SEED,
            "player_pos": player_pos, # Save player position as a tuple
            "chunks": {},
            "storage": storage_system.get_all_storage_data() # Get storage data
        }

        with chunk_lock:
            print(f"Saving {len(loaded_chunks)} loaded chunks...")
            # Save all currently loaded chunks. Consider saving only modified ones later for optimization.
            for (cx, cy), chunk_data in loaded_chunks.items():
                chunk_key = f"{cx},{cy}" # Use string key for JSON
                # Convert numpy array to list for JSON serialization
                world_data["chunks"][chunk_key] = chunk_data.tolist()
            print(f"Finished preparing {len(world_data['chunks'])} chunks for saving.")

        # Write the data to the file
        with open(filename, 'w') as f:
            json.dump(world_data, f, indent=2) # Use indent for readability

        print(f"World saved successfully to {filename}")

    except Exception as e:
        print(f"Error saving world: {e}")
        traceback.print_exc() # Print detailed traceback

def load_world_from_file(filename, storage_system):
    """Loads the world state from a file."""
    print(f"Attempting to load world from: {filename}")
    if not os.path.exists(filename):
        print(f"Save file not found: {filename}")
        return False, (0, 0) # Return failure and default position

    try:
        with open(filename, 'r') as f:
            world_data = json.load(f)

        # Load seed
        loaded_seed = world_data.get("seed", config.SEED) # Use default if not found
        config.SEED = loaded_seed # Update global config seed
        print(f"Loaded seed: {config.SEED}")

        # Load player position (handle old format for compatibility if needed)
        if "player_pos" in world_data:
            player_pos = tuple(world_data["player_pos"])
        elif "player_x" in world_data and "player_y" in world_data: # Backward compatibility
             player_pos = (world_data["player_x"], world_data["player_y"])
             print("Loaded player position using old format (player_x, player_y).")
        else:
             player_pos = (0, 0) # Default if not found
        print(f"Loaded player position: {player_pos}")


        # Load chunks
        loaded_chunk_count = 0
        chunks_to_load = world_data.get("chunks", {})
        print(f"Found {len(chunks_to_load)} chunks in save file.")

        with chunk_lock:
            loaded_chunks.clear() # Clear existing chunks before loading
            modified_chunks.clear()
            generating_chunks.clear() # Also clear generating set

            for chunk_key, chunk_list in chunks_to_load.items():
                try:
                    cx_str, cy_str = chunk_key.split(',')
                    cx, cy = int(cx_str), int(cy_str)

                    # --- Robustness Check ---
                    if not isinstance(chunk_list, list):
                        print(f"Warning: Chunk {chunk_key} data is not a list. Skipping.")
                        continue

                    try:
                        # Attempt to convert list to numpy array
                        chunk_array = np.array(chunk_list, dtype=np.int32)
                    except ValueError as ve:
                        print(f"Warning: Chunk {chunk_key} data could not be converted to array: {ve}. Skipping.")
                        continue

                    # Check shape AFTER conversion
                    expected_shape = (config.CHUNK_SIZE, config.CHUNK_SIZE)
                    if chunk_array.shape != expected_shape:
                         print(f"Warning: Chunk {chunk_key} has incorrect shape {chunk_array.shape}. Expected {expected_shape}. Skipping.")
                         continue
                    # --- End Robustness Check ---

                    loaded_chunks[(cx, cy)] = chunk_array
                    loaded_chunk_count += 1
                except Exception as e:
                    # Catch other potential errors during chunk loading (e.g., key parsing)
                    print(f"Error loading chunk {chunk_key}: {e}")
            print(f"Successfully loaded {loaded_chunk_count} valid chunks from file.")

        # Load storage system data
        storage_data = world_data.get("storage", {})
        storage_system.load_all_storage_data(storage_data)
        print(f"Loaded {len(storage_data)} storage units.")


        print(f"World loaded successfully from {filename}")
        return True, player_pos # Return success and player position

    except json.JSONDecodeError as json_err:
        print(f"Error decoding JSON from {filename}: {json_err}")
        print("Save file might be corrupted. Consider deleting it and starting fresh.")
        # Clear potentially corrupted state on load failure
        with chunk_lock:
            loaded_chunks.clear()
            modified_chunks.clear()
            generating_chunks.clear()
        return False, (0, 0) # Return failure

    except Exception as e:
        print(f"Error loading world: {e}")
        traceback.print_exc()
        # Clear potentially corrupted state on load failure
        with chunk_lock:
            loaded_chunks.clear()
            modified_chunks.clear()
            generating_chunks.clear()
        return False, (0, 0) # Return failure

def ensure_origin_chunk_exists():
    with chunk_lock:
        if (0, 0) not in loaded_chunks:
            print("Origin chunk (0,0) missing, generating...")
            origin_data = generate_chunk_data(0, 0, config.SEED)
            if origin_data is not None:
                loaded_chunks[(0, 0)] = origin_data
                modified_chunks.add((0, 0))
                print("Origin chunk (0,0) generated and added.")
            else:
                print("Error: Failed to generate data for origin chunk (0,0).")
                loaded_chunks[(0, 0)] = np.full((config.CHUNK_SIZE, config.CHUNK_SIZE), config.EMPTY, dtype=np.int32)

__all__ = [
    'get_chunk_coords', 'get_block_at', 'set_block_at', 'mark_chunk_modified',
    'generate_chunk_data',
    'start_chunk_workers', 'stop_chunk_workers',
    'ensure_chunks_around_point', 'unload_distant_chunks', 'get_active_chunks',
    'save_world_to_file', 'load_world_from_file', 'chunk_lock', 'generating_chunks',
    'ensure_origin_chunk_exists', 'chunk_generation_queue', 'loaded_chunks', 'modified_chunks'
]
