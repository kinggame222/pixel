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

def get_block_at(block_world_x, block_world_y):
    chunk_x = int(block_world_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    chunk_y = int(block_world_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    with chunk_lock:
        chunk = loaded_chunks.get((chunk_x, chunk_y))
        if chunk is None:
            return config.EMPTY

        local_x = int(block_world_x // config.PIXEL_SIZE) % config.CHUNK_SIZE
        local_y = int(block_world_y // config.PIXEL_SIZE) % config.CHUNK_SIZE

        if 0 <= local_y < config.CHUNK_SIZE and 0 <= local_x < config.CHUNK_SIZE:
            return chunk[local_y, local_x]
        else:
            print(f"Warning: Calculated local coords ({local_x}, {local_y}) out of bounds for chunk ({chunk_x}, {chunk_y}). World coords: ({block_world_x}, {block_world_y})")
            return config.EMPTY

def set_block_at(block_world_x, block_world_y, block_type):
    chunk_x = int(block_world_x // (config.CHUNK_SIZE * config.PIXEL_SIZE))
    chunk_y = int(block_world_y // (config.CHUNK_SIZE * config.PIXEL_SIZE))

    with chunk_lock:
        chunk = loaded_chunks.get((chunk_x, chunk_y))
        if chunk is None:
            print(f"Warning: Attempted to set block in non-loaded chunk ({chunk_x}, {chunk_y})")
            return False

        local_x = int(block_world_x // config.PIXEL_SIZE) % config.CHUNK_SIZE
        local_y = int(block_world_y // config.PIXEL_SIZE) % config.CHUNK_SIZE

        if not (0 <= local_y < config.CHUNK_SIZE and 0 <= local_x < config.CHUNK_SIZE):
            print(f"Warning: Attempted to set block out of bounds at local coords ({local_x}, {local_y}) in chunk ({chunk_x}, {chunk_y}). World coords: ({block_world_x}, {block_world_y})")
            return False

        if chunk[local_y, local_x] != block_type:
            chunk[local_y, local_x] = block_type
            modified_chunks.add((chunk_x, chunk_y))
            return True
        return False

def mark_chunk_modified(chunk_x, chunk_y):
    with chunk_lock:
        if (chunk_x, chunk_y) in loaded_chunks:
            modified_chunks.add((chunk_x, chunk_y))

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

def save_world_to_file(filename, storage_system=None, player_pos=(0,0)):
    print(f"Saving world to {filename}...")
    saved_count = 0
    world_data = {}

    chunk_data_to_save = {}
    with chunk_lock:
        chunks_to_process = list(modified_chunks)

        print(f"Found {len(chunks_to_process)} modified chunks to save.")

        for chunk_pos in chunks_to_process:
            if chunk_pos in loaded_chunks:
                chunk = loaded_chunks[chunk_pos]
                chunk_data_to_save[f"{chunk_pos[0]},{chunk_pos[1]}"] = chunk.tolist()
                saved_count += 1

    world_data = {
        "seed": config.SEED,
        "player_x": player_pos[0],
        "player_y": player_pos[1],
        "chunks": chunk_data_to_save,
    }

    try:
        dir_name = os.path.dirname(filename)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
            print(f"Ensured directory exists: {dir_name}")
        else:
            print("Saving to current directory, no need to create path.")

        with open(filename, "w") as f:
            json.dump(world_data, f, indent=2)

        print(f"World saved successfully ({saved_count} chunks) to {filename}")
        with chunk_lock:
            modified_chunks.clear()

    except Exception as e:
        print(f"Error saving world: {e}")
        traceback.print_exc()

def load_world_from_file(filename, storage_system=None):
    print(f"Loading world from {filename}...")
    if not os.path.exists(filename):
        print(f"Save file {filename} not found. Cannot load.")
        return False, (0, 0)

    try:
        with open(filename, 'r') as f:
            data = json.load(f)

        loaded_seed = data.get("seed", config.SEED)
        config.SEED = loaded_seed
        print(f"Loaded and set world seed: {config.SEED}")

        player_x = data.get("player_x", 0)
        player_y = data.get("player_y", 0)
        player_pos = (player_x, player_y)
        print(f"Loaded player position: {player_pos}")

        loaded_count = 0
        with chunk_lock:
            loaded_chunks.clear()
            modified_chunks.clear()
            generating_chunks.clear()

            chunk_data = data.get('chunks', {})
            print(f"Found {len(chunk_data)} chunks in save file.")

            for coord_str, chunk_list in chunk_data.items():
                try:
                    x_str, y_str = coord_str.split(',')
                    chunk_x, chunk_y = int(x_str), int(y_str)

                    chunk_array = np.array(chunk_list, dtype=np.int32)

                    if chunk_array.shape != (config.CHUNK_SIZE, config.CHUNK_SIZE):
                        print(f"Warning: Chunk {coord_str} has incorrect shape {chunk_array.shape}. Skipping.")
                        continue

                    loaded_chunks[(chunk_x, chunk_y)] = chunk_array
                    loaded_count += 1

                except Exception as e:
                    print(f"Error loading chunk data for '{coord_str}': {e}")
                    continue

        print(f"World loaded successfully with {loaded_count} chunks.")
        ensure_origin_chunk_exists()
        return True, player_pos

    except FileNotFoundError:
        print(f"Save file {filename} not found.")
        return False, (0, 0)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from save file {filename}.")
        return False, (0, 0)
    except Exception as e:
        print(f"An unexpected error occurred loading world: {e}")
        traceback.print_exc()
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
    'ensure_origin_chunk_exists', 'chunk_generation_queue', 'loaded_chunks', 'modified_chunks'
]
