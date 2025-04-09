import pygame
import numpy as np
import cProfile
import time
import sys  # Pour quitter proprement
import random  # Pour la génération procédurale
import json  # Import the json module
from threading import Thread
from queue import Queue, Empty  # Import Empty directly for clarity
import threading
import os  # For file operations

# Importe les modules locaux
import config
import simulation
import map_generation  # Import the map generation module

# --- Chunk Management ---
CHUNK_SIZE = 16  # Size of each chunk (in blocks)

# --- Performance Settings ---
ENABLE_CHUNK_CACHE = True  # Enable chunk caching for performance
MAX_ACTIVE_CHUNKS = 200  # Maximum active chunks to render
PERFORMANCE_MONITOR = True  # Show performance stats 
VIEW_DISTANCE_MULTIPLIER = 2.0  # Multiplier to increase view distance
CHUNK_LOAD_RADIUS = 5  # Radius of chunkds to keep loaded around player

# --- Infinite World Settings ---
ENABLE_INFINITE_WORLD = True  # Enable infinite world generation
CHUNK_GEN_THREAD_COUNT = 2  # Number of threads for chunk generation
CHUNK_UNLOAD_DISTANCE = 5  # Distance in chunks to unload chunks

# --- Chunk Cache ---
chunk_cache = {}  # Dictionary to store rendered chunk surfaces
modified_chunks = set()  # Set to track which chunks need to be re-rendered
loaded_chunks = {}  # Dictionary to store loaded chunk data

# Add a thread-safe queue for chunk generation requests
chunk_gen_queue = Queue()
chunk_gen_active = True  # Flag to control chunk generation threads

SAVE_FILE = "world.json"  # Path to the save file

def save_map_to_json():
    """Saves the current map (loaded chunks) to a JSON file."""
    world_data = []
    for (chunk_x, chunk_y), chunk in loaded_chunks.items():
        chunk_data = {
            "chunk_x": chunk_x,
            "chunk_y": chunk_y,
            "blocks": chunk.tolist()  # Convert numpy array to a list for JSON serialization
        }
        world_data.append(chunk_data)
    
    with open(SAVE_FILE, "w") as f:
        json.dump(world_data, f, indent=4)
    print(f"World saved to {SAVE_FILE}")

def load_map_from_json():
    """Loads the map (chunks) from a JSON file."""
    if not os.path.exists(SAVE_FILE):
        print(f"No save file found at {SAVE_FILE}")
        return
    
    with open(SAVE_FILE, "r") as f:
        world_data = json.load(f)
    
    for chunk_data in world_data:
        chunk_x = chunk_data["chunk_x"]
        chunk_y = chunk_data["chunk_y"]
        blocks = np.array(chunk_data["blocks"], dtype=np.uint8)  # Convert list back to numpy array
        loaded_chunks[(chunk_x, chunk_y)] = blocks
    print(f"World loaded from {SAVE_FILE}")

def regenerate_map():
    """Clears the current map and regenerates it."""
    global loaded_chunks, chunk_cache, modified_chunks
    loaded_chunks.clear()  # Clear all loaded chunks
    chunk_cache.clear()  # Clear the chunk rendering cache
    modified_chunks.clear()  # Clear the modified chunks set
    print("Map cleared. Regenerating...")
    
    # Regenerate chunks around the player
    player_chunk_x, player_chunk_y = get_chunk_coords(int(player_x // config.PIXEL_SIZE),
                                                      int(player_y // config.PIXEL_SIZE))
    for dx in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
        for dy in range(-CHUNK_LOAD_RADIUS, CHUNK_LOAD_RADIUS + 1):
            generate_chunk(player_chunk_x + dx, player_chunk_y + dy)
    print("Map regenerated.")

# --- Initialisation Pygame ---
pygame.init()
# Use default screen dimensions for the initial window size
screen_width = 800  # Default screen width in pixels
screen_height = 600  # Default screen height in pixels
screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)  # Ajout de pygame.RESIZABLE
pygame.display.set_caption(config.WINDOW_TITLE)
fps_font = pygame.font.SysFont("Consolas", 18)
clock = pygame.time.Clock()

def get_chunk_coords(x, y):
    """Returns the chunk coordinates for a given block coordinate."""
    # Handle negative coordinates properly
    chunk_x = x // CHUNK_SIZE
    if x < 0 and x % CHUNK_SIZE != 0:
        chunk_x -= 1
    chunk_y = y // CHUNK_SIZE
    if y < 0 and y % CHUNK_SIZE != 0:
        chunk_y -= 1
    return chunk_x, chunk_y

def get_local_block_coords(x, y):
    """Returns the local coordinates within a chunk for a given block coordinate."""
    local_x = x % CHUNK_SIZE
    if local_x < 0:
        local_x += CHUNK_SIZE
    local_y = y % CHUNK_SIZE
    if local_y < 0:
        local_y += CHUNK_SIZE
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
        generate_chunk(chunk_x, chunk_y)
    
    loaded_chunks[chunk_key][local_y, local_x] = block_type
    mark_chunk_modified(chunk_x, chunk_y)

def generate_chunk(chunk_x, chunk_y):
    """Generates a new chunk at the given chunk coordinates."""
    chunk = np.full((CHUNK_SIZE, CHUNK_SIZE), config.EMPTY, dtype=np.uint8)
    
    # Generate terrain using map_generation module
    map_generation.generate_chunk(chunk, chunk_x, chunk_y, SEED)
    
    # Store the chunk in loaded_chunks
    loaded_chunks[(chunk_x, chunk_y)] = chunk
    return chunk

def chunk_generation_worker():
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
            generate_chunk(chunk_x, chunk_y)
            
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

def unload_distant_chunks(player_x, player_y):
    """Unloads chunks that are too far from the player."""
    player_chunk_x, player_chunk_y = get_chunk_coords(int(player_x // config.PIXEL_SIZE), 
                                                     int(player_y // config.PIXEL_SIZE))
    
    # Find chunks to unload
    chunks_to_unload = []
    for chunk_key in loaded_chunks.keys():
        chunk_x, chunk_y = chunk_key
        distance = max(abs(chunk_x - player_chunk_x), abs(chunk_y - player_chunk_y))
        if distance > CHUNK_UNLOAD_DISTANCE:
            chunks_to_unload.append(chunk_key)
    
    # Unload the chunks
    for chunk_key in chunks_to_unload:
        # Save modified chunks (if we had persistence)
        if chunk_key in modified_chunks:
            # TODO: Save chunk to disk here if implementing persistence
            modified_chunks.remove(chunk_key)
        
        # Remove from loaded chunks
        del loaded_chunks[chunk_key]
        
        # Remove from render cache
        if chunk_key in chunk_cache:
            del chunk_cache[chunk_key]

def get_active_chunks(player_x, player_y, screen_width, screen_height):
    """Returns a set of active chunk coordinates based on the player's position and screen size."""
    # Increase the view distance using the multiplier
    expanded_width = screen_width * VIEW_DISTANCE_MULTIPLIER
    expanded_height = screen_height * VIEW_DISTANCE_MULTIPLIER
    
    start_x = int((player_x - expanded_width // 2) // (config.PIXEL_SIZE * CHUNK_SIZE))
    start_y = int((player_y - expanded_height // 2) // (config.PIXEL_SIZE * CHUNK_SIZE))
    end_x = int((player_x + expanded_width // 2) // (config.PIXEL_SIZE * CHUNK_SIZE))
    end_y = int((player_y + expanded_height // 2) // (config.PIXEL_SIZE * CHUNK_SIZE))

    active_chunks = set()
    for x in range(start_x - 1, end_x + 2):
        for y in range(start_y - 1, end_y + 2):
            active_chunks.add((x, y))
    
    # Limit the number of active chunks for performance
    if len(active_chunks) > MAX_ACTIVE_CHUNKS:
        # Sort chunks by distance from player
        player_chunk_x = player_x // (config.PIXEL_SIZE * CHUNK_SIZE)
        player_chunk_y = player_y // (config.PIXEL_SIZE * CHUNK_SIZE)
        
        # Get player movement direction for prioritizing chunks
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
        active_chunks = set([c[0] for c in chunks_with_distance[:MAX_ACTIVE_CHUNKS]])
    
    return active_chunks

# --- Debug Mode ---
DEBUG_MODE = True  # Set to True to enable debug mode

# --- Load Block Data from JSON ---
try:
    with open("blocks.json", "r") as f:
        BLOCK_DATA = json.load(f)
except FileNotFoundError:
    print("Error: blocks.json not found!")
    sys.exit()

# Create a dictionary mapping block IDs to block data
BLOCKS = {block["id"]: block for block in BLOCK_DATA}

# Create a dictionary to cache block colors
BLOCK_COLORS = {block_id: BLOCKS[block_id]["color"] for block_id in BLOCKS}

# --- Cache Block Surfaces ---
block_surfaces = {}
for block_id, block in BLOCKS.items():
    if block_id != config.EMPTY:
        surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE))
        surface.fill(block["color"])
        block_surfaces[block_id] = surface

# --- Initialisation de l'état du jeu ---

# Seed pour la génération procédurale
SEED = 1  # Change this to generate different maps
random.seed(SEED)
np.random.seed(SEED)

# Adjust the player's spawn position to ensure it starts above the ground
def find_spawn_position():
    """Finds a safe spawn position for the player above the ground."""
    spawn_chunk_x, spawn_chunk_y = 0, 0  # Start at the origin chunk
    if (spawn_chunk_x, spawn_chunk_y) not in loaded_chunks:
        generate_chunk(spawn_chunk_x, spawn_chunk_y)
    
    chunk = loaded_chunks[(spawn_chunk_x, spawn_chunk_y)]
    for y in range(CHUNK_SIZE):
        for x in range(CHUNK_SIZE):
            if chunk[y, x] == config.EMPTY:
                return x * config.PIXEL_SIZE, y * config.PIXEL_SIZE
    return 0, 0  # Default to (0, 0) if no empty space is found

# Set the player's initial position
player_x, player_y = find_spawn_position()

# Position initiale de la caméra (centrée sur le joueur)
camera_x = player_x - screen_width // 2
camera_y = player_y - screen_height // 2

# Variables de simulation
falling_animations = []  # Liste des animations en cours
active_columns = set()
animating_sources = set()  # Ensemble des sources (r,c) en animation
next_active_columns = set()  # Initialize next_active_columns

# --- Nouvelle variable pour la gravité ---
player_velocity_y = 0.0  # Vitesse verticale du joueur
GRAVITY = 0  # Gravité, pixels par seconde carrée
JUMP_SPEED = 0  # Vitesse initiale du saut
JETPACK_SPEED = 200  # Vitesse du jetpack

# --- Fonction d'aide pour contraindre le joueur ---
def clamp_player_position(px, py):
    """Remove clamping logic since the world is infinite."""
    return px, py

# --- Collision Detection ---
PLAYER_COLLISION_ENABLED = True

def is_solid_block(x, y):
    """Checks if the block at the given coordinates is solid."""
    block_type = get_block_at(x, y)
    if block_type in BLOCKS:
        return BLOCKS[block_type]["solid"]
    return False

def check_collision(px, py, move_x, move_y):
    """Checks for collisions with solid blocks."""
    if not PLAYER_COLLISION_ENABLED:
        return False  # Skip collision checks if collisions are disabled

    player_width = config.PLAYER_WIDTH
    player_height = config.PLAYER_HEIGHT

    # Calculate the player's bounding box
    player_rect = pygame.Rect(px, py, player_width, player_height)

    # Calculate the potential new position
    new_player_rect = player_rect.move(move_x, move_y)

    # Check for collisions with solid blocks
    for x in range(new_player_rect.left // config.PIXEL_SIZE, (new_player_rect.right // config.PIXEL_SIZE) + 1):
        for y in range(new_player_rect.top // config.PIXEL_SIZE, (new_player_rect.bottom // config.PIXEL_SIZE) + 1):
            if is_solid_block(x, y):
                block_rect = pygame.Rect(x * config.PIXEL_SIZE, y * config.PIXEL_SIZE, config.PIXEL_SIZE, config.PIXEL_SIZE)
                if new_player_rect.colliderect(block_rect):
                    return True  # Collision detected

    return False  # No collision detected

# --- Inventory System ---
HOTBAR_SIZE = 9  # Number of slots in the hotbar
hotbar = [None] * HOTBAR_SIZE  # List to store the hotbar items (block_type, count)
inventory_font = pygame.font.SysFont("Consolas", 14)
selected_slot = 0  # Initially selected hotbar slot

def add_to_inventory(block_type):
    # Check if the block_type is already in the hotbar
    for i in range(HOTBAR_SIZE):
        if hotbar[i] is not None and hotbar[i][0] == block_type:
            hotbar[i] = (block_type, hotbar[i][1] + 1)
            return True

    # If the block_type is not in the hotbar, add it to the first empty slot
    for i in range(HOTBAR_SIZE):
        if hotbar[i] is None:
            hotbar[i] = (block_type, 1)
            return True

    # If the hotbar is full, return False
    return False

def remove_from_inventory(slot):
    if 0 <= slot < HOTBAR_SIZE and hotbar[slot] is not None:
        block_type, count = hotbar[slot]
        if count > 1:
            hotbar[slot] = (block_type, count - 1)
        else:
            hotbar[slot] = None
        return block_type
    return None

def draw_inventory(screen):
    hotbar_x = screen_width // 2 - (HOTBAR_SIZE * 25)  # Centered hotbar
    hotbar_y = screen_height - 50  # Near the bottom of the screen
    slot_size = 50
    slot_spacing = 5

    for i in range(HOTBAR_SIZE):
        x = hotbar_x + i * (slot_size + slot_spacing)
        y = hotbar_y

        # Draw slot background
        if i == selected_slot:
            pygame.draw.rect(screen, (150, 150, 150), (x, y, slot_size, slot_size))  # Highlight selected slot
        else:
            pygame.draw.rect(screen, (50, 50, 50), (x, y, slot_size, slot_size))

        # Draw item in slot
        if hotbar[i] is not None:
            block_type, count = hotbar[i]

            if block_type in BLOCKS:
                block_color = BLOCKS[block_type]["color"]
                pygame.draw.rect(screen, block_color, (x + 5, y + 5, slot_size - 10, slot_size - 10))  # Draw block color
                item_name = BLOCKS[block_type]["name"]
            else:
                item_name = "Unknown"

            # Draw count at the bottom
            count_surface = inventory_font.render(str(count), True, (255, 255, 255))
            count_rect = count_surface.get_rect(center=(x + slot_size // 2, y + slot_size - 10))  # Position at the bottom
            screen.blit(count_surface, count_rect)

# --- Rendering Functions ---
def render_chunk(chunk_x, chunk_y, camera_x, camera_y, mining_animation, block_surfaces):
    """Renders a chunk of the grid to a surface."""
    # Check if the chunk is in cache and has not been modified
    cache_key = (chunk_x, chunk_y)
    if ENABLE_CHUNK_CACHE and cache_key in chunk_cache and cache_key not in modified_chunks:
        return chunk_cache[cache_key]
    
    # Skip rendering if the chunk is not loaded
    if (chunk_x, chunk_y) not in loaded_chunks:
        # Return an empty surface
        surface = pygame.Surface((CHUNK_SIZE * config.PIXEL_SIZE, CHUNK_SIZE * config.PIXEL_SIZE))
        surface.fill((0, 0, 0))  # Black background
        return surface
    
    chunk = loaded_chunks[(chunk_x, chunk_y)]
    
    surface = pygame.Surface((CHUNK_SIZE * config.PIXEL_SIZE, CHUNK_SIZE * config.PIXEL_SIZE))
    surface.fill((0, 0, 0))  # Black background
    
    # Optimization: Draw blocks in batches by type
    blocks_by_type = {}
    
    for y in range(CHUNK_SIZE):
        for x in range(CHUNK_SIZE):
            block_type = chunk[y, x]
            
            if block_type == config.EMPTY:
                continue
            
            # Convert chunk-local coordinates to world coordinates
            block_x = x * config.PIXEL_SIZE
            block_y = y * config.PIXEL_SIZE
            
            # Group blocks by type for batch rendering
            if (y, x) in mining_animation:
                # Mining animation blocks need individual rendering
                animation_progress = mining_animation[(y, x)]
                red_intensity = int(255 * animation_progress)
                animated_surface = pygame.Surface((config.PIXEL_SIZE, config.PIXEL_SIZE))
                block_color = BLOCKS[block_type]["color"]
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
        else:
            if DEBUG_MODE:
                print(f"Error: No surface found for block type {block_type}")
    
    # Cache the rendered chunk
    if ENABLE_CHUNK_CACHE:
        chunk_cache[cache_key] = surface
        if cache_key in modified_chunks:
            modified_chunks.remove(cache_key)
    
    return surface

def mark_chunk_modified(chunk_x, chunk_y):
    """Mark a chunk as modified so it will be re-rendered."""
    modified_chunks.add((chunk_x, chunk_y))

# --- Performance Monitor ---
def draw_performance_stats(screen, dt, active_chunk_count):
    """Draw performance statistics on screen."""
    if not PERFORMANCE_MONITOR:
        return
        
    fps = int(1.0 / dt) if dt > 0 else 0
    text_color = (255, 255, 0)  # Yellow
    
    fps_text = f"FPS: {fps}"
    chunks_text = f"Chunks: {active_chunk_count}/{MAX_ACTIVE_CHUNKS}"
    memory_text = f"Cache: {len(chunk_cache)} chunks"
    
    fps_surface = fps_font.render(fps_text, True, text_color)
    chunks_surface = fps_font.render(chunks_text, True, text_color)
    memory_surface = fps_font.render(memory_text, True, text_color)
    
    screen.blit(fps_surface, (10, 10))
    screen.blit(chunks_surface, (10, 30))
    screen.blit(memory_surface, (10, 50))

# Start chunk generation worker threads
chunk_gen_threads = []
for i in range(CHUNK_GEN_THREAD_COUNT):
    thread = threading.Thread(target=chunk_generation_worker, daemon=True)
    thread.start()
    chunk_gen_threads.append(thread)

# --- Boucle Principale du Jeu ---
if __name__ == '__main__':
    running = True
    profiler = cProfile.Profile()
    profiler.enable()
    last_time = time.time()

    # Load the map if a save file exists
    load_map_from_json()

    laser_active = False
    laser_points = []  # List of points for the laser beam
    mining_progress = {}  # Dictionary to track mining progress for each block
    mining_animation = {}  # Dictionary to store mining animation progress
    COOL_DOWN_RATE = 0.1  # Rate at which the block cools down (per second)

    # Initialize with some chunks around the player
    player_chunk_x, player_chunk_y = get_chunk_coords(int(player_x // config.PIXEL_SIZE),
                                                      int(player_y // config.PIXEL_SIZE))
                                                      
    # Start with a small loaded area around the player
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            generate_chunk(player_chunk_x + dx, player_chunk_y + dy)

    while running:
        # --- Calcul du Delta Time et Temps Actuel ---
        current_time_precise = time.time()
        dt = current_time_precise - last_time
        if dt == 0: dt = 1 / config.FPS_CAP  # Evite division par zéro si frame trop rapide
        last_time = current_time_precise
        current_time_ms = pygame.time.get_ticks()

        # --- Gestion des Événements ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Save the map before quitting
                save_map_to_json()
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_o:  # Press 'O' to manually save the map
                    save_map_to_json()
                elif event.key == pygame.K_l:  # Press 'L' to manually load the map
                    load_map_from_json()
                elif event.key == pygame.K_r:  # Press 'R' to regenerate the map
                    regenerate_map()
                elif event.key == pygame.K_c:  # Press 'C' to toggle player collision
                    PLAYER_COLLISION_ENABLED = not PLAYER_COLLISION_ENABLED
                    print(f"Player collision {'enabled' if PLAYER_COLLISION_ENABLED else 'disabled'}.")
                elif event.key == pygame.VIDEORESIZE:  # Gestion du redimensionnement
                    screen_width, screen_height = event.size
                    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                    # Mise à jour de la caméra pour rester centrée sur le joueur
                    camera_x = player_x - screen_width // 2
                    camera_y = player_y - screen_height // 2
                elif event.key == pygame.K_1:  # Number keys to select hotbar slots
                    selected_slot = 0
                elif event.key == pygame.K_2:
                    selected_slot = 1
                elif event.key == pygame.K_3:
                    selected_slot = 2
                elif event.key == pygame.K_4:
                    selected_slot = 3
                elif event.key == pygame.K_5:
                    selected_slot = 4
                elif event.key == pygame.K_6:
                    selected_slot = 5
                elif event.key == pygame.K_7:
                    selected_slot = 6
                elif event.key == pygame.K_8:
                    selected_slot = 7
                elif event.key == pygame.K_9:
                    selected_slot = 8
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:  # Increase view distance
                    VIEW_DISTANCE_MULTIPLIER = min(3.0, VIEW_DISTANCE_MULTIPLIER + 0.5)
                    print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                elif event.key == pygame.K_MINUS:  # Decrease view distance
                    VIEW_DISTANCE_MULTIPLIER = max(1.0, VIEW_DISTANCE_MULTIPLIER - 0.5)
                    print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                elif event.key == pygame.K_i:  # Toggle debug mode with F12 key
                    DEBUG_MODE = not DEBUG_MODE
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # Right mouse button
                # Place block from selected slot
                mouse_x, mouse_y = pygame.mouse.get_pos()
                world_x = mouse_x + camera_x
                world_y = mouse_y + camera_y

                place_x = int(world_x // config.PIXEL_SIZE)
                place_y = int(world_y // config.PIXEL_SIZE)

                # Check if the position is valid for placing a block
                if get_block_at(place_x, place_y) == config.EMPTY:
                    # Get the block type from the selected slot
                    if 0 <= selected_slot < HOTBAR_SIZE and hotbar[selected_slot] is not None:
                        block_type, count = hotbar[selected_slot]
                        # Place the block
                        set_block_at(place_x, place_y, block_type)
                        # Remove the block from the inventory
                        remove_from_inventory(selected_slot)
                        # Mark the chunk as modified
                        chunk_x, chunk_y = get_chunk_coords(place_x, place_y)
                        mark_chunk_modified(chunk_x, chunk_y)

        # --- Mouse Button Pressed ---
        mouse_pressed = pygame.mouse.get_pressed()[0]  # Left mouse button

        # --- Laser Logic ---
        if mouse_pressed:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            world_x = mouse_x + camera_x
            world_y = mouse_y + camera_y

            # Calculate direction vector from player to mouse
            direction_x = world_x - player_x
            direction_y = world_y - player_y
            distance = np.sqrt(direction_x ** 2 + direction_y ** 2)
            if distance == 0: distance = 1  # Avoid division by zero

            # Normalize the direction vector
            direction_x /= distance
            direction_y /= distance

            # Laser range (in blocks)
            laser_range = 15
            laser_points = []

            # Dig along the laser direction
            for i in range(laser_range):
                dig_x = int((player_x + direction_x * i * config.PIXEL_SIZE) // config.PIXEL_SIZE)
                dig_y = int((player_y + direction_y * i * config.PIXEL_SIZE) // config.PIXEL_SIZE)

                # Check if dig position has a block
                block_type = get_block_at(dig_x, dig_y)
                if block_type != config.EMPTY:
                    block_index = (dig_y, dig_x)
                    # Get block hardness
                    if block_type in BLOCKS:
                        hardness = BLOCKS[block_type]["hardness"]
                    else:
                        continue  # Skip if block type is not in BLOCKS

                    # Initialize mining progress if it doesn't exist
                    if block_index not in mining_progress:
                        mining_progress[block_index] = 0
                        mining_animation[block_index] = 0  # Initialize animation progress

                    # Increase mining progress based on hardness and delta time
                    mining_progress[block_index] += dt / hardness
                    mining_animation[block_index] = min(mining_progress[block_index], 1)  # Clamp animation progress

                    # If mining is complete, generate drops
                    if mining_progress[block_index] >= 1:
                        # Determine the drop
                        dropped_block = config.EMPTY  # Default to empty
                        if block_type in BLOCKS and "drops" in BLOCKS[block_type]:
                            drops = BLOCKS[block_type]["drops"]
                            for drop_id_str, probability in drops.items():
                                try:
                                    drop_id = int(drop_id_str)
                                except ValueError:
                                    print(f"Invalid drop ID: {drop_id_str}")
                                    continue

                                if drop_id in BLOCKS and random.random() < probability:
                                    dropped_block = drop_id
                                    break  # Only generate one drop

                        # Add the dropped block to the inventory
                        if dropped_block != config.EMPTY:
                            if add_to_inventory(dropped_block):
                                set_block_at(dig_x, dig_y, config.EMPTY)  # Set the block to empty only if added to inventory
                            else:
                                dropped_block = block_type # If inventory is full, keep the block
                                set_block_at(dig_x, dig_y, dropped_block)
                        else:
                            set_block_at(dig_x, dig_y, config.EMPTY)

                        mining_progress.pop(block_index, None)  # Remove progress
                    laser_points.append((dig_x * config.PIXEL_SIZE + config.PIXEL_SIZE // 2 - camera_x,
                                         dig_y * config.PIXEL_SIZE + config.PIXEL_SIZE // 2 - camera_y))
            laser_active = True  # Laser is active while mining
        else:
            laser_active = False

        # --- Mouvement du Joueur ---
        keys = pygame.key.get_pressed()
        move_x = 0
        move_y = 0  # Ajout du mouvement vertical

        if keys[pygame.K_LEFT] or keys[pygame.K_a]: move_x -= config.PLAYER_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: move_x += config.PLAYER_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]: move_y -= JETPACK_SPEED  # Jetpack vers le haut
        if keys[pygame.K_DOWN] or keys[pygame.K_s]: move_y += JETPACK_SPEED  # Jetpack vers le bas

        # --- Collision Detection ---
        # Check horizontal collision
        if not check_collision(player_x, player_y, move_x * dt, 0):
            player_x += move_x * dt  # Mouvement horizontal
        else:
            # If collision, try to slide
            player_x += 0  # Stop horizontal movement

        # Check vertical collision
        if not check_collision(player_x, player_y, 0, move_y * dt):
            player_y += move_y * dt  # Mouvement vertical
        else:
            player_y += 0  # Stop vertical movement

        player_x, player_y = clamp_player_position(player_x, player_y)  # Applique les limites

        # --- Mise à jour de la Caméra ---
        # Fait suivre la caméra le joueur
        target_camera_x = player_x - screen_width / 2
        target_camera_y = player_y - screen_height / 2
        camera_x = int(target_camera_x)
        camera_y = int(target_camera_y)

        # --- Simulation ---
        # For infinite world, we need to disable the old simulation for now
        # TODO: Update simulation for infinite world
        if not ENABLE_INFINITE_WORLD:
            # Met à jour les animations (place les blocs qui ont fini de tomber)
            falling_animations, animating_sources, grid, next_active_columns = \
                simulation.update_animations(current_time_ms, falling_animations, grid, next_active_columns)

            # Exécute la simulation de gravité pour les colonnes actives
            grid, falling_animations, animating_sources, next_active_columns = \
                simulation.run_gravity_simulation(active_columns, grid, falling_animations, animating_sources,
                                               current_time_ms, next_active_columns)

            # Met à jour l'ensemble des colonnes actives pour la prochaine frame
            active_columns = next_active_columns

        # Handle chunk loading/unloading for infinite world
        if ENABLE_INFINITE_WORLD:
            # Ensure chunks around the player are loaded
            ensure_chunks_around_point(player_x, player_y, CHUNK_LOAD_RADIUS)
            
            # Periodically unload distant chunks (every second)
            if int(current_time_precise) != int(last_time):
                unload_distant_chunks(player_x, player_y)

        # --- Rendu ---
        # Draw the background
        screen.fill((0, 0, 0)) # Black background

        # Get active chunks
        active_chunks = get_active_chunks(player_x, player_y, screen_width, screen_height)

        # Render each chunk to a separate surface
        rendered_chunks = {}
        for chunk_x, chunk_y in active_chunks:
            rendered_chunks[(chunk_x, chunk_y)] = render_chunk(chunk_x, chunk_y, camera_x, camera_y, mining_animation, block_surfaces)

        # Blit the rendered chunks to the screen
        for (chunk_x, chunk_y) in active_chunks:
            if (chunk_x, chunk_y) in rendered_chunks:
                surface = rendered_chunks[(chunk_x, chunk_y)]
                chunk_screen_x = chunk_x * CHUNK_SIZE * config.PIXEL_SIZE - camera_x
                chunk_screen_y = chunk_y * CHUNK_SIZE * config.PIXEL_SIZE - camera_y
                screen.blit(surface, (chunk_screen_x, chunk_screen_y))

        # --- Debug Rendering ---
        if DEBUG_MODE:
            for chunk_x, chunk_y in active_chunks:
                chunk_screen_x = chunk_x * CHUNK_SIZE * config.PIXEL_SIZE - camera_x
                chunk_screen_y = chunk_y * CHUNK_SIZE * config.PIXEL_SIZE - camera_y
                chunk_rect = pygame.Rect(chunk_screen_x, chunk_screen_y, CHUNK_SIZE * config.PIXEL_SIZE, CHUNK_SIZE * config.PIXEL_SIZE)
                pygame.draw.rect(screen, (0, 255, 0), chunk_rect, 1)  # Green border

      
        # Draw the player
        player_screen_x = player_x - camera_x
        player_screen_y = player_y - camera_y
        player_rect = pygame.Rect(player_screen_x, player_screen_y, config.PLAYER_WIDTH, config.PLAYER_HEIGHT)
        pygame.draw.rect(screen, (255, 255, 255), player_rect)  # White player

        # Draw laser beam
        if laser_active:
            # Draw the laser beam
            if len(laser_points) >= 2:  # Ensure there are at least two points
                pygame.draw.lines(screen, (255, 0, 0), False, laser_points, 3)

        # Draw inventory
        draw_inventory(screen)

        # Draw performance stats
        draw_performance_stats(screen, dt, len(active_chunks))

        # --- Contrôle des FPS ---
        clock.tick(config.FPS_CAP)

        pygame.display.flip()  # Met à jour l'affichage complet

    # Clean up chunk generation threads before exiting
    chunk_gen_active = False
    for thread in chunk_gen_threads:
        thread.join(timeout=0.5)  # Give threads time to exit

    # --- Fin de la Boucle ---
    profiler.disable()
    print("\n--- Profiler Stats ---")
    profiler.print_stats(sort='cumulative')

    pygame.quit()
    sys.exit()

