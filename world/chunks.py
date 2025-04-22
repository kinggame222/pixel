import numpy as np
import threading
import queue
import time
import json
import os
import traceback
import random # Import random
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

# Add a dict to hold user‐modified chunk data persistently
user_modified_chunks = {}

loaded_chunks = {}
modified_chunks = set()
chunk_generation_queue = queue.Queue()
chunk_worker_running = threading.Event()
chunk_lock = threading.RLock()
generating_chunks = set()
initial_save_chunks = {} # Store chunks loaded from save file initially

# --- Coordinate System Refactor ---
# All functions below now expect world BLOCK coordinates (integers), not pixel coordinates.

def get_chunk_coords(world_block_x, world_block_y):
    """Calculates the chunk coordinates containing the given world block coordinates."""
    chunk_x = world_block_x // config.CHUNK_SIZE
    chunk_y = world_block_y // config.CHUNK_SIZE
    return chunk_x, chunk_y

def get_block_coords_in_chunk(world_block_x, world_block_y):
    """Calculates the local (x, y) coordinates within a chunk for the given world block coordinates."""
    local_x = world_block_x % config.CHUNK_SIZE
    local_y = world_block_y % config.CHUNK_SIZE
    return local_x, local_y

def get_block_at(world_block_x, world_block_y):
    """Gets the block type at the given world block coordinates."""
    chunk_x, chunk_y = get_chunk_coords(world_block_x, world_block_y)
    local_x, local_y = get_block_coords_in_chunk(world_block_x, world_block_y)
    chunk_coord = (chunk_x, chunk_y)

    with chunk_lock:
        if chunk_coord in loaded_chunks:
            try:
                # Numpy array access is [row, column] -> [y, x]
                block_type = loaded_chunks[chunk_coord][local_y, local_x]
                return block_type
            except IndexError:
                 print(f"ERROR: Invalid local coordinates ({local_x}, {local_y}) calculated for chunk {chunk_coord} from world block ({world_block_x}, {world_block_y})")
                 return config.EMPTY # Or some error indicator
        else:
            # Chunk not loaded, treat as empty
            return config.EMPTY

def set_block_at(world_block_x, world_block_y, block_type):
    """Sets the block type at the given world block coordinates."""
    chunk_x, chunk_y = get_chunk_coords(world_block_x, world_block_y)
    local_x, local_y = get_block_coords_in_chunk(world_block_x, world_block_y)
    chunk_coord = (chunk_x, chunk_y)

    with chunk_lock:
        if chunk_coord in loaded_chunks:
            try:
                # Numpy array access is [row, column] -> [y, x]
                current_block = loaded_chunks[chunk_coord][local_y, local_x]
                if current_block != block_type:
                    # --- DETAILED DEBUG PRINT (Now uses block coords) ---
                    print(f"[DEBUG set_block_at] WorldBlock:({world_block_x},{world_block_y}) -> Chunk:{chunk_coord}, Local:({local_x},{local_y}), Old:{current_block}, New:{block_type}")
                    # --- END DEBUG PRINT ---
                    loaded_chunks[chunk_coord][local_y, local_x] = block_type
                    mark_chunk_modified(chunk_x, chunk_y) # mark_chunk_modified uses chunk coords, which is fine
                    return True
                else:
                    # Block is already the desired type
                    return False # Indicate no change was made
            except IndexError:
                print(f"ERROR: Invalid local coordinates ({local_x}, {local_y}) for chunk {chunk_coord} from world block ({world_block_x}, {world_block_y})")
                return False
        else:
            print(f"Warning: Attempted to set block in unloaded chunk: {chunk_coord} at world block ({world_block_x}, {world_block_y})")
            # Optionally, queue the chunk for loading/generation here if desired
            return False

def mark_chunk_modified(chunk_x, chunk_y):
    """Marks a chunk as modified and saves a copy."""
    with chunk_lock:
        coord = (chunk_x, chunk_y)
        if coord in loaded_chunks:
            modified_chunks.add(coord)
            # persist a copy of the modified chunk
            user_modified_chunks[coord] = loaded_chunks[coord].copy()

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
        chunk_data = generate_chunk_terrain_cpu(chunk_data, chunk_x, chunk_y, seed, get_chunk_seed=get_chunk_seed)
        invalid_blocks = np.isin(chunk_data, list(config.BLOCKS.keys()), invert=True)
        if np.any(invalid_blocks):
            print(f"Warning: CPU generation created invalid block IDs in chunk ({chunk_x}, {chunk_y}). Replacing with EMPTY.")
            chunk_data[invalid_blocks] = config.EMPTY
        return chunk_data
    except Exception as e:
        print(f"CPU generation failed for chunk ({chunk_x}, {chunk_y}): {e}")
        traceback.print_exc()
        return np.full((config.CHUNK_SIZE, config.CHUNK_SIZE), config.EMPTY, dtype=np.int32)

# --- Chunk Seed Generation ---
def get_chunk_seed(chunk_x, chunk_y, world_seed):
    """Generates a unique, deterministic seed for a given chunk."""
    # Combine world seed and chunk coordinates in a stable way
    # Using large prime numbers can help distribute seeds better
    seed_str = f"{world_seed}-{chunk_x * 73856093}-{chunk_y * 19349663}"
    # Hash the string to get an integer seed
    return hash(seed_str)

def generate_chunk_worker():
    while chunk_worker_running.is_set():
        try:
            chunk_x, chunk_y, seed = chunk_generation_queue.get(timeout=0.1)
            coord = (chunk_x, chunk_y)
            should_gen = False
            with chunk_lock:
                if coord not in loaded_chunks and coord not in generating_chunks:
                    generating_chunks.add(coord)
                    should_gen = True

            if should_gen:
                # Prefer user modifications over save or fresh generation
                if coord in user_modified_chunks:
                    new_chunk = user_modified_chunks[coord]
                elif coord in initial_save_chunks:
                    new_chunk = initial_save_chunks[coord]
                else:
                    new_chunk = generate_chunk_data(chunk_x, chunk_y, seed)

                with chunk_lock:
                    # only load if still not present
                    if coord not in loaded_chunks:
                        loaded_chunks[coord] = new_chunk
                    generating_chunks.discard(coord)
                chunk_generation_queue.task_done()
            else:
                chunk_generation_queue.task_done()
        except queue.Empty:
            time.sleep(0.1)
        except Exception as e:
            print(f"Error in chunk worker: {e}")
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

    # Drain pending tasks to avoid deadlock on queue.join()
    pending = chunk_generation_queue.qsize()
    if pending > 0:
        print(f"Cancelling {pending} pending chunk tasks...")
        while not chunk_generation_queue.empty():
            try:
                chunk_generation_queue.get_nowait()
                chunk_generation_queue.task_done()
            except queue.Empty:
                break

    for worker in workers:
        worker.join(timeout=1.0)
        if worker.is_alive():
            print(f"Warning: Worker {worker.name} did not stop gracefully.")
    print("Chunk workers stopped.")

def ensure_chunks_around_point(pixel_x, pixel_y, radius_chunks):
    """Ensures chunks around a central PIXEL coordinate are loaded or queued."""
    # Convert center pixel coordinates to center chunk coordinates
    center_chunk_x = int(pixel_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(pixel_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    chunks_to_queue = []
    with chunk_lock:
        loaded_coords = set(loaded_chunks.keys())
        generating_coords = set(generating_chunks)

        # Iterate through the square radius of chunks
        for dy in range(-radius_chunks, radius_chunks + 1):
            for dx in range(-radius_chunks, radius_chunks + 1):
                cx, cy = center_chunk_x + dx, center_chunk_y + dy
                # Check if the chunk is neither loaded nor currently being generated
                if (cx, cy) not in loaded_coords and (cx, cy) not in generating_coords:
                    chunks_to_queue.append((cx, cy))

    # Sort chunks to load by distance from the center (optional, but good for perceived performance)
    chunks_to_queue.sort(key=lambda coords: abs(coords[0] - center_chunk_x) + abs(coords[1] - center_chunk_y))

    # Add the necessary chunks to the generation queue
    queued_count = 0
    for cx, cy in chunks_to_queue:
        # Add chunk coordinates and the current seed to the queue
        chunk_generation_queue.put((cx, cy, config.SEED))
        queued_count += 1

def unload_distant_chunks(pixel_x, pixel_y, unload_distance_chunks, rendered_chunk_cache):
    """Unloads chunks that are farther than unload_distance_chunks from the central PIXEL coordinate."""

    # Convert center pixel coordinates to center chunk coordinates
    center_chunk_x = int(pixel_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(pixel_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    chunks_to_unload = []
    with chunk_lock:
        current_chunk_keys = list(loaded_chunks.keys())
        for chunk_x, chunk_y in current_chunk_keys:
            # Calculate distance in chunks (Manhattan distance is sufficient)
            dist_x = abs(chunk_x - center_chunk_x)
            dist_y = abs(chunk_y - center_chunk_y)
            # Check if the chunk is outside the unload distance
            if max(dist_x, dist_y) > unload_distance_chunks:
                # Basic protection: Never unload the origin chunk (0,0)
                if chunk_x == 0 and chunk_y == 0:
                    continue
                chunks_to_unload.append((chunk_x, chunk_y))

    unloaded_count = 0
    if chunks_to_unload:
        with chunk_lock:
            for chunk_pos in chunks_to_unload:
                if chunk_pos in loaded_chunks:
                    del loaded_chunks[chunk_pos]
                    modified_chunks.discard(chunk_pos) # Remove from modified set as well
                    rendered_chunk_cache.pop(chunk_pos, None) # Clear the render cache for the unloaded chunk
                    unloaded_count += 1

def get_active_chunks(pixel_x, pixel_y, screen_width, screen_height, view_multiplier, max_chunks):
    """Gets a list of loaded chunk coordinates visible or nearly visible on screen."""
    # Convert center pixel coordinates to center chunk coordinates
    center_chunk_x = int(pixel_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    center_chunk_y = int(pixel_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    # Calculate the view distance in pixels from the center
    view_dist_pixels_x = (screen_width * view_multiplier) / 2
    view_dist_pixels_y = (screen_height * view_multiplier) / 2
    # Calculate the span in chunks needed to cover the view distance (+2 for buffer)
    chunk_span_x = int(view_dist_pixels_x // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2
    chunk_span_y = int(view_dist_pixels_y // (config.CHUNK_SIZE * config.PIXEL_SIZE)) + 2

    active_chunks_list = []
    with chunk_lock:
        # Iterate through the calculated span around the center chunk
        for dx in range(-chunk_span_x, chunk_span_x + 1):
            for dy in range(-chunk_span_y, chunk_span_y + 1):
                chunk_coords = (center_chunk_x + dx, center_chunk_y + dy)
                # Add the chunk coordinates if the chunk is currently loaded
                if chunk_coords in loaded_chunks:
                    active_chunks_list.append(chunk_coords)

    # Limit the number of active chunks if necessary
    if len(active_chunks_list) > max_chunks:
        # Sort by distance from the center chunk (Manhattan distance)
        active_chunks_list.sort(key=lambda pos: max(abs(pos[0] - center_chunk_x), abs(pos[1] - center_chunk_y)))
        # Keep only the closest 'max_chunks' chunks
        active_chunks_list = active_chunks_list[:max_chunks]

    return active_chunks_list

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.int32):
            return int(obj)
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)

def save_world_to_file(filename, storage_system, player_pos, conveyor_system=None, extractor_system=None, multi_block_system=None, auto_miner_system=None):
    """Saves the current world state to a file."""
    print(f"Starting world save to {filename}...")
    start_time = time.time()
    data_to_save = {
        "seed": config.SEED,
        "player_pos": player_pos,
        "chunks": {},
        "storage": storage_system.get_save_data(),
        "conveyors": conveyor_system.get_save_data() if conveyor_system else {},
        "extractors": extractor_system.get_save_data() if extractor_system else {},
        "multi_blocks": multi_block_system.get_save_data() if multi_block_system else {},
        "auto_miners": auto_miner_system.get_save_data() if auto_miner_system else {}
    }

    chunks_saved_count = 0
    with chunk_lock:
        for chunk_coord in list(loaded_chunks.keys()):
            if chunk_coord in loaded_chunks:
                chunk_key = f"{chunk_coord[0]},{chunk_coord[1]}"
                data_to_save["chunks"][chunk_key] = loaded_chunks[chunk_coord]
                chunks_saved_count += 1

    try:
        with open(filename, 'w') as f:
            json.dump(data_to_save, f, cls=NumpyEncoder, indent=2)
        end_time = time.time()
        print(f"World saved successfully to {filename} ({chunks_saved_count} chunks) in {end_time - start_time:.2f} seconds.")
    except Exception as e:
        print(f"Error saving world to {filename}: {e}")
        traceback.print_exc()

def load_world_from_file(filename, storage_system, rendered_chunk_cache, conveyor_system=None, extractor_system=None, multi_block_system=None, auto_miner_system=None):
    """Loads world state from a file."""
    print(f"Attempting to load world from {filename}...")
    start_time = time.time()
    try:
        with open(filename, 'r') as f:
            loaded_data = json.load(f)

        with chunk_lock:
            # Clear current world state
            loaded_chunks.clear()
            modified_chunks.clear()
            generating_chunks.clear()
            initial_save_chunks.clear() # Clear initial save cache
            rendered_chunk_cache.clear() # Clear render cache on load
            storage_system.storages.clear()
            if conveyor_system:
                conveyor_system.conveyors.clear()
                conveyor_system.items_on_conveyors.clear()
            if extractor_system:
                extractor_system.extractors.clear()
            if multi_block_system:
                multi_block_system.multi_block_origins.clear()
                multi_block_system.multi_block_structures.clear()
            if auto_miner_system:
                auto_miner_system.miners.clear()

            loaded_seed = loaded_data.get("seed", int(time.time()))
            config.SEED = loaded_seed
            print(f"Loaded world seed: {config.SEED}")

            loaded_chunk_count = 0
            # Load chunks into BOTH loaded_chunks and initial_save_chunks
            for key, chunk_data_list in loaded_data.get("chunks", {}).items():
                try:
                    x_str, y_str = key.split(',')
                    chunk_coord = (int(x_str), int(y_str))
                    chunk_np_data = np.array(chunk_data_list, dtype=config.CHUNK_DATA_TYPE)
                    loaded_chunks[chunk_coord] = chunk_np_data
                    initial_save_chunks[chunk_coord] = chunk_np_data # Store in initial cache
                    loaded_chunk_count += 1
                except Exception as e:
                    print(f"Error loading chunk data for key {key}: {e}")

            storage_system.load_save_data(loaded_data.get("storage", {}))
            if conveyor_system:
                conveyor_system.load_save_data(loaded_data.get("conveyors", {}))
            if extractor_system:
                extractor_system.load_save_data(loaded_data.get("extractors", {}))
            if multi_block_system:
                multi_block_system.load_save_data(loaded_data.get("multi_blocks", {}))
            if auto_miner_system:
                auto_miner_system.load_save_data(loaded_data.get("auto_miners", {}))

            player_pos = loaded_data.get("player_pos", (0, 0))

            end_time = time.time()
            print(f"World loaded successfully from {filename} ({loaded_chunk_count} chunks) in {end_time - start_time:.2f} seconds.")
            return True, player_pos

    except FileNotFoundError:
        print(f"Save file {filename} not found.")
        with chunk_lock: initial_save_chunks.clear() # Clear cache if file not found
        return False, (0, 0)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {filename}: {e}")
        with chunk_lock: initial_save_chunks.clear() # Clear cache on decode error
        return False, (0, 0)
    except Exception as e:
        print(f"An unexpected error occurred loading world from {filename}: {e}")
        traceback.print_exc()
        with chunk_lock: initial_save_chunks.clear() # Clear cache on other errors
        return False, (0, 0)

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
    'ensure_origin_chunk_exists', 'chunk_generation_queue', 'loaded_chunks', 'modified_chunks',
    'initial_save_chunks'
]
