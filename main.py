import pygame
import yappi 
import time
import sys
import os
import random
import numpy as np
import threading
import queue
import json
import math
import copy

import gc
import traceback

# Import core modules
from core import config

# Import the queue explicitly from chunks 
from world.chunks import (chunk_generation_queue, loaded_chunks, modified_chunks, 
                        generating_chunks,  # Import generating_chunks
                        chunk_lock, get_chunk_coords, 
                        ensure_chunks_around_point, unload_distant_chunks, 
                        get_active_chunks, set_block_at, get_block_at,
                        mark_chunk_modified, start_chunk_workers, stop_chunk_workers,
                        save_world_to_file, load_world_from_file,
                        ensure_origin_chunk_exists, initial_save_chunks)  # Import initial_save_chunks

from entities.player import Player
from ui.inventory import Inventory, HOTBAR_SIZE  # Import HOTBAR_SIZE
from ui.machine_ui import MachineUI
from systems.machine_system import MachineSystem
from utils.rendering import create_block_surfaces, render_chunk, draw_performance_stats, render_block
from systems.crafting_system import CraftingSystem
from ui.crafting_ui import CraftingUI
from systems.storage_system import StorageSystem
from systems.conveyor_system import ConveyorSystem
from ui.storage_ui import StorageUI
from systems.multi_block_system import MultiBlockSystem
from systems.extractor_system import ExtractorSystem
from systems.auto_miner_system import AutoMinerSystem  # Import the new system
from utils.background import generate_clouds, generate_hills, generate_stars, draw_background
from world.block_utils import apply_gravity

# Import GPU detection
from utils.gpu_detection import GPU_AVAILABLE, detect_gpu

from ui.main_menu import MainMenu

# --- Game Settings ---
DEBUG_MODE = False         # Disable debug mode for performance testing
SAVES_DIR = "saves"        # Define the saves directory
if not os.path.exists(SAVES_DIR):  # Ensure the saves directory exists
    os.makedirs(SAVES_DIR)
CURRENT_SAVE_FILE_NAME = None  # Track the currently loaded save file name
SAVE_FILE = None           # Path to the save file (set dynamically)
SEED = None                # World generation seed (set dynamically)
ENABLE_CHUNK_CACHE = True  # Enable chunk caching for performance
MAX_ACTIVE_CHUNKS = 64     # Further reduce maximum active chunks to render
PERFORMANCE_MONITOR = True # Show performance stats
VIEW_DISTANCE_MULTIPLIER = 1.2  # Slightly reduce view distance multiplier
CHUNK_LOAD_RADIUS = 4      # Revert to a reasonable value (e.g., 6 or 7)
CHUNK_UNLOAD_DISTANCE = 8  # Keep chunks loaded a bit longer than the load radius
CHUNK_GEN_THREAD_COUNT = 2 # Augmentez à 4 threads pour une génération plus rapide
ENABLE_INFINITE_WORLD = True  # Enable infinite world generation
USE_GPU_GENERATION = True  # Use GPU for generation if available

def get_chunk_seed(global_seed, chunk_x, chunk_y):
    return global_seed

def play_sound_effect(effect_name):
    """Play a sound effect."""
    pass

def show_visual_effect(effect_name, position):
    """Show a visual effect."""
    pass

def display_notification(message, duration=2):
    """Display a notification on the screen."""
    pass

def display_help_overlay():
    """Display help overlay with controls and tips."""
    pass

def close_all_interfaces():
    """Close all active interfaces."""
    global active_storage, inventory_open, machine_ui_open, crafting_ui_open  # Add UI state flags
    if machine_system.get_active_machine() is not None:
        machine_system.close_machine_ui()
        machine_ui_open = False
    if crafting_system.get_active_table() is not None:
        crafting_system.close_table_ui()
        crafting_ui_open = False
    active_storage = None
    inventory_open = False  # Close inventory as well

def quick_move_item(source, destination):
    """Move item quickly between inventory and storage."""
    pass

last_placement = None

def undo_last_placement():
    """Undo the last block placement."""
    global last_placement
    if last_placement:
        block_x, block_y, block_type = last_placement
        set_block_at(block_x, block_y, config.EMPTY)
        last_placement = None
    else:
        pass

def display_durability(machine_or_tool):
    """Display durability of a machine or tool."""
    pass

def render_mini_map():
    """Render a mini-map of the explored area."""
    pass

def auto_save():
    """Automatically save the game at regular intervals."""
    save_current_world()

def translate_text(text, language="en"):
    """Translate text to the specified language."""
    return text

def find_spawn_position():
    """Finds a safe spawn position for the player above the ground."""
    spawn_chunk_x, spawn_chunk_y = 0, 0

    ensure_origin_chunk_exists()

    with chunk_lock:
        if (spawn_chunk_x, spawn_chunk_y) not in loaded_chunks:
            return 0, 0
        chunk = loaded_chunks[(spawn_chunk_x, spawn_chunk_y)]

    try:
        for y in range(config.CHUNK_SIZE):
            for x in range(config.CHUNK_SIZE):
                is_empty = chunk[y, x] == config.EMPTY
                is_ground_below = False
                if y < config.CHUNK_SIZE - 1:
                    below_block_type = chunk[y + 1, x]
                    is_ground_below = below_block_type in config.BLOCKS and config.BLOCKS[below_block_type]["solid"]

                if is_empty and is_ground_below:
                    return (spawn_chunk_x * config.CHUNK_SIZE + x) * config.PIXEL_SIZE, \
                        (spawn_chunk_y * config.CHUNK_SIZE + y) * config.PIXEL_SIZE

        middle_x = config.CHUNK_SIZE // 2
        for y in range(config.CHUNK_SIZE):
            if chunk[y, middle_x] == config.EMPTY:
                return (spawn_chunk_x * config.CHUNK_SIZE + middle_x) * config.PIXEL_SIZE, \
                    (spawn_chunk_y * config.CHUNK_SIZE + y) * config.PIXEL_SIZE

        middle_x = config.CHUNK_SIZE // 2
        with chunk_lock:
            chunk[0, middle_x] = config.EMPTY
            modified_chunks.add((spawn_chunk_x, spawn_chunk_y))
        return (spawn_chunk_x * config.CHUNK_SIZE + middle_x) * config.PIXEL_SIZE, \
            (spawn_chunk_y * config.CHUNK_SIZE + 0) * config.PIXEL_SIZE

    except Exception:
        return 0, 0

def check_collision(px, py, move_x, move_y):
    """Check for collisions between player and blocks."""
    if not player.collision_enabled:
        return False
    
    player_rect = pygame.Rect(px, py, player.width, player.height)
    new_player_rect = player_rect.move(move_x, move_y)
    
    for x in range(new_player_rect.left // config.PIXEL_SIZE, (new_player_rect.right // config.PIXEL_SIZE) + 1):
        for y in range(new_player_rect.top // config.PIXEL_SIZE, (new_player_rect.bottom // config.PIXEL_SIZE) + 1):
            block_type = get_block_at(x, y)
            if block_type in config.BLOCKS and config.BLOCKS[block_type]["solid"]:
                block_rect = pygame.Rect(x * config.PIXEL_SIZE, y * config.PIXEL_SIZE, 
                                        config.PIXEL_SIZE, config.PIXEL_SIZE)
                if new_player_rect.colliderect(block_rect):
                    return True
        
    return False

def handle_mining(dt, mouse_x, mouse_y, player_x, player_y, camera_x, camera_y):
    """Handle mining action when the player is using the laser."""
    laser_points = []
    world_pixel_x = mouse_x + camera_x
    world_pixel_y = mouse_y + camera_y

    player_center_x = player_x + player.width / 2
    player_center_y = player_y + player.height / 2
    direction_x = world_pixel_x - player_center_x
    direction_y = world_pixel_y - player_center_y
    distance = math.hypot(direction_x, direction_y)
    if distance == 0: distance = 1

    norm_direction_x = direction_x / distance
    norm_direction_y = direction_y / distance

    laser_range_pixels = 15 * config.PIXEL_SIZE

    step_size = config.PIXEL_SIZE / 4
    for i in range(int(laser_range_pixels / step_size)):
        current_pixel_x = player_center_x + norm_direction_x * i * step_size
        current_pixel_y = player_center_y + norm_direction_y * i * step_size

        dig_block_x = int(current_pixel_x // config.PIXEL_SIZE)
        dig_block_y = int(current_pixel_y // config.PIXEL_SIZE)

        block_type = get_block_at(dig_block_x, dig_block_y)

        if block_type != config.EMPTY:
            block_index = (dig_block_x, dig_block_y)

            if block_type in config.BLOCKS:
                hardness = config.BLOCKS[block_type].get("hardness", 1)
                if hardness < 0:
                    break
            else:
                break

            if block_index not in mining_progress:
                mining_progress[block_index] = 0
                mining_animation[block_index] = 0

            mining_progress[block_index] += dt / hardness
            mining_animation[block_index] = min(mining_progress[block_index], 1)

            if mining_progress[block_index] >= 1:
                original_block_type = block_type

                dropped_block = config.EMPTY
                drop_data = config.BLOCKS.get(original_block_type, {}).get("drops")
                if drop_data:
                    for drop_id_str, probability in drop_data.items():
                        try: drop_id = int(drop_id_str)
                        except ValueError: continue
                        if drop_id in config.BLOCKS and random.random() < probability:
                            dropped_block = drop_id
                            break
                else:
                    if hardness >= 0:
                        dropped_block = original_block_type

                added_to_inventory = False
                if dropped_block != config.EMPTY:
                    if inventory.add_item(dropped_block):
                        added_to_inventory = True

                if set_block_at(dig_block_x, dig_block_y, config.EMPTY):
                    if original_block_type == config.STORAGE_CHEST:
                        storage_system.unregister_storage(dig_block_x, dig_block_y)
                        multi_block_system.unregister_multi_block(dig_block_x, dig_block_y)
                    elif original_block_type == config.CRAFTING_TABLE:
                        crafting_system.unregister_table(dig_block_x, dig_block_y)
                    elif original_block_type == config.ORE_PROCESSOR:
                        machine_system.unregister_machine(dig_block_x, dig_block_y)
                        multi_block_system.unregister_multi_block(dig_block_x, dig_block_y)
                    elif original_block_type == config.CONVEYOR_BELT or original_block_type == config.VERTICAL_CONVEYOR:
                        conveyor_system.unregister_conveyor(dig_block_x, dig_block_y)
                        multi_block_system.unregister_multi_block(dig_block_x, dig_block_y)
                    elif original_block_type == config.ITEM_EXTRACTOR:
                        extractor_system.unregister_extractor(dig_block_x, dig_block_y)
                        multi_block_system.unregister_multi_block(dig_block_x, dig_block_y)
                    elif original_block_type == config.AUTO_MINER:
                        auto_miner_system.unregister_miner(dig_block_x, dig_block_y)

                mining_progress.pop(block_index, None)
                mining_animation.pop(block_index, None)

            laser_points.append((current_pixel_x - camera_x, current_pixel_y - camera_y))
            break

    return laser_points

def initialize_game(save_name=None):
    """Initializes game state, loading from save or creating a new world."""
    global player, camera_x, camera_y, SEED, CURRENT_SAVE_FILE_NAME, rendered_chunk_cache
    global player_start_pos, inventory, machine_system, crafting_system, storage_system
    global conveyor_system, extractor_system, multi_block_system, auto_miner_system
    global mining_progress, mining_animation, time_of_day

    print(f"Initializing game. Save name: {save_name}")

    # Clear existing state before loading/creating
    with chunk_lock:
        loaded_chunks.clear()
        modified_chunks.clear()
        generating_chunks.clear()
        initial_save_chunks.clear()
    rendered_chunk_cache.clear()
    storage_system.storages.clear()
    conveyor_system.conveyors.clear()
    conveyor_system.items_on_conveyors.clear()
    extractor_system.extractors.clear()
    multi_block_system.multi_block_origins.clear()
    multi_block_system.multi_block_structures.clear()
    auto_miner_system.miners.clear()
    machine_system.machines.clear() # Assuming MachineSystem has a 'machines' dict
    crafting_system.tables.clear() # Assuming CraftingSystem has a 'tables' dict
    inventory.items = [None] * inventory.size # Reset inventory

    mining_progress = {}
    mining_animation = {}
    time_of_day = 0.3 # Reset time

    CURRENT_SAVE_FILE_NAME = save_name
    save_file_path = os.path.join(SAVES_DIR, save_name) if save_name else None

    if save_name and os.path.exists(save_file_path):
        print(f"Loading world from: {save_file_path}")
        success, player_start_pos = load_world_from_file(save_file_path, storage_system, rendered_chunk_cache, conveyor_system, extractor_system, multi_block_system, auto_miner_system)
        if success:
            SEED = config.SEED # SEED is loaded from the file via config by load_world_from_file
            print(f"Successfully loaded world. Seed: {SEED}")
            player = Player(player_start_pos[0], player_start_pos[1])
            camera_x = player.x - screen_width // 2
            camera_y = player.y - screen_height // 2
        else:
            print(f"Failed to load {save_file_path}, creating a new world with this name.")
            # Fallback to creating a new world if load fails
            SEED = int(time.time()) # Use a new seed
            config.SEED = SEED
            random.seed(SEED)
            np.random.seed(SEED)
            ensure_origin_chunk_exists()
            player_start_pos = find_spawn_position()
            player = Player(player_start_pos[0], player_start_pos[1])
            camera_x = player.x - screen_width // 2
            camera_y = player.y - screen_height // 2
            save_current_world()
    else:
        if save_name:
            print(f"Save file {save_file_path} not found or specified name invalid. Creating new world: {save_name}")
        else:
            print("No save name provided. Creating new default world.")
            # Generate a default name if none provided (e.g., for quick start)
            save_name = f"world_{int(time.time())}.json"
            CURRENT_SAVE_FILE_NAME = save_name
            print(f"Generated save name: {CURRENT_SAVE_FILE_NAME}")

        # Create a new world
        SEED = int(time.time()) # Use a new seed
        config.SEED = SEED
        random.seed(SEED)
        np.random.seed(SEED)
        ensure_origin_chunk_exists()
        player_start_pos = find_spawn_position()
        player = Player(player_start_pos[0], player_start_pos[1])
        camera_x = player.x - screen_width // 2
        camera_y = player.y - screen_height // 2
        save_current_world() # Save the newly created world immediately

    # Ensure initial chunks are loaded around the player
    ensure_chunks_around_point(player.x, player.y, CHUNK_LOAD_RADIUS + 2)
    print("Game initialization complete.")


def save_current_world():
    """Saves the current game state to the currently loaded save file."""
    if CURRENT_SAVE_FILE_NAME:
        save_file_path = os.path.join(SAVES_DIR, CURRENT_SAVE_FILE_NAME)
        print(f"Saving world to {save_file_path}...")
        save_world_to_file(save_file_path, storage_system, (player.x, player.y), conveyor_system, extractor_system, multi_block_system, auto_miner_system)
    else:
        print("Error: Cannot save world, no save file name is set.")

pygame.init()

try:
    display_info = pygame.display.Info()
    screen_width = display_info.current_w
    screen_height = display_info.current_h
except pygame.error:
    screen_width = 1200
    screen_height = 1000

screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
pygame.display.set_caption(config.WINDOW_TITLE)
clock = pygame.time.Clock()
fps_font = pygame.font.SysFont("Consolas", 18)

block_surfaces = create_block_surfaces()

multi_block_system = MultiBlockSystem(get_block_at, set_block_at)

machine_system = MachineSystem(get_block_at, set_block_at)

machine_ui = MachineUI(screen_width, screen_height, block_surfaces)

crafting_system = CraftingSystem(get_block_at, set_block_at)
crafting_ui = CraftingUI(screen_width, screen_height, block_surfaces)

storage_system = StorageSystem(get_block_at, set_block_at, multi_block_system)
conveyor_system = ConveyorSystem(get_block_at, set_block_at, multi_block_system)
storage_ui = StorageUI(screen_width, screen_height, block_surfaces)

extractor_system = ExtractorSystem(
    get_block_at, set_block_at, storage_system, conveyor_system, multi_block_system
)

auto_miner_system = AutoMinerSystem(get_block_at, set_block_at, storage_system)

inventory = Inventory()

active_storage = None

conveyor_placement_active = False
conveyor_placement_mode = 0
conveyor_placement_direction = 0
conveyor_placement_preview = []

chunk_workers = start_chunk_workers(CHUNK_GEN_THREAD_COUNT, int(time.time()))

rendered_chunk_cache = {}

player_start_pos = (0, 0)
player = None
camera_x, camera_y = 0, 0

time_of_day = 0.3
DAY_LENGTH = 60.0

background_width = screen_width * 3
background_height = screen_height
cloud_layer = None
hill_layers = None
star_layer = None

def initialize_background():
    """Generates background layers based on the current SEED."""
    global cloud_layer, hill_layers, star_layer
    print(f"Initializing background with seed: {SEED}")
    cloud_layer = generate_clouds(background_width, background_height, SEED)
    hill_layers = generate_hills(background_width, background_height, 2, SEED)
    star_layer = generate_stars(background_width, background_height, SEED)

if USE_GPU_GENERATION:
    if not detect_gpu():
        USE_GPU_GENERATION = False

main_menu = MainMenu(screen_width, screen_height, SAVES_DIR)

def render_visible_chunks(screen, camera_x, camera_y, active_chunks, loaded_chunks, block_surfaces, machine_system):
    """Render only the visible chunks to improve performance."""
    with chunk_lock:
        for chunk_x, chunk_y in active_chunks:
            chunk_coord = (chunk_x, chunk_y)
            if chunk_coord in loaded_chunks:
                # Check if chunk needs re-rendering (modified or not in cache)
                needs_render = chunk_coord in modified_chunks or chunk_coord not in rendered_chunk_cache

                if needs_render:
                    chunk_data = loaded_chunks[chunk_coord]
                    # Render the chunk surface
                    new_surface = render_chunk(
                        chunk_data, chunk_x, chunk_y, camera_x, camera_y,
                        mining_animation, block_surfaces, machine_system,
                        multi_block_system
                    )
                    # Store in cache and remove from modified set
                    rendered_chunk_cache[chunk_coord] = new_surface
                    modified_chunks.discard(chunk_coord) # Remove after rendering

                # Get the surface (either newly rendered or from cache)
                surface_to_blit = rendered_chunk_cache.get(chunk_coord)

                if surface_to_blit:
                    # Calculate screen position and blit
                    chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
                    chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
                    screen.blit(surface_to_blit, (chunk_screen_x, chunk_screen_y))

def render_debug_chunks(screen, camera_x, camera_y, active_chunks):
    """Render chunk borders for debugging purposes."""
    for chunk_x, chunk_y in active_chunks:
        chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
        chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
        chunk_rect = pygame.Rect(chunk_screen_x, chunk_screen_y,
                                config.CHUNK_SIZE * config.PIXEL_SIZE,
                                config.CHUNK_SIZE * config.PIXEL_SIZE)
        pygame.draw.rect(screen, (0, 255, 0), chunk_rect, 1)

if __name__ == '__main__':
    running = True
    in_menu = True
    game_initialized = False # Track if the game world is ready
    last_time = time.time()

    # UI State Flags
    inventory_open = False
    machine_ui_open = False
    crafting_ui_open = False
    storage_ui_open = False # Assuming you might add this later

    # Placement State
    placement_rotation = 0 # 0: Right, 1: Down, 2: Left, 3: Up (for rotatable blocks)
    placement_conveyor_mode = 0 # 0: Horizontal, 1: Vertical (for conveyors)

    # configure yappi if debugging
    if DEBUG_MODE:
        yappi.set_clock_type("cpu")

    while running:
        if in_menu:
            game_initialized = False # Reset flag when returning to menu
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen_width, screen_height = event.size
                    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                    main_menu.update_screen_size(screen_width, screen_height)
                else:
                    action = main_menu.handle_input(event)
                    if isinstance(action, tuple): # Check if action is a tuple (type, value)
                        action_type, value = action
                        if action_type == "load_game":
                            print(f"Menu action: Load Game '{value}'")
                            initialize_game(save_name=value)
                            initialize_background() # Init background with loaded seed
                            in_menu = False
                            game_initialized = True
                            last_time = time.time() # Reset dt timer
                            # --- Start Profiler on Game Start ---
                            if DEBUG_MODE: yappi.start()
                        elif action_type == "new_game":
                            print(f"Menu action: New Game '{value}'")
                            initialize_game(save_name=value) # Create new world with name
                            initialize_background() # Init background with new seed
                            in_menu = False
                            game_initialized = True
                            last_time = time.time() # Reset dt timer
                            # --- Start Profiler on Game Start ---
                            if DEBUG_MODE: yappi.start()
                        elif action_type == "delete_game":
                            try:
                                file_to_delete = os.path.join(SAVES_DIR, value)
                                if os.path.exists(file_to_delete):
                                    print(f"Deleting save: {file_to_delete}")
                                    os.remove(file_to_delete)
                                    main_menu.scan_saves() # Refresh save list in menu
                                else:
                                    print(f"Save file not found for deletion: {file_to_delete}")
                            except Exception as e:
                                print(f"Error deleting save file {value}: {e}")

                    elif action == "Quit":
                        running = False

            main_menu.draw(screen)
            pygame.display.flip()
            clock.tick(config.FPS_CAP)
        elif game_initialized: # Only run game logic if initialized
            # --- Game Loop Logic ---
            laser_active = False
            laser_points = []
            # compute current mouse block coordinates for interactions and placement
            mouse_x, mouse_y = pygame.mouse.get_pos()
            mouse_block_x = (mouse_x + camera_x) // config.PIXEL_SIZE
            mouse_block_y = (mouse_y + camera_y) // config.PIXEL_SIZE

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    save_current_world() # Use the new save function
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_o:
                        save_current_world() # Use the new save function
                    elif event.key == pygame.K_ESCAPE:
                        save_current_world() # Save before returning to menu
                        in_menu = True
                    elif event.key == pygame.K_e: # Inventory Toggle
                        inventory_open = not inventory_open
                        if inventory_open:
                            if machine_ui_open: machine_system.close_machine_ui(); machine_ui_open = False
                            if crafting_ui_open: crafting_system.close_table_ui(); crafting_ui_open = False
                            active_storage = None # Close storage UI
                        else:
                            inventory.dragged_item = None # Clear dragged item on close
                    elif event.key == pygame.K_f: # Interaction Key
                        if not (inventory_open or machine_ui_open or crafting_ui_open or active_storage): # Only interact if no UI is open
                            block_type = get_block_at(mouse_block_x, mouse_block_y)
                            if block_type == config.ORE_PROCESSOR:
                                machine_system.toggle_machine_ui(mouse_block_x, mouse_block_y)
                                machine_ui_open = machine_system.get_active_machine() is not None
                            elif block_type == config.CRAFTING_TABLE:
                                crafting_system.toggle_table_ui(mouse_block_x, mouse_block_y)
                                crafting_ui_open = crafting_system.get_active_table() is not None
                            elif block_type == config.STORAGE_CHEST:
                                storage_origin = storage_system.multi_block_system.get_multi_block_origin(mouse_block_x, mouse_block_y)
                                if storage_origin:
                                    if active_storage and active_storage == storage_system.get_storage_at(*storage_origin):
                                        active_storage = None # Close if interacting with the same one
                                    else:
                                        active_storage = storage_system.get_storage_at(*storage_origin)
                                        if inventory_open: inventory_open = False
                                        if machine_ui_open: machine_system.close_machine_ui(); machine_ui_open = False
                                        if crafting_ui_open: crafting_system.close_table_ui(); crafting_ui_open = False
                                else:
                                    if storage_system.register_storage(mouse_block_x, mouse_block_y):
                                        storage_origin = storage_system.multi_block_system.get_multi_block_origin(mouse_block_x, mouse_block_y)
                                        if storage_origin:
                                            active_storage = storage_system.get_storage_at(*storage_origin)
                    elif event.key == pygame.K_r: # Rotate Placement
                        placement_rotation = (placement_rotation + 1) % 4
                    elif event.key == pygame.K_t: # Cycle Conveyor Mode/Direction
                        selected_item_id = inventory.get_selected_item()
                        if selected_item_id == config.CONVEYOR_BELT or selected_item_id == config.VERTICAL_CONVEYOR:
                            if placement_conveyor_mode == 0:
                                placement_conveyor_mode = 1
                                placement_rotation = 1
                            else:
                                placement_conveyor_mode = 0
                                placement_rotation = 0
                    elif event.key == pygame.K_n: # Toggle Noclip
                        collision_status = player.toggle_collision()
                    elif pygame.K_1 <= event.key <= pygame.K_9:
                        inventory.selected_slot = event.key - pygame.K_1
                    elif event.key == pygame.K_0:
                        inventory.selected_slot = HOTBAR_SIZE - 1

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 3 and player:
                        selected_item_id = inventory.get_selected_item()
                        if selected_item_id is not None and selected_item_id != config.EMPTY:
                            target_block_type = get_block_at(mouse_block_x, mouse_block_y)
                            if target_block_type == config.EMPTY:
                                block_to_place = selected_item_id
                                place_success = False

                                size = multi_block_system.block_sizes.get(block_to_place, (1, 1))
                                if size != (1, 1):
                                    can_place_multi = True
                                    for dx in range(size[0]):
                                        for dy in range(size[1]):
                                            if get_block_at(mouse_block_x + dx, mouse_block_y + dy) != config.EMPTY:
                                                can_place_multi = False
                                                break
                                        if not can_place_multi: break

                                    if can_place_multi:
                                        if multi_block_system.register_multi_block(mouse_block_x, mouse_block_y, block_to_place):
                                            if set_block_at(mouse_block_x, mouse_block_y, block_to_place):
                                                if block_to_place == config.STORAGE_CHEST:
                                                    storage_system.register_storage(mouse_block_x, mouse_block_y)
                                                elif block_to_place == config.ORE_PROCESSOR:
                                                    machine_system.register_machine(mouse_block_x, mouse_block_y, block_to_place)
                                                elif block_to_place == config.CRAFTING_TABLE:
                                                    crafting_system.register_table(mouse_block_x, mouse_block_y)
                                                elif block_to_place == config.CONVEYOR_BELT or block_to_place == config.VERTICAL_CONVEYOR:
                                                    conveyor_system.register_conveyor(mouse_block_x, mouse_block_y, placement_rotation)
                                                elif block_to_place == config.ITEM_EXTRACTOR:
                                                    extractor_system.register_extractor(mouse_block_x, mouse_block_y)
                                                elif block_to_place == config.AUTO_MINER:
                                                    auto_miner_system.register_miner(mouse_block_x, mouse_block_y)

                                                inventory.remove_item(selected_item_id)
                                                place_success = True
                                        else:
                                            print("Failed to register multi-block structure.")
                                    else:
                                        print("Not enough space for multi-block structure.")
                                elif size == (1, 1):
                                    if set_block_at(mouse_block_x, mouse_block_y, block_to_place):
                                        if block_to_place == config.CONVEYOR_BELT or block_to_place == config.VERTICAL_CONVEYOR:
                                            conveyor_system.register_conveyor(mouse_block_x, mouse_block_y, placement_rotation)
                                        inventory.remove_item(selected_item_id)
                                        place_success = True

                                if place_success:
                                    placement_rotation = 0
                                    placement_conveyor_mode = 0

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        pass
                    elif event.button == 3:
                        pass

            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            keys = pygame.key.get_pressed()
            if player:
                player.update(dt, keys, check_collision)
                camera_x = player.x - screen_width // 2
                camera_y = player.y - screen_height // 2

                if ENABLE_INFINITE_WORLD:
                    ensure_chunks_around_point(player.x, player.y, CHUNK_LOAD_RADIUS)
                    if int(current_time) % 5 == 0:
                        unload_distant_chunks(player.x, player.y, CHUNK_UNLOAD_DISTANCE, rendered_chunk_cache)

            mouse_pressed = pygame.mouse.get_pressed()[0]
            if mouse_pressed and not inventory.dragged_item and player:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                laser_points = handle_mining(dt, mouse_x, mouse_y, player.x, player.y, camera_x, camera_y)
                laser_active = len(laser_points) > 0
            else:
                laser_active = False
                laser_points = []

            machine_system.update()
            conveyor_system.update(dt, storage_system, machine_system)
            extractor_system.update(dt)
            auto_miner_system.update(dt)

            time_of_day += dt / DAY_LENGTH
            if time_of_day >= 1.0: time_of_day -= 1.0

            screen.fill((0, 0, 0))

            if cloud_layer and hill_layers and star_layer:
                draw_background(screen, camera_x, camera_y, time_of_day, background_width, background_height,
                                cloud_layer, hill_layers, star_layer)

            if player:
                active_chunks = get_active_chunks(player.x, player.y, screen_width, screen_height,
                                                VIEW_DISTANCE_MULTIPLIER, MAX_ACTIVE_CHUNKS)
                render_visible_chunks(screen, camera_x, camera_y, active_chunks, loaded_chunks, block_surfaces, machine_system)
                if DEBUG_MODE:
                    render_debug_chunks(screen, camera_x, camera_y, active_chunks)

            if player:
                player.draw(screen, camera_x, camera_y)

            if laser_active and len(laser_points) >= 2 and player:
                 start_point = (player.x + player.width // 2 - camera_x,
                               player.y + player.height // 2 - camera_y)
                 pygame.draw.line(screen, (255, 0, 0), start_point, laser_points[0], 3)

            inventory.draw(screen, screen_width, screen_height)
            inventory.draw_dragged_item(screen)

            if PERFORMANCE_MONITOR:
                draw_performance_stats(screen, dt, len(active_chunks) if player else 0, len(loaded_chunks), fps_font)

            pygame.display.flip()
            clock.tick(config.FPS_CAP)
        else:
            print("Warning: Game loop running but game not initialized.")
            in_menu = True
            clock.tick(config.FPS_CAP)

    if game_initialized and CURRENT_SAVE_FILE_NAME:
        save_current_world()
    stop_chunk_workers(chunk_workers)
    rendered_chunk_cache.clear()
    pygame.quit()
    sys.exit()



