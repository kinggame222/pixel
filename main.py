import pygame
import cProfile
import time
import sys
import os
import random
import numpy as np

# Import core modules
from core import config
from world.chunks import (
    get_block_at, set_block_at, generate_chunk, get_chunk_coords, start_chunk_workers,
    stop_chunk_workers, ensure_chunks_around_point, unload_distant_chunks, get_active_chunks,
    save_world_to_file, load_world_from_file, loaded_chunks, mark_chunk_modified, chunk_cache
)
from entities.player import Player
from ui.inventory import Inventory
from ui.machine_ui import MachineUI
from systems.machine_system import MachineSystem
from utils.rendering import create_block_surfaces, render_chunk, draw_performance_stats
from systems.crafting_system import CraftingSystem
from ui.crafting_ui import CraftingUI

# --- Game Settings ---
DEBUG_MODE = True          # Enable debug mode
SAVE_FILE = "world.json"   # Path to the save file
SEED = 1                   # World generation seed
ENABLE_CHUNK_CACHE = True  # Enable chunk caching for performance
MAX_ACTIVE_CHUNKS = 200    # Maximum active chunks to render
PERFORMANCE_MONITOR = True # Show performance stats 
VIEW_DISTANCE_MULTIPLIER = 2.0  # View distance multiplier
CHUNK_LOAD_RADIUS = 5      # Radius of chunks to keep loaded around player
CHUNK_UNLOAD_DISTANCE = 5  # Distance in chunks to unload chunks
CHUNK_GEN_THREAD_COUNT = 2 # Number of threads for chunk generation
ENABLE_INFINITE_WORLD = True  # Enable infinite world generation

def find_spawn_position():
    """Finds a safe spawn position for the player above the ground."""
    spawn_chunk_x, spawn_chunk_y = 0, 0  # Start at the origin chunk
    
    if (spawn_chunk_x, spawn_chunk_y) not in loaded_chunks:
        generate_chunk(spawn_chunk_x, spawn_chunk_y, SEED)
    
    chunk = loaded_chunks[(spawn_chunk_x, spawn_chunk_y)]
    for y in range(config.CHUNK_SIZE):
        for x in range(config.CHUNK_SIZE):
            if chunk[y, x] == config.EMPTY:
                return x * config.PIXEL_SIZE, y * config.PIXEL_SIZE
    
    return 0, 0  # Default to (0, 0) if no empty space is found

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
    
    # Calculate world position
    world_x = mouse_x + camera_x
    world_y = mouse_y + camera_y
    
    # Calculate direction vector from player to mouse
    direction_x = world_x - player_x
    direction_y = world_y - player_y
    distance = ((direction_x ** 2) + (direction_y ** 2)) ** 0.5
    if distance == 0: distance = 1  # Avoid division by zero
    
    # Normalize the direction vector
    direction_x /= distance
    direction_y /= distance
    
    # Laser range (in blocks)
    laser_range = 15
    
    # Dig along the laser direction
    for i in range(laser_range):
        dig_x = int((player_x + direction_x * i * config.PIXEL_SIZE) // config.PIXEL_SIZE)
        dig_y = int((player_y + direction_y * i * config.PIXEL_SIZE) // config.PIXEL_SIZE)
        
        # Check if dig position has a block
        block_type = get_block_at(dig_x, dig_y)
        if block_type != config.EMPTY:
            block_index = (dig_y, dig_x)
            
            # Get block hardness
            if block_type in config.BLOCKS:
                hardness = config.BLOCKS[block_type].get("hardness", 1)
                if hardness < 0:  # Unbreakable
                    break
            else:
                break  # Skip if block type is not in BLOCKS
            
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
                
                if block_type in config.BLOCKS and "drops" in config.BLOCKS[block_type]:
                    drops = config.BLOCKS[block_type]["drops"]
                    for drop_id_str, probability in drops.items():
                        try:
                            drop_id = int(drop_id_str)
                        except ValueError:
                            print(f"Invalid drop ID: {drop_id_str}")
                            continue
                        
                        if drop_id in config.BLOCKS and random.random() < probability:
                            dropped_block = drop_id
                            break  # Only generate one drop
                
                # Add the dropped block to the inventory
                if dropped_block != config.EMPTY:
                    if inventory.add_item(dropped_block):
                        set_block_at(dig_x, dig_y, config.EMPTY)
                    else:
                        # If inventory is full, keep the block
                        set_block_at(dig_x, dig_y, block_type)
                else:
                    set_block_at(dig_x, dig_y, config.EMPTY)
                
                mining_progress.pop(block_index, None)  # Remove progress
            
            laser_points.append((dig_x * config.PIXEL_SIZE + config.PIXEL_SIZE // 2 - camera_x,
                                dig_y * config.PIXEL_SIZE + config.PIXEL_SIZE // 2 - camera_y))
            break  # Stop at the first block hit
    
    return laser_points

# Initialize Pygame
pygame.init()
screen_width = 1200
screen_height = 1000
screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
pygame.display.set_caption(config.WINDOW_TITLE)
clock = pygame.time.Clock()
fps_font = pygame.font.SysFont("Consolas", 18)

# Create block surfaces
block_surfaces = create_block_surfaces()

# Initialize the machine system
machine_system = MachineSystem(get_block_at, set_block_at)

# Initialize machine UI
machine_ui = MachineUI(screen_width, screen_height, block_surfaces)

# Initialize crafting system and UI
crafting_system = CraftingSystem(get_block_at, set_block_at)
crafting_ui = CraftingUI(screen_width, screen_height, block_surfaces)

# Set random seed for world generation
random.seed(SEED)
np.random.seed(SEED)

# Start chunk generation worker threads
chunk_workers = start_chunk_workers(CHUNK_GEN_THREAD_COUNT, SEED)

# Initialize game state
if os.path.exists(SAVE_FILE):
    load_world_from_file(SAVE_FILE)
    
# Get initial player position
player_x, player_y = find_spawn_position()
player = Player(player_x, player_y)

# Initialize inventory
inventory = Inventory()

# Initialize camera position
camera_x = player_x - screen_width // 2
camera_y = player_y - screen_height // 2

# Initialize mining tracking
mining_progress = {}  # Dictionary to track mining progress for each block
mining_animation = {}  # Dictionary to store mining animation progress

# Generate initial chunks around the player
player_chunk_x, player_chunk_y = get_chunk_coords(int(player.x // config.PIXEL_SIZE), 
                                                 int(player.y // config.PIXEL_SIZE))
for dx in range(-3, 4):
    for dy in range(-3, 4):
        generate_chunk(player_chunk_x + dx, player_chunk_y + dy, SEED)

# Main Game Loop
if __name__ == '__main__':
    running = True
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
                save_world_to_file(SAVE_FILE)
                running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_o:  # Press 'O' to manually save the map
                    save_world_to_file(SAVE_FILE)
                elif event.key == pygame.K_l:  # Press 'L' to manually load the map
                    load_world_from_file(SAVE_FILE)
                elif event.key == pygame.K_c:  # Press 'C' to toggle player collision
                    player.toggle_collision()
                    print(f"Player collision {'enabled' if player.collision_enabled else 'disabled'}.")
                elif event.key == pygame.VIDEORESIZE:
                    screen_width, screen_height = event.size
                    screen = pygame.display.set_mode((screen_width, screen_height), pygame.RESIZABLE)
                    machine_ui.update_screen_size(screen_width, screen_height)
                    crafting_ui.update_screen_size(screen_width, screen_height)
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
                    VIEW_DISTANCE_MULTIPLIER = min(3.0, VIEW_DISTANCE_MULTIPLIER + 0.5)
                    print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                elif event.key == pygame.K_MINUS:
                    VIEW_DISTANCE_MULTIPLIER = max(1.0, VIEW_DISTANCE_MULTIPLIER - 0.5)
                    print(f"View distance: {VIEW_DISTANCE_MULTIPLIER:.1f}x")
                elif event.key == pygame.K_i:  # Toggle debug mode
                    DEBUG_MODE = not DEBUG_MODE
                elif event.key == pygame.K_p:  # Add ore processor to inventory
                    inventory.add_item(config.ORE_PROCESSOR)
                    print("Ore processor added to inventory!")
                elif event.key == pygame.K_t:  # Add crafting table to inventory
                    inventory.add_item(config.CRAFTING_TABLE)
                    print("Crafting table added to inventory!")
                elif event.key == pygame.K_ESCAPE:  # Close active UIs when ESC is pressed
                    if machine_system.get_active_machine() is not None:
                        machine_system.close_machine_ui()
                    if crafting_system.get_active_table() is not None:
                        crafting_system.close_table_ui()
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                world_x = mouse_x + camera_x
                world_y = mouse_y + camera_y
                block_x = int(world_x // config.PIXEL_SIZE)
                block_y = int(world_y // config.PIXEL_SIZE)
                
                if event.button == 1:  # Left button
                    # Check if clicking on a machine or crafting table
                    if get_block_at(block_x, block_y) == config.ORE_PROCESSOR or machine_system.is_machine_position(block_x, block_y):
                        machine_origin = machine_system.get_machine_origin(block_x, block_y)
                        if machine_origin:
                            machine_system.open_machine_ui(*machine_origin)
                            # Close the crafting UI if it's open
                            crafting_system.close_table_ui()
                        else:
                            machine_system.register_machine(block_x, block_y)
                            machine_system.open_machine_ui(block_x, block_y)
                            crafting_system.close_table_ui()
                    elif get_block_at(block_x, block_y) == config.CRAFTING_TABLE or crafting_system.is_table_position(block_x, block_y):
                        table_origin = crafting_system.get_table_origin(block_x, block_y)
                        if table_origin:
                            crafting_system.open_table_ui(*table_origin)
                            # Close the machine UI if it's open
                            machine_system.close_machine_ui()
                        else:
                            crafting_system.register_table(block_x, block_y)
                            crafting_system.open_table_ui(block_x, block_y)
                            machine_system.close_machine_ui()
                    
                    # Check for close button clicks in the machine UI
                    if machine_system.get_active_machine() is not None:
                        if machine_ui.is_close_button_clicked(mouse_x, mouse_y):
                            machine_system.close_machine_ui()
                    
                    # Check for close button clicks in the crafting UI
                    if crafting_system.get_active_table() is not None:
                        if crafting_ui.is_close_button_clicked(mouse_x, mouse_y):
                            crafting_system.close_table_ui()
                    
                    # Handle inventory drag start
                    if inventory.start_drag(mouse_x, mouse_y, screen_width, screen_height):
                        pass  # Item was picked up from inventory
                    
                    # Add crafting table UI interaction
                    if (crafting_system.get_active_table() is not None and 
                        crafting_ui.is_point_in_ui(mouse_x, mouse_y)):
                        table_pos = crafting_system.get_active_table()
                        table_data = crafting_system.get_table_data(table_pos)
                        slot_info = crafting_ui.get_slot_at_position(mouse_x, mouse_y)
                        
                        if slot_info:
                            slot_type, slot_x, slot_y = slot_info
                            
                            if slot_type == "grid" and table_data["grid"][slot_y][slot_x] is not None:
                                inventory.dragged_item = table_data["grid"][slot_y][slot_x]
                                inventory.drag_source = "crafting_grid"
                                inventory.drag_slot = (table_pos, slot_x, slot_y)
                                crafting_system.take_item_from_grid(table_pos, slot_x, slot_y)
                            
                            elif slot_type == "output" and table_data["output"] is not None:
                                inventory.dragged_item = table_data["output"]
                                inventory.drag_source = "crafting_output"
                                inventory.drag_slot = table_pos
                                crafting_system.take_output_item(table_pos)
                
                elif event.button == 3:  # Right button
                    if machine_system.get_active_machine() is not None and machine_ui.is_point_in_ui(mouse_x, mouse_y):
                        machine_pos = machine_system.get_active_machine()
                        slot = machine_ui.get_slot_at_position(mouse_x, mouse_y)
                        
                        if slot == "input":
                            selected_item = inventory.get_selected_item()
                            if selected_item:
                                if machine_system.add_item_to_machine(machine_pos, selected_item[0], 1):
                                    inventory.remove_item(inventory.selected_slot)
                        
                        elif slot == "output":
                            item = machine_system.take_item_from_machine(machine_pos, output_slot=True)
                            if item:
                                block_type, count = item
                                inventory.add_item(block_type, count)
                    
                    elif get_block_at(block_x, block_y) == config.EMPTY:
                        selected_item = inventory.get_selected_item()
                        if selected_item:
                            block_type, _ = selected_item
                            
                            if block_type == config.ORE_PROCESSOR:
                                width, height = machine_system.get_machine_size(config.ORE_PROCESSOR)
                                space_available = True
                                for dx in range(width):
                                    for dy in range(height):
                                        check_x = block_x + dx
                                        check_y = block_y + dy
                                        if get_block_at(check_x, check_y) != config.EMPTY:
                                            space_available = False
                                            break
                                    if not space_available:
                                        break
                                
                                if space_available:
                                    set_block_at(block_x, block_y, block_type)
                                    machine_system.register_machine(block_x, block_y)
                                    inventory.remove_item(inventory.selected_slot)
                                    chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
                                    mark_chunk_modified(chunk_x, chunk_y)
                            elif block_type == config.CRAFTING_TABLE:
                                set_block_at(block_x, block_y, block_type)
                                crafting_system.register_table(block_x, block_y)
                                inventory.remove_item(inventory.selected_slot)
                                chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
                                mark_chunk_modified(chunk_x, chunk_y)
                            else:
                                set_block_at(block_x, block_y, block_type)
                                inventory.remove_item(inventory.selected_slot)
                                chunk_x, chunk_y = get_chunk_coords(block_x, block_y)
                                mark_chunk_modified(chunk_x, chunk_y)
                    
                    if crafting_system.get_active_table() is not None and crafting_ui.is_point_in_ui(mouse_x, mouse_y):
                        table_pos = crafting_system.get_active_table()
                        slot_info = crafting_ui.get_slot_at_position(mouse_x, mouse_y)
                        
                        if slot_info:
                            slot_type, slot_x, slot_y = slot_info
                            
                            if slot_type == "grid":
                                selected_item = inventory.get_selected_item()
                                if selected_item:
                                    block_type, count = selected_item
                                    if crafting_system.add_item_to_grid(table_pos, slot_x, slot_y, block_type, 1):
                                        inventory.remove_item(inventory.selected_slot, 1)
                            
                            elif slot_type == "output":
                                output_item = crafting_system.take_output_item(table_pos)
                                if output_item:
                                    block_type, count = output_item
                                    inventory.add_item(block_type, count)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                dropped = False  # Initialize the dropped flag
                
                # Only proceed with dropping if we actually have an item being dragged
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
                            item = inventory.dragged_item  # This is already checked to be non-None at the beginning
                            if crafting_system.add_item_to_grid(table_pos, grid_x, grid_y, item[0], item[1]):
                                inventory.dragged_item = None
                                inventory.drag_source = None
                                inventory.drag_slot = None
                                dropped = True
                    
                    if not dropped and inventory.drag_source:
                        if inventory.drag_source == "input":
                            machine_system.add_item_to_machine(inventory.drag_slot, inventory.dragged_item[0], inventory.dragged_item[1])
                        elif inventory.drag_source == "output":
                            machine_data = machine_system.get_machine_data(inventory.drag_slot)
                            machine_data["output"] = inventory.dragged_item
                        elif inventory.drag_source == "crafting_grid" and inventory.drag_slot:
                            table_pos, slot_x, slot_y = inventory.drag_slot
                            crafting_system.add_item_to_grid(table_pos, slot_x, slot_y, 
                                                            inventory.dragged_item[0], 
                                                            inventory.dragged_item[1])
                        
                        inventory.dragged_item = None
                        inventory.drag_source = None
                        inventory.drag_slot = None
        
        # Gather player input for movement
        keys = pygame.key.get_pressed()
        player.update(dt, keys, check_collision)
        
        # Update camera to follow player
        camera_x = player.x - screen_width // 2
        camera_y = player.y - screen_height // 2
        
        # Handle mining and laser
        mouse_pressed = pygame.mouse.get_pressed()[0]  # Left mouse button
        if mouse_pressed and not inventory.dragged_item:  # Don't mine while dragging items
            mouse_x, mouse_y = pygame.mouse.get_pos()
            laser_points = handle_mining(dt, mouse_x, mouse_y, player.x, player.y, camera_x, camera_y)
            laser_active = len(laser_points) > 0
        else:
            laser_active = False
            laser_points = []
        
        # Manage chunks for infinite world
        if ENABLE_INFINITE_WORLD:
            ensure_chunks_around_point(player.x, player.y, CHUNK_LOAD_RADIUS)
            if int(current_time) != int(last_time):
                unload_distant_chunks(player.x, player.y, CHUNK_UNLOAD_DISTANCE)
        
        # Update machines
        machine_system.update()
        
        # --- RENDERING ---
        screen.fill((0, 0, 0))
        
        active_chunks = get_active_chunks(player.x, player.y, screen_width, screen_height, 
                                         VIEW_DISTANCE_MULTIPLIER, MAX_ACTIVE_CHUNKS)
        
        rendered_chunks = {}
        for chunk_x, chunk_y in active_chunks:
            if (chunk_x, chunk_y) in loaded_chunks:
                chunk = loaded_chunks[(chunk_x, chunk_y)]
                rendered_chunks[(chunk_x, chunk_y)] = render_chunk(
                    chunk, chunk_x, chunk_y, camera_x, camera_y, 
                    mining_animation, block_surfaces, machine_system
                )
        
        for (chunk_x, chunk_y), surface in rendered_chunks.items():
            chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
            chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
            screen.blit(surface, (chunk_screen_x, chunk_screen_y))
        
        if DEBUG_MODE:
            for chunk_x, chunk_y in active_chunks:
                chunk_screen_x = chunk_x * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_x
                chunk_screen_y = chunk_y * config.CHUNK_SIZE * config.PIXEL_SIZE - camera_y
                chunk_rect = pygame.Rect(chunk_screen_x, chunk_screen_y, 
                                        config.CHUNK_SIZE * config.PIXEL_SIZE, 
                                        config.CHUNK_SIZE * config.PIXEL_SIZE)
                pygame.draw.rect(screen, (0, 255, 0), chunk_rect, 1)
        
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
        
        inventory.draw_dragged_item(screen)
        
        if PERFORMANCE_MONITOR:
            draw_performance_stats(screen, dt, len(active_chunks), len(chunk_cache), fps_font)
        
        pygame.display.flip()
        clock.tick(config.FPS_CAP)
    
    save_world_to_file(SAVE_FILE)
    stop_chunk_workers(chunk_workers)
    
    profiler.disable()
    if DEBUG_MODE:
        print("\n--- Profiler Stats ---")
        profiler.print_stats(sort='cumulative')
    
    pygame.quit()
    sys.exit()

