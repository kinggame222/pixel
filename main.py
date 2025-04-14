import pygame
import cProfile
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
                         ensure_origin_chunk_exists)  # Import ensure_origin_chunk_exists

from entities.player import Player
from ui.inventory import Inventory
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
DEBUG_MODE = True          # Enable debug mode
SAVE_FILE = "world.json"   # Path to the save file
SEED = config.SEED         # World generation seed
ENABLE_CHUNK_CACHE = True  # Enable chunk caching for performance
MAX_ACTIVE_CHUNKS = 50     # Reduce maximum active chunks to render
PERFORMANCE_MONITOR = True # Show performance stats
VIEW_DISTANCE_MULTIPLIER = 1.5  # Reduce view distance multiplier
CHUNK_LOAD_RADIUS = 4      # Revert to a reasonable value (e.g., 6 or 7)
CHUNK_UNLOAD_DISTANCE = 4 # Revert to a reasonable value (e.g., 10 or 12)
CHUNK_GEN_THREAD_COUNT = 2 # Augmentez à 4 threads pour une génération plus rapide
ENABLE_INFINITE_WORLD = True  # Enable infinite world generation
USE_GPU_GENERATION = True  # Use GPU for generation if available

def find_spawn_position():
    """Finds a safe spawn position for the player above the ground."""
    spawn_chunk_x, spawn_chunk_y = 0, 0  # Start at the origin chunk

    # Ensure the origin chunk exists using the dedicated function
    ensure_origin_chunk_exists()  # This handles generation/loading if needed

    # Now safely get the origin chunk
    with chunk_lock:
        # Check again in case ensure_origin_chunk_exists failed silently (though it shouldn't)
        if (spawn_chunk_x, spawn_chunk_y) not in loaded_chunks:
            print("CRITICAL ERROR: Origin chunk still missing after ensure_origin_chunk_exists!")
            # Fallback emergency spawn
            return 0, 0
        chunk = loaded_chunks[(spawn_chunk_x, spawn_chunk_y)]

    try:
        # Find an empty space for spawning (using config constants)
        for y in range(config.CHUNK_SIZE):
            for x in range(config.CHUNK_SIZE):
                # Check for empty space with a solid block below
                is_empty = chunk[y, x] == config.EMPTY
                is_ground_below = False
                if y < config.CHUNK_SIZE - 1:
                    below_block_type = chunk[y + 1, x]
                    is_ground_below = below_block_type in config.BLOCKS and config.BLOCKS[below_block_type]["solid"]
                elif y == config.CHUNK_SIZE - 1:  # If at the bottom, check chunk below? More complex. Assume no spawn at bottom edge for now.
                    pass

                if is_empty and is_ground_below:
                    # Found empty space with ground beneath it
                    # Return world coordinates
                    return (spawn_chunk_x * config.CHUNK_SIZE + x) * config.PIXEL_SIZE, \
                           (spawn_chunk_y * config.CHUNK_SIZE + y) * config.PIXEL_SIZE

        # If no ideal spot is found, just use the highest empty space in the middle column
        middle_x = config.CHUNK_SIZE // 2
        for y in range(config.CHUNK_SIZE):
            if chunk[y, middle_x] == config.EMPTY:
                print("No ideal spawn found, using highest empty block in middle column.")
                return (spawn_chunk_x * config.CHUNK_SIZE + middle_x) * config.PIXEL_SIZE, \
                       (spawn_chunk_y * config.CHUNK_SIZE + y) * config.PIXEL_SIZE

        # If no empty space at all (highly unlikely), create one at the top center
        print("No empty space found in origin chunk, creating one at top center")
        middle_x = config.CHUNK_SIZE // 2
        with chunk_lock:  # Need lock to modify chunk data
            chunk[0, middle_x] = config.EMPTY
            modified_chunks.add((spawn_chunk_x, spawn_chunk_y))  # Mark modified
        return (spawn_chunk_x * config.CHUNK_SIZE + middle_x) * config.PIXEL_SIZE, \
               (spawn_chunk_y * config.CHUNK_SIZE + 0) * config.PIXEL_SIZE

    except Exception as e:
        # Last resort emergency spawn
        print(f"EMERGENCY: Error in finding spawn position: {e}")
        traceback.print_exc()
        print("Using emergency world origin spawn at (0,0)")
        return 0, 0

def check_collision(px, py, move_x, move_y):
    """Check for collisions between player and blocks."""
    if not player.collision_enabled:
        return False
    
    # Calculate player rectangle at new position
    player_rect = pygame.Rect(px, py, player.width, player.height)
    new_player_rect = player_rect.move(move_x, move_y)
    
    # Check for collisions with solid blocks
    for x in range(new_player_rect.left // config.PIXEL_SIZE, (new_player_rect.right // config.PIXEL_SIZE) + 1):
        for y in range(new_player_rect.top // config.PIXEL_SIZE, (new_player_rect.bottom // config.PIXEL_SIZE) + 1):
            block_type = get_block_at(x, y)
            if block_type in config.BLOCKS and config.BLOCKS[block_type]["solid"]:
                block_rect = pygame.Rect(x * config.PIXEL_SIZE, y * config.PIXEL_SIZE, 
                                        config.PIXEL_SIZE, config.PIXEL_SIZE)
                if new_player_rect.colliderect(block_rect):
                    return True  # Collision detected
    
    return False  # No collision detected

def handle_mining(dt, mouse_x, mouse_y, player_x, player_y, camera_x, camera_y):
    """Handle mining action when the player is using the laser."""
    laser_points = []
    # Calculate world PIXEL position
    world_pixel_x = mouse_x + camera_x
    world_pixel_y = mouse_y + camera_y

    # Calculate direction vector from player (center) to mouse pixel position
    player_center_x = player_x + player.width / 2
    player_center_y = player_y + player.height / 2
    direction_x = world_pixel_x - player_center_x
    direction_y = world_pixel_y - player_center_y
    distance = math.hypot(direction_x, direction_y) # Use math.hypot for distance
    if distance == 0: distance = 1

    # Normalize the direction vector
    norm_direction_x = direction_x / distance
    norm_direction_y = direction_y / distance

    # Laser range (in pixels) - adjust if needed
    laser_range_pixels = 15 * config.PIXEL_SIZE

    # Step along the laser direction in small increments
    step_size = config.PIXEL_SIZE / 4 # Check more frequently along the ray
    for i in range(int(laser_range_pixels / step_size)):
        current_pixel_x = player_center_x + norm_direction_x * i * step_size
        current_pixel_y = player_center_y + norm_direction_y * i * step_size

        # Convert current pixel position to world BLOCK coordinates
        dig_block_x = int(current_pixel_x // config.PIXEL_SIZE)
        dig_block_y = int(current_pixel_y // config.PIXEL_SIZE)

        # Check if dig position has a block using world BLOCK coordinates
        block_type = get_block_at(dig_block_x, dig_block_y) # Use block coords

        if block_type != config.EMPTY:
            # Use world BLOCK coordinates for mining progress keys
            block_index = (dig_block_x, dig_block_y) # Switched to (x, y) for consistency

            # Get block hardness
            if block_type in config.BLOCKS:
                hardness = config.BLOCKS[block_type].get("hardness", 1)
                if hardness < 0:  # Unbreakable
                    break
            else:
                # print(f"Warning: Block type {block_type} not found in config.BLOCKS")
                break # Skip if block type is not in BLOCKS

            # Initialize mining progress if it doesn't exist
            if block_index not in mining_progress:
                mining_progress[block_index] = 0
                mining_animation[block_index] = 0  # Initialize animation progress

            # Increase mining progress based on hardness and delta time
            mining_progress[block_index] += dt / hardness
            mining_animation[block_index] = min(mining_progress[block_index], 1)  # Clamp animation progress

            # If mining is complete, generate drops
            if mining_progress[block_index] >= 1:
                original_block_type = block_type  # Store before setting to EMPTY

                # --- Determine Drop ---
                dropped_block = config.EMPTY # Default to empty
                drop_data = config.BLOCKS.get(original_block_type, {}).get("drops")
                if drop_data:
                    # Simple drop logic: check probabilities
                    for drop_id_str, probability in drop_data.items():
                        try: drop_id = int(drop_id_str)
                        except ValueError: continue
                        if drop_id in config.BLOCKS and random.random() < probability:
                            dropped_block = drop_id
                            break # Take first successful drop based on probability
                else: # Default drop is the block itself if no drops defined (and not unbreakable)
                    if hardness >= 0:
                         dropped_block = original_block_type

                # --- Add to Inventory & Update World ---
                added_to_inventory = False
                if dropped_block != config.EMPTY:
                    if inventory.add_item(dropped_block):
                        added_to_inventory = True
                    # else: Inventory full, item lost for now

                # Set block to empty using world BLOCK coordinates
                if set_block_at(dig_block_x, dig_block_y, config.EMPTY): # Use block coords
                    # --- Unregister Systems if block was special ---
                    # (No changes needed here, functions already take block coords)
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
                        # multi_block_system.unregister_multi_block(dig_block_x, dig_block_y) # If it was registered

                # Remove progress tracking
                mining_progress.pop(block_index, None)
                mining_animation.pop(block_index, None) # Also remove animation progress

            # Add laser point for drawing (using pixel coordinates)
            laser_points.append((current_pixel_x - camera_x, current_pixel_y - camera_y))
            break # Stop laser at first block hit

    return laser_points

# Initialize Pygame
pygame.init()

# Get current screen dimensions
try:
    display_info = pygame.display.Info()
    screen_width = display_info.current_w
    screen_height = display_info.current_h
    print(f"Detected screen size: {screen_width}x{screen_height}")
except pygame.error as e:
    print(f"Could not get display info: {e}. Using default size.")
    screen_width = 1200  # Default width
    screen_height = 1000 # Default height

# Set display mode using detected or default size, make it resizable
screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
pygame.display.set_caption(config.WINDOW_TITLE)
clock = pygame.time.Clock()
fps_font = pygame.font.SysFont("Consolas", 18)

# Create block surfaces
block_surfaces = create_block_surfaces()

# Test rendering of block surfaces
for block_id, surface in block_surfaces.items():
    if surface.get_alpha() is None:
        print(f"Block ID {block_id} has no alpha channel.")
    else:
        print(f"Block ID {block_id} rendered successfully.")

# Initialize systems
# Create MultiBlockSystem before others that depend on it
multi_block_system = MultiBlockSystem(get_block_at, set_block_at)

# Initialize the machine system
machine_system = MachineSystem(get_block_at, set_block_at)

# Initialize machine UI (after screen size is determined)
machine_ui = MachineUI(screen_width, screen_height, block_surfaces)

# Initialize crafting system and UI (after screen size is determined)
crafting_system = CraftingSystem(get_block_at, set_block_at)
crafting_ui = CraftingUI(screen_width, screen_height, block_surfaces)

# Initialize storage and conveyor systems with multi-block awareness
storage_system = StorageSystem(get_block_at, set_block_at, multi_block_system)
conveyor_system = ConveyorSystem(get_block_at, set_block_at, multi_block_system)
storage_ui = StorageUI(screen_width, screen_height, block_surfaces) # Pass screen size

# Initialize extractor system to move items
extractor_system = ExtractorSystem(
    get_block_at, set_block_at, storage_system, conveyor_system, multi_block_system
)

# Initialize AutoMiner system
auto_miner_system = AutoMinerSystem(get_block_at, set_block_at, storage_system)  # Initialize

# Initialize inventory
inventory = Inventory()

# Add these variables to track UI state
active_storage = None

# Add conveyor placement variables
conveyor_placement_active = False
conveyor_placement_mode = 0  # 0=ligne droite, 1=diagonale, 2=zigzag
conveyor_placement_direction = 0  # 0=droite, 1=bas, 2=gauche, 3=haut
conveyor_placement_preview = []  # Liste des positions de prévisualisation

# Set random seed for world generation
random.seed(SEED)
np.random.seed(SEED)

# Start chunk generation worker threads
chunk_workers = start_chunk_workers(CHUNK_GEN_THREAD_COUNT, SEED)

# Initialize game state
player_start_pos = (0, 0)  # Default player start position
if os.path.exists(SAVE_FILE):
    print(f"Save file found: {SAVE_FILE}")
    # load_world_from_file now returns success status and player position
    success, player_start_pos = load_world_from_file(SAVE_FILE, storage_system, conveyor_system, extractor_system, multi_block_system, auto_miner_system)
    if success:
        print(f"Successfully loaded {len(loaded_chunks)} chunks from save file.")
        # Ensure the seed from the loaded world is used for new chunks
        SEED = config.SEED  # Update local SEED variable if config.SEED was changed by load_world
    else:
        print("Failed to load world from save file, generating new world.")
        # Clear any partially loaded state
        with chunk_lock:
            loaded_chunks.clear()
            modified_chunks.clear()
            generating_chunks.clear()
        # Reset other systems if needed
        storage_system.storages.clear()
        conveyor_system.conveyors.clear()
        conveyor_system.items_on_conveyors.clear()
        extractor_system.extractors.clear()
        multi_block_system.multi_block_origins.clear()
        multi_block_system.multi_block_structures.clear()
        auto_miner_system.miners.clear()  # Clear miners on failed load
        # Set seed for new world
        random.seed(SEED)
        np.random.seed(SEED)
        config.SEED = SEED  # Ensure config has the correct seed
        ensure_origin_chunk_exists()  # Make sure origin exists for a new world
        player_start_pos = find_spawn_position()  # Find spawn for new world
else:
    print(f"No save file found at {SAVE_FILE}, generating new world.")
    # Set seed for new world
    random.seed(SEED)
    np.random.seed(SEED)
    config.SEED = SEED  # Ensure config has the correct seed
    ensure_origin_chunk_exists()  # Generate origin chunk for the new world
    player_start_pos = find_spawn_position()  # Find spawn for new world

# Explicitly verify that chunks are loaded correctly after load/new world gen
with chunk_lock:
    print(f"Total loaded chunks after init: {len(loaded_chunks)}")
    if (0, 0) not in loaded_chunks:
        print("CRITICAL WARNING: Origin chunk (0,0) is NOT loaded after initialization!")
    else:
        print("Origin chunk (0,0) is loaded.")

# Get initial player position from loaded save or new world spawn
player_x, player_y = player_start_pos
player = Player(player_x, player_y)

# Initialize camera position
camera_x = player_x - screen_width // 2
camera_y = player_y - screen_height // 2

# Initialize mining tracking
mining_progress = {}  # Dictionary to track mining progress for each block
mining_animation = {}  # Dictionary to store mining animation progress

# Queue initial chunks around the player for background loading
print("Queueing initial chunks around player...")
ensure_chunks_around_point(player.x, player.y, CHUNK_LOAD_RADIUS + 2)  # Queue a slightly larger area initially
print(f"Initial queue size: {chunk_generation_queue.qsize()} chunks.")

# Initialize time of day (Terraria-style day/night cycle)
time_of_day = 0.3  # Start at morning
DAY_LENGTH = 60.0  # 10 real minutes = 1 full day/night cycle

# Generate background layers
background_width = screen_width * 3
background_height = screen_height
cloud_layer = generate_clouds(background_width, background_height, SEED)
hill_layers = generate_hills(background_width, background_height, 2, SEED)
star_layer = generate_stars(background_width, background_height, SEED)

# Check for GPU at startup
if USE_GPU_GENERATION:
    if detect_gpu():
        print("GPU détecté et activé pour la génération de terrain!")
    else:
        print("Aucun GPU compatible détecté, utilisation du CPU pour la génération.")
        USE_GPU_GENERATION = False

# Initialize main menu (after screen size is determined)
main_menu = MainMenu(screen_width, screen_height)

# --- Rendering Functions ---

def render_visible_chunks(screen, camera_x, camera_y, active_chunks, loaded_chunks, block_surfaces, machine_system):
    """Render only the visible chunks to improve performance."""
    rendered_chunk_surfaces = {}
    with chunk_lock: # Access loaded_chunks safely
        for chunk_x, chunk_y in active_chunks:
            if (chunk_x, chunk_y) in loaded_chunks:
                chunk_data = loaded_chunks[(chunk_x, chunk_y)]
                rendered_chunk_surfaces[(chunk_x, chunk_y)] = render_chunk(
                    chunk_data, chunk_x, chunk_y, camera_x, camera_y,
                    mining_animation, block_surfaces, machine_system,
                    multi_block_system
                )

    for (chunk_x, chunk_y), surface in rendered_chunk_surfaces.items():
        chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
        chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
        screen.blit(surface, (chunk_screen_x, chunk_screen_y))

def render_debug_chunks(screen, camera_x, camera_y, active_chunks):
    """Render chunk borders for debugging purposes."""
    for chunk_x, chunk_y in active_chunks:
        chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
        chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
        chunk_rect = pygame.Rect(chunk_screen_x, chunk_screen_y,
                                 config.CHUNK_SIZE * config.PIXEL_SIZE,
                                 config.CHUNK_SIZE * config.PIXEL_SIZE)
        pygame.draw.rect(screen, (0, 255, 0), chunk_rect, 1)  # Green border for chunks

# Main Game Loop
if __name__ == '__main__':
    running = True
    in_menu = True  # Start in the main menu

    while running:
        if in_menu:
            # Handle main menu
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE: # Handle resize in menu too
                    screen_width, screen_height = event.size
                    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                    main_menu.update_screen_size(screen_width, screen_height) # Update menu size
                else:
                    action = main_menu.handle_input(event)
                    if action == "Start Game":
                        in_menu = False  # Exit menu and start the game
                        # Ensure game UIs are updated to current screen size when starting
                        machine_ui.update_screen_size(screen_width, screen_height)
                        crafting_ui.update_screen_size(screen_width, screen_height)
                        storage_ui.update_screen_size(screen_width, screen_height)
                    elif action == "Open Settings": # Handle the new action
                        print("Settings button clicked! (Implement settings screen here)")
                        # Placeholder: Currently does nothing but print.
                        # You would typically set a new state like 'in_settings_menu = True'
                        # and handle that state similar to 'in_menu'.
                    elif action == "Quit":
                        running = False

            # Draw main menu
            main_menu.draw(screen)
            pygame.display.flip()
            clock.tick(config.FPS_CAP)
        else:
            profiler = cProfile.Profile()
            profiler.enable()
            last_time = time.time()
            
            # For laser drawing
            laser_active = False
            laser_points = []

            while running:
                # Calculate delta time
                current_time = time.time()
                dt = current_time - last_time
                if dt == 0:
                    dt = 1 / config.FPS_CAP  # Avoid division by zero
                last_time = current_time
                
                # Handle events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        save_world_to_file(SAVE_FILE, storage_system, (player.x, player.y), conveyor_system, extractor_system, multi_block_system, auto_miner_system)
                        running = False
                    
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_o:  # Press 'O' to manually save the map
                            save_world_to_file(SAVE_FILE, storage_system, (player.x, player.y), conveyor_system, extractor_system, multi_block_system, auto_miner_system)
                        elif event.key == pygame.K_l:  # Press 'L' to manually load the map
                            success, loaded_player_pos = load_world_from_file(SAVE_FILE, storage_system, conveyor_system, extractor_system, multi_block_system, auto_miner_system)
                            if success:
                                player.x, player.y = loaded_player_pos
                                camera_x = player.x - screen_width // 2
                                camera_y = player.y - screen_height // 2
                                print("World reloaded.")
                            else:
                                print("Failed to reload world.")
                        elif event.key == pygame.K_c:  # Press 'C' to toggle player collision
                            player.toggle_collision()
                            print(f"Player collision {'enabled' if player.collision_enabled else 'disabled'}.")
                        elif event.key == pygame.VIDEORESIZE:
                            screen_width, screen_height = event.size
                            screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                            machine_ui.update_screen_size(screen_width, screen_height)
                            crafting_ui.update_screen_size(screen_width, screen_height)
                            storage_ui.update_screen_size(screen_width, screen_height)
                        elif event.key == pygame.K_1:  # Number keys to select hotbar slots
                            inventory.select_slot(0)
                        elif event.key == pygame.K_2:
                            inventory.select_slot(1)
                        elif event.key == pygame.K_3:
                            inventory.select_slot(2)
                        elif event.key == pygame.K_4:
                            inventory.select_slot(3)
                        elif event.key == pygame.K_5:
                            inventory.select_slot(4)
                        elif event.key == pygame.K_6:
                            inventory.select_slot(5)
                        elif event.key == pygame.K_7:
                            inventory.select_slot(6)
                        elif event.key == pygame.K_8:
                            inventory.select_slot(7)
                        elif event.key == pygame.K_9:
                            inventory.select_slot(8)
                        elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                            VIEW_DISTANCE_MULTIPLIER = min(100.0, VIEW_DISTANCE_MULTIPLIER + 2)
                            print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                            print(f"Max active chunks: {MAX_ACTIVE_CHUNKS}")
                        elif event.key == pygame.K_MINUS:
                            VIEW_DISTANCE_MULTIPLIER = max(1.0, VIEW_DISTANCE_MULTIPLIER - 2)
                            print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                            print(f"Max active chunks: {MAX_ACTIVE_CHUNKS}")
                        elif event.key == pygame.K_i:  # Toggle debug mode
                            DEBUG_MODE = not DEBUG_MODE
                        elif event.key == pygame.K_p:  # Add ore processor to inventory
                            inventory.add_item(config.ORE_PROCESSOR)
                            print("Ore processor added to inventory!")
                        elif event.key == pygame.K_t:  # Add crafting table to inventory
                            inventory.add_item(config.CRAFTING_TABLE)
                            print("Crafting table added to inventory!")
                        elif event.key == pygame.K_n:  # Press 'S' to add storage chest to inventory
                            inventory.add_item(config.STORAGE_CHEST)
                            print("Storage chest added to inventory!")
                        elif event.key == pygame.K_v:  # Press 'V' to add conveyor belt to inventory
                            inventory.add_item(config.CONVEYOR_BELT)
                            print("Conveyor belt added to inventory!")
                        elif event.key == pygame.K_b:  # Press 'B' to add vertical conveyor to inventory
                            inventory.add_item(config.VERTICAL_CONVEYOR)
                            print("Vertical conveyor added to inventory!")
                        elif event.key == pygame.K_x:  # Press 'X' to add item extractor to inventory
                            inventory.add_item(config.ITEM_EXTRACTOR)
                            print("Item extractor added to inventory!")
                        elif event.key == pygame.K_m:  # Add Auto Miner to inventory
                            inventory.add_item(config.AUTO_MINER)
                            print("Auto Miner added to inventory!")
                        elif event.key == pygame.K_ESCAPE:  # Close active UIs when ESC is pressed
                            MainMenu(screen_width, screen_height).draw(screen)
                            if machine_system.get_active_machine() is not None:
                                machine_system.close_machine_ui()
                            if crafting_system.get_active_table() is not None:
                                crafting_system.close_table_ui()
                            active_storage = None
                        elif event.key == pygame.K_z:  # Touche Z pour activer/désactiver le mode de placement rapide
                            conveyor_placement_active = not conveyor_placement_active
                            conveyor_placement_preview = []
                            print(f"Mode de placement rapide de convoyeurs {'activé' if conveyor_placement_active else 'désactivé'}")
                        elif event.key == pygame.K_r:  # Touche R pour changer le mode de placement
                            conveyor_placement_mode = (conveyor_placement_mode + 1) % 3
                            mode_names = ["Ligne Droite", "Diagonale", "Zig-Zag"]
                            print(f"Mode de placement: {mode_names[conveyor_placement_mode]}")
                        elif event.key == pygame.K_TAB:  # Tab pour changer la direction
                            conveyor_placement_direction = (conveyor_placement_direction + 1) % 4
                            directions = ["Droite", "Bas", "Gauche", "Haut"]
                            print(f"Direction de placement: {directions[conveyor_placement_direction]}")
                    
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        # Calculate world PIXEL coordinates from mouse click
                        world_pixel_x = mouse_x + camera_x
                        world_pixel_y = mouse_y + camera_y
                        # Convert pixel coordinates to world BLOCK coordinates
                        block_x = int(world_pixel_x // config.PIXEL_SIZE)
                        block_y = int(world_pixel_y // config.PIXEL_SIZE)

                        if event.button == 1:  # Left button
                            # --- Interaction logic ---
                            # Use block_x, block_y (world block coords) for interactions
                            block_at_click = get_block_at(block_x, block_y)

                            # Check if clicking on a machine or crafting table
                            if block_at_click == config.ORE_PROCESSOR or machine_system.is_machine_position(block_x, block_y):
                                # ... (rest of machine UI logic uses block_x, block_y) ...
                                pass
                            elif block_at_click == config.CRAFTING_TABLE or crafting_system.is_table_position(block_x, block_y):
                                pass
                                # ... (rest of crafting UI logic uses block_x, block_y) ...

                            # Add check for storage chests
                            elif block_at_click == config.STORAGE_CHEST or storage_system.is_storage_position(block_x, block_y):
                                # ... (rest of storage UI logic uses block_x, block_y) ...
                                pass
                            # --- UI Click Handling (uses screen coords: mouse_x, mouse_y) ---
                            # ... (storage UI click) ...
                            # ... (machine UI click) ...
                            # ... (crafting UI click) ...
                            # ... (inventory drag start) ...

                        elif event.button == 3:  # Right button (Placement)
                            # Use block_x, block_y (world block coords) for placement checks and calls
                            if get_block_at(block_x, block_y) == config.EMPTY:
                                selected_item = inventory.get_selected_item()
                                if selected_item:
                                    block_type_to_place, _ = selected_item
                                    print(f"[DEBUG] Attempting to place block type {block_type_to_place} at Block({block_x}, {block_y})")

                                    # --- Conveyor Placement Preview Logic ---
                                    if conveyor_placement_active and (
                                        block_type_to_place == config.CONVEYOR_BELT or block_type_to_place == config.VERTICAL_CONVEYOR
                                    ):
                                        if conveyor_placement_preview:
                                            placed_count = 0
                                            # conveyor_placement_preview should contain world BLOCK coords
                                            for place_block_x, place_block_y in conveyor_placement_preview:
                                                if inventory.get_item_count(block_type_to_place) > 0:
                                                    # Register multi-block using block coords
                                                    if multi_block_system.register_multi_block(place_block_x, place_block_y, block_type_to_place):
                                                        # Set block using block coords
                                                        if set_block_at(place_block_x, place_block_y, block_type_to_place):
                                                            conveyor_system.register_conveyor(place_block_x, place_block_y, conveyor_placement_direction)
                                                            inventory.remove_item(inventory.selected_slot, 1)
                                                            # Mark chunk modified (uses chunk coords, derived from block coords)
                                                            # mark_chunk_modified is called within set_block_at
                                                            placed_count += 1
                                                        else:
                                                             print(f"Placement failed: set_block_at returned false at {place_block_x},{place_block_y}")
                                                             multi_block_system.unregister_multi_block(place_block_x, place_block_y) # Undo registration
                                                    else:
                                                        print(f"Placement failed: register_multi_block failed at {place_block_x}, {place_block_y}")
                                                else:
                                                    print("Ran out of items during conveyor placement.")
                                                    break
                                            print(f"Placed {placed_count} conveyor sections.")
                                            conveyor_placement_preview = []
                                        else:
                                             print("[DEBUG] Conveyor placement active but no preview available.")


                                    # --- Multi-Block Placement (Example: Ore Processor) ---
                                    elif block_type_to_place == config.ORE_PROCESSOR:
                                        width, height = config.BLOCKS[block_type_to_place].get("size", (1, 1))
                                        space_available = True
                                        affected_chunks = set()

                                        # Check if space is available using block coords
                                        for dx in range(width):
                                            for dy in range(height):
                                                check_block_x = block_x + dx
                                                check_block_y = block_y + dy
                                                if get_block_at(check_block_x, check_block_y) != config.EMPTY:
                                                    space_available = False
                                                    print(f"[DEBUG] Placement failed: Block at ({check_block_x}, {check_block_y}) is not empty.")
                                                    break
                                            if not space_available:
                                                break

                                        if space_available:
                                            # Place all blocks using block coords
                                            placement_successful = True
                                            placed_blocks_coords = [] # Keep track of placed blocks for potential rollback
                                            for dx in range(width):
                                                for dy in range(height):
                                                    place_block_x = block_x + dx
                                                    place_block_y = block_y + dy
                                                    if set_block_at(place_block_x, place_block_y, block_type_to_place):
                                                        placed_blocks_coords.append((place_block_x, place_block_y))
                                                        chunk_cx, chunk_cy = get_chunk_coords(place_block_x, place_block_y)
                                                        affected_chunks.add((chunk_cx, chunk_cy)) # set_block_at already marks modified
                                                    else:
                                                        placement_successful = False
                                                        print(f"ERROR: Failed to place part of multi-block at ({place_block_x},{place_block_y})")
                                                        break
                                                if not placement_successful:
                                                    break

                                            if placement_successful:
                                                # Register the machine/structure at its origin (using block coords)
                                                machine_system.register_machine(block_x, block_y)
                                                inventory.remove_item(inventory.selected_slot)
                                                print(f"[DEBUG] Placed multi-block type {block_type_to_place} at Block({block_x}, {block_y}).")
                                            else:
                                                # Rollback: Set placed blocks back to empty
                                                print(f"Rolling back failed multi-block placement at Block({block_x},{block_y})")
                                                for rb_x, rb_y in placed_blocks_coords:
                                                    set_block_at(rb_x, rb_y, config.EMPTY)
                                        else:
                                            print(f"[DEBUG] Not enough space to place multi-block type {block_type_to_place} at Block({block_x}, {block_y})")


                                    # --- Single Block Placement ---
                                    # Use block_x, block_y for all checks and placements
                                    elif block_type_to_place == config.CRAFTING_TABLE:
                                        if set_block_at(block_x, block_y, block_type_to_place):
                                            crafting_system.register_table(block_x, block_y)
                                            inventory.remove_item(inventory.selected_slot)
                                    elif block_type_to_place == config.STORAGE_CHEST:
                                        if set_block_at(block_x, block_y, block_type_to_place):
                                            if multi_block_system.register_multi_block(block_x, block_y, block_type_to_place):
                                                storage_system.register_storage(block_x, block_y)
                                                inventory.remove_item(inventory.selected_slot)
                                            else:
                                                set_block_at(block_x, block_y, config.EMPTY) # Revert
                                                print(f"Failed to register multi-block for storage chest at Block({block_x},{block_y})")
                                    elif block_type_to_place == config.CONVEYOR_BELT or block_type_to_place == config.VERTICAL_CONVEYOR:
                                        if set_block_at(block_x, block_y, block_type_to_place):
                                            if multi_block_system.register_multi_block(block_x, block_y, block_type_to_place):
                                                conveyor_system.register_conveyor(block_x, block_y)
                                                inventory.remove_item(inventory.selected_slot)
                                            else:
                                                set_block_at(block_x, block_y, config.EMPTY) # Revert
                                                print(f"Failed to register multi-block for conveyor at Block({block_x},{block_y})")
                                    elif block_type_to_place == config.ITEM_EXTRACTOR:
                                         if set_block_at(block_x, block_y, block_type_to_place):
                                            if multi_block_system.register_multi_block(block_x, block_y, block_type_to_place):
                                                extractor_system.register_extractor(block_x, block_y)
                                                extractor_system.set_direction(block_x, block_y, 0)
                                                inventory.remove_item(inventory.selected_slot)
                                            else:
                                                set_block_at(block_x, block_y, config.EMPTY) # Revert
                                                print(f"Failed to register multi-block for extractor at Block({block_x},{block_y})")
                                    elif block_type_to_place == config.AUTO_MINER:
                                        if set_block_at(block_x, block_y, block_type_to_place):
                                            auto_miner_system.register_miner(block_x, block_y)
                                            inventory.remove_item(inventory.selected_slot)
                                    else: # Default case for simple blocks
                                        if set_block_at(block_x, block_y, block_type_to_place):
                                            inventory.remove_item(inventory.selected_slot)
                                # ... (rest of right-click logic) ...

                    elif event.type == pygame.MOUSEBUTTONUP:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        dropped = False
                        
                        if inventory.dragged_item:
                            dropped = inventory.drop_item(mouse_x, mouse_y, screen_width, screen_height)
                            
                            if not dropped and machine_system.get_active_machine() is not None and machine_ui.is_point_in_ui(mouse_x, mouse_y):
                                machine_pos = machine_system.get_active_machine()
                                slot = machine_ui.get_slot_at_position(mouse_x, mouse_y)
                                
                                if slot == "input":
                                    item = inventory.dragged_item
                                    if machine_system.add_item_to_machine(machine_pos, item[0], item[1]):
                                        inventory.dragged_item = None
                                        inventory.drag_source = None
                                        inventory.drag_slot = None
                                        dropped = True
                            
                            if not dropped and crafting_system.get_active_table() is not None and crafting_ui.is_point_in_ui(mouse_x, mouse_y):
                                table_pos = crafting_system.get_active_table()
                                slot_info = crafting_ui.get_slot_at_position(mouse_x, mouse_y)
                                
                                if slot_info and slot_info[0] == "grid":
                                    _, grid_x, grid_y = slot_info
                                    item = inventory.dragged_item
                                    if crafting_system.add_item_to_grid(table_pos, grid_x, grid_y, item[0], item[1]):
                                        inventory.dragged_item = None
                                        inventory.drag_source = None
                                        inventory.drag_slot = None
                                        dropped = True
                            
                            if not dropped and active_storage is not None and storage_ui.is_point_in_ui(mouse_x, mouse_y) and inventory.dragged_item:
                                if storage_system.add_item_to_storage(*active_storage, inventory.dragged_item[0], inventory.dragged_item[1]):
                                    inventory.dragged_item = None
                                    inventory.drag_source = None
                                    inventory.drag_slot = None
                                    dropped = True
                            
                            if not dropped and inventory.drag_source == "storage" and inventory.dragged_item:
                                storage_system.add_item_to_storage(*inventory.drag_slot, inventory.dragged_item[0], inventory.dragged_item[1])
                                inventory.dragged_item = None
                                inventory.drag_source = None
                                inventory.drag_slot = None
                
                keys = pygame.key.get_pressed()
                player.update(dt, keys, check_collision)
                
                camera_x = player.x - screen_width // 2
                camera_y = player.y - screen_height // 2
                
                mouse_pressed = pygame.mouse.get_pressed()[0]
                if mouse_pressed and not inventory.dragged_item:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    laser_points = handle_mining(dt, mouse_x, mouse_y, player.x, player.y, camera_x, camera_y)
                    laser_active = len(laser_points) > 0
                else:
                    laser_active = False
                    laser_points = []
                
                if ENABLE_INFINITE_WORLD:
                    ensure_chunks_around_point(player.x, player.y, CHUNK_LOAD_RADIUS)
                    
                    if int(current_time) % 5 == 0 and int(current_time) != int(last_time):
                        print(f"Checking chunks to unload. {len(loaded_chunks)} chunks currently loaded.")
                        unload_distant_chunks(player.x, player.y, CHUNK_UNLOAD_DISTANCE)
                
                machine_system.update()
                
                conveyor_system.update(dt, storage_system, machine_system)
                
                extractor_system.update(dt)
                
                auto_miner_system.update(dt)  # Update the auto miners
                
                time_of_day += dt / DAY_LENGTH
                if time_of_day >= 1.0:
                    time_of_day -= 1.0
                
                # Clear the screen (e.g., with black or a dynamic sky color)
                screen.fill((0, 0, 0)) # Fill with black first

                draw_background(screen, camera_x, camera_y, time_of_day, background_width, background_height, 
                                cloud_layer, hill_layers, star_layer)
                
                active_chunks = get_active_chunks(player.x, player.y, screen_width, screen_height, 
                                                  VIEW_DISTANCE_MULTIPLIER, MAX_ACTIVE_CHUNKS)
                render_visible_chunks(screen, camera_x, camera_y, active_chunks, loaded_chunks, block_surfaces, machine_system)
                
                if DEBUG_MODE:
                    render_debug_chunks(screen, camera_x, camera_y, active_chunks)

                player.draw(screen, camera_x, camera_y)
                
                if laser_active and len(laser_points) >= 2:
                    start_point = (player.x + player.width // 2 - camera_x,
                                player.y + player.height // 2 - camera_y)
                    pygame.draw.line(screen, (255, 0, 0), start_point, laser_points[0], 3)
                
                inventory.draw(screen, screen_width, screen_height)
                
                active_machine = machine_system.get_active_machine()
                if active_machine:
                    machine_data = machine_system.get_machine_data(active_machine)
                    progress = machine_system.get_machine_progress(active_machine)
                    machine_ui.draw(screen, machine_data, progress, inventory.dragged_item)
                
                active_table = crafting_system.get_active_table()
                if active_table:
                    table_data = crafting_system.get_table_data(active_table)
                    crafting_ui.draw(screen, table_data, inventory.dragged_item)
                
                if active_storage:
                    storage_data = storage_system.get_storage_at(*active_storage)
                    storage_ui.draw(screen, storage_data, inventory.dragged_item)
                
                conveyor_system.draw_items(screen, camera_x, camera_y, block_surfaces)
                
                if conveyor_placement_active and inventory.get_selected_item():
                    selected_type = inventory.get_selected_item()[0]
                    if selected_type in [config.CONVEYOR_BELT, config.VERTICAL_CONVEYOR]:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        # Calculate target block from mouse screen coords
                        world_pixel_x = mouse_x + camera_x
                        world_pixel_y = mouse_y + camera_y
                        target_block_x = int(world_pixel_x // config.PIXEL_SIZE)
                        target_block_y = int(world_pixel_y // config.PIXEL_SIZE)

                        width, height = multi_block_system.block_sizes.get(selected_type, (1, 1)) # Default to 1x1 if not found

                        conveyor_placement_preview = [] # List of world BLOCK coords
                        count_available = inventory.get_selected_item()[1]
                        max_length = min(20, count_available) # Limit preview length

                        # Calculate preview based on BLOCK coordinates
                        if conveyor_placement_mode == 0: # Straight Line
                            dx, dy = 0, 0
                            if conveyor_placement_direction == 0: dx = width # Move right by block width
                            elif conveyor_placement_direction == 1: dy = height # Move down by block height
                            elif conveyor_placement_direction == 2: dx = -width # Move left by block width
                            elif conveyor_placement_direction == 3: dy = -height # Move up by block height

                            for i in range(max_length):
                                next_block_x = target_block_x + i * dx
                                next_block_y = target_block_y + i * dy

                                # Check space for the entire block footprint
                                space_available = True
                                for check_dx in range(width):
                                    for check_dy in range(height):
                                        check_x = next_block_x + check_dx
                                        check_y = next_block_y + check_dy
                                        # Check if any part of the footprint is occupied
                                        if get_block_at(check_x, check_y) != config.EMPTY:
                                            space_available = False
                                            break
                                    if not space_available:
                                        break

                                if space_available:
                                    conveyor_placement_preview.append((next_block_x, next_block_y))
                                else:
                                    break # Stop preview if space is blocked

                        elif conveyor_placement_mode == 1: # Diagonal (Assuming width=height for simplicity here)
                            # This mode might need refinement if width != height
                            step_x, step_y = 0, 0
                            if conveyor_placement_direction == 0: step_x, step_y = width, height   # Down-Right
                            elif conveyor_placement_direction == 1: step_x, step_y = -width, height  # Down-Left
                            elif conveyor_placement_direction == 2: step_x, step_y = -width, -height # Up-Left
                            elif conveyor_placement_direction == 3: step_x, step_y = width, -height  # Up-Right

                            for i in range(max_length):
                                next_block_x = target_block_x + i * step_x
                                next_block_y = target_block_y + i * step_y

                                # Check space (same as straight line)
                                space_available = True
                                for check_dx in range(width):
                                    for check_dy in range(height):
                                        check_x = next_block_x + check_dx
                                        check_y = next_block_y + check_dy
                                        if get_block_at(check_x, check_y) != config.EMPTY:
                                            space_available = False
                                            break
                                    if not space_available:
                                        break

                                if space_available:
                                    conveyor_placement_preview.append((next_block_x, next_block_y))
                                else:
                                    break
                        # Add ZigZag mode (mode 2) if needed

                        # --- Render Preview ---
                        preview_surface = None
                        if conveyor_placement_preview:
                            # Create a surface for one block preview
                            preview_block_surf = pygame.Surface((width * config.PIXEL_SIZE, height * config.PIXEL_SIZE), pygame.SRCALPHA)
                            preview_color = list(config.BLOCKS[selected_type]["color"]) + [128] # Semi-transparent color
                            preview_block_surf.fill(preview_color)

                            # Draw direction arrow on the preview surface
                            arrow_color = (0, 0, 0, 200)
                            center_px_x = width * config.PIXEL_SIZE // 2
                            center_px_y = height * config.PIXEL_SIZE // 2
                            arrow_size_px = min(width, height) * config.PIXEL_SIZE // 3

                            # Arrow points based on conveyor_placement_direction
                            if conveyor_placement_direction == 0: # Right
                                pygame.draw.polygon(preview_block_surf, arrow_color, [
                                    (center_px_x - arrow_size_px//2, center_px_y - arrow_size_px//2),
                                    (center_px_x + arrow_size_px//2, center_px_y),
                                    (center_px_x - arrow_size_px//2, center_px_y + arrow_size_px//2)
                                ])
                            elif conveyor_placement_direction == 1: # Down
                                pygame.draw.polygon(preview_block_surf, arrow_color, [
                                    (center_px_x - arrow_size_px//2, center_px_y - arrow_size_px//2),
                                    (center_px_x + arrow_size_px//2, center_px_y - arrow_size_px//2),
                                    (center_px_x, center_px_y + arrow_size_px//2)
                                ])
                            elif conveyor_placement_direction == 2: # Left
                                pygame.draw.polygon(preview_block_surf, arrow_color, [
                                    (center_px_x + arrow_size_px//2, center_px_y - arrow_size_px//2),
                                    (center_px_x - arrow_size_px//2, center_px_y),
                                    (center_px_x + arrow_size_px//2, center_px_y + arrow_size_px//2)
                                ])
                            elif conveyor_placement_direction == 3: # Up
                                pygame.draw.polygon(preview_block_surf, arrow_color, [
                                    (center_px_x - arrow_size_px//2, center_px_y + arrow_size_px//2),
                                    (center_px_x + arrow_size_px//2, center_px_y + arrow_size_px//2),
                                    (center_px_x, center_px_y - arrow_size_px//2)
                                ])

                            # Blit the preview surface for each block in the preview list
                            for block_render_x, block_render_y in conveyor_placement_preview:
                                # Convert block world coords to screen pixel coords
                                screen_x = block_render_x * config.PIXEL_SIZE - camera_x
                                screen_y = block_render_y * config.PIXEL_SIZE - camera_y
                                screen.blit(preview_block_surf, (screen_x, screen_y))

                # Draw dragged item last so it's on top
                inventory.draw_dragged_item(screen)
                
                # Draw performance stats if enabled
                if PERFORMANCE_MONITOR:
                    draw_performance_stats(screen, dt, len(active_chunks), len(loaded_chunks), fps_font)
                
                # Update the display
                pygame.display.flip()
                
                # Cap the frame rate
                clock.tick(config.FPS_CAP)
            
            # --- End of main game loop ---
            
            # Save world on exit
            save_world_to_file(SAVE_FILE, storage_system, (player.x, player.y), conveyor_system, extractor_system, multi_block_system, auto_miner_system)
            
            # Stop worker threads
            stop_chunk_workers(chunk_workers)
            
            # Disable and print profiler stats if debug mode was on
            profiler.disable()
            if DEBUG_MODE:
                print("\n--- Profiler Stats ---")
                profiler.print_stats(sort='cumulative')
            
            # Quit Pygame and exit
            pygame.quit()
            sys.exit()



