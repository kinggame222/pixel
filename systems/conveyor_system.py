import pygame
import time
import math
from core import config

class ConveyorItem:
    """Represents an item moving on a conveyor belt."""
    def __init__(self, item_id, count=1):
        self.item_id = item_id
        self.count = count
        self.position = 0.0  # Position on the belt (0.0 to 1.0)
        self.destination = None  # Used for vertical conveyors
    
    def advance(self, speed):
        """Move the item along the belt."""
        self.position += speed
        return self.position >= 1.0  # Return True if item reached the end

class ConveyorSystem:
    def __init__(self, get_block_at, set_block_at, multi_block_system=None):
        # Store references to world interaction functions
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        self.multi_block_system = multi_block_system
        
        # Dictionary of conveyors: {(x, y): ConveyorData}
        self.conveyors = {}
        self.items_on_conveyors = {}  # (x, y): [{"id": item_id, "progress": 0.0-1.0}, ...]
        
        # Get conveyor block IDs with fallbacks
        self.conveyor_id = getattr(config, "CONVEYOR_BELT", 17)
        self.vertical_conveyor_id = getattr(config, "VERTICAL_CONVEYOR", 18)
        self.extractor_id = getattr(config, "ITEM_EXTRACTOR", 19)
        
        # Conveyor belt speed (fractional distance per second)
        self.speed = 2.0  # Items move 2 blocks per second
        
        # Time tracking
        self.last_update = time.time()
    
    def register_conveyor(self, x, y, direction=0):
        """Register a new conveyor at the given position."""
        # Check if this is an origin block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin  # Use the origin coordinates
            
        block_type = self.get_block_at(x, y)
        is_vertical = block_type == self.vertical_conveyor_id
        
        # Create conveyor data
        self.conveyors[(x, y)] = {
            "direction": direction,  # 0: right, 1: down, 2: left, 3: up
            "items": [],  # List of ConveyorItem objects
            "is_vertical": is_vertical,
            "last_processed": time.time()
        }
        if (x, y) not in self.items_on_conveyors:
            self.items_on_conveyors[(x, y)] = []
        print(f"Conveyor registered at ({x}, {y}) with direction {direction}")
        return True
    
    def unregister_conveyor(self, x, y):
        """Unregister a conveyor at the given position."""
        self.conveyors.pop((x, y), None)
        self.items_on_conveyors.pop((x, y), None)
        print(f"Conveyor unregistered at ({x}, {y})")
    
    def place_item_on_conveyor(self, x, y, item_id, count=1):
        """Place an item on a conveyor belt."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) in self.conveyors:
            item = {"id": item_id, "progress": 0.0}
            self.items_on_conveyors.setdefault((x, y), []).append(item)
            print(f"Item {item_id} placed on conveyor at ({x}, {y})")
            return True
        return False
    
    def rotate_conveyor(self, x, y):
        """Rotate a conveyor to change its direction."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) in self.conveyors:
            # Update direction (0 → 1 → 2 → 3 → 0)
            self.conveyors[(x, y)]["direction"] = (self.conveyors[(x, y)]["direction"] + 1) % 4
            print(f"Conveyor at ({x}, {y}) rotated to direction {self.conveyors[(x, y)]['direction']}")
            return True
        return False
    
    def get_next_position(self, x, y, direction):
        """Get the next conveyor or machine position in the specified direction."""
        if direction == 0:  # Right
            next_pos = (x + 1, y)
        elif direction == 1:  # Down
            next_pos = (x, y + 1)
        elif direction == 2:  # Left
            next_pos = (x - 1, y)
        elif direction == 3:  # Up
            next_pos = (x, y - 1)
        else:
            return None
        
        # Check if next position is a valid destination
        block_type = self.get_block_at(*next_pos)
        if block_type in [self.conveyor_id, self.vertical_conveyor_id]:
            return next_pos
        
        # Check if next position is a valid machine or storage
        # This would need to interface with other systems like storage_system
        # For now, just return the position and let the update method handle it
        return next_pos
    
    def update(self, dt, storage_system=None, machine_system=None):
        """Update all conveyor belts and move items along them."""
        items_to_move = []  # Collect moves to process after iteration

        for (x, y), items in list(self.items_on_conveyors.items()):
            if not items:
                continue  # Skip if no items on this belt

            conveyor_data = self.conveyors.get((x, y))
            if not conveyor_data:
                continue  # Should not happen if items_on_conveyors is synced

            direction = conveyor_data["direction"]
            dx = [1, 0, -1, 0][direction]
            dy = [0, 1, 0, -1][direction]
            next_x, next_y = x + dx, y + dy

            # Process items in reverse order to handle removals safely
            for i in range(len(items) - 1, -1, -1):
                item = items[i]
                
                # Only advance progress if not blocked at the end (progress == 1.0)
                if item["progress"] < 1.0:
                    item["progress"] += self.speed * dt
                    item["progress"] = min(item["progress"], 1.0)  # Clamp to 1.0

                # If item reaches the end, attempt to transfer
                if item["progress"] >= 1.0:
                    can_transfer = False
                    next_block_type = self.get_block_at(next_x, next_y)
                    next_conveyor_data = self.conveyors.get((next_x, next_y))

                    # 1. Check if next block is a conveyor
                    if next_conveyor_data:
                        # Check if the target conveyor has space (simple check)
                        if len(self.items_on_conveyors.get((next_x, next_y), [])) < 4:
                            items_to_move.append(((x, y, i), (next_x, next_y), item["id"]))
                            can_transfer = True

                    # 2. Check if next block is a storage chest (using storage_system)
                    elif storage_system and storage_system.is_storage_position(next_x, next_y):
                        if storage_system.add_item_to_storage(next_x, next_y, item["id"], 1):
                            items.pop(i)  # Remove item if successfully added
                            can_transfer = True

                    # 3. Check if next block is a machine (using machine_system)
                    elif machine_system and machine_system.is_machine_position(next_x, next_y):
                        machine_origin = machine_system.get_machine_origin(next_x, next_y)
                        if machine_origin:
                            if machine_system.add_item_to_machine(machine_origin, item["id"], 1):
                                items.pop(i)  # Remove item if successfully added
                                can_transfer = True

                    # If transfer happened (or item was removed), continue to next item
                    if can_transfer:
                        continue

        # Process the collected moves
        items_removed_from_source = {}  # Track removals to avoid index errors
        for (source_x, source_y, source_index), (dest_x, dest_y), item_id in items_to_move:
            source_key = (source_x, source_y)
            current_source_items = self.items_on_conveyors.get(source_key, [])
            adjusted_index = source_index - items_removed_from_source.get(source_key, 0)

            if adjusted_index < len(current_source_items) and current_source_items[adjusted_index]["id"] == item_id:
                self.place_item_on_conveyor(dest_x, dest_y, item_id)
                current_source_items[adjusted_index] = None  # Mark as None for later removal
                items_removed_from_source[source_key] = items_removed_from_source.get(source_key, 0) + 1

        # Clean up items marked as None
        for (x, y), items in self.items_on_conveyors.items():
            self.items_on_conveyors[(x, y)] = [item for item in items if item is not None]

    def draw_items(self, screen, camera_x, camera_y, block_surfaces):
        """Draw items on conveyor belts."""
        item_size = config.PIXEL_SIZE // 2  # Size of item icon on belt
        half_item_size = item_size // 2
        half_block_size = config.PIXEL_SIZE // 2

        for (x, y), items in self.items_on_conveyors.items():
            if not items:
                continue

            conveyor_data = self.conveyors.get((x, y))
            if not conveyor_data:
                continue

            direction = conveyor_data["direction"]
            # Base position of the conveyor block's top-left corner on screen
            base_screen_x = x * config.PIXEL_SIZE - camera_x
            base_screen_y = y * config.PIXEL_SIZE - camera_y

            for item in items:
                item_id = item["id"]
                progress = item["progress"]  # Value from 0.0 to 1.0

                # Calculate the item's CENTER position based on progress and direction
                item_center_x = 0
                item_center_y = 0

                if direction == 0:  # Moving Right
                    item_center_x = base_screen_x + progress * config.PIXEL_SIZE
                    item_center_y = base_screen_y + half_block_size
                elif direction == 1:  # Moving Down
                    item_center_x = base_screen_x + half_block_size
                    item_center_y = base_screen_y + progress * config.PIXEL_SIZE
                elif direction == 2:  # Moving Left
                    item_center_x = base_screen_x + (1.0 - progress) * config.PIXEL_SIZE
                    item_center_y = base_screen_y + half_block_size
                elif direction == 3:  # Moving Up
                    item_center_x = base_screen_x + half_block_size
                    item_center_y = base_screen_y + (1.0 - progress) * config.PIXEL_SIZE

                # Calculate the top-left drawing position from the center position
                draw_x = item_center_x - half_item_size
                draw_y = item_center_y - half_item_size

                if item_id in block_surfaces:
                    item_surface = block_surfaces[item_id]
                    # Scale the surface if needed (or pre-scale surfaces)
                    try:
                        # Optimization: Cache scaled surfaces if performance becomes an issue
                        scaled_surface = pygame.transform.scale(item_surface, (item_size, item_size))
                        screen.blit(scaled_surface, (draw_x, draw_y))
                    except Exception as e:
                        print(f"Error scaling/blitting item {item_id}: {e}")  # Should not happen if block_surfaces is valid
                else:
                    # Draw a placeholder if surface not found
                    pygame.draw.rect(screen, (255, 0, 255), (draw_x, draw_y, item_size, item_size))
    
    def get_save_data(self):
        """Get save data for conveyors and items."""
        return {
            "conveyors": {f"{x},{y}": data for (x, y), data in self.conveyors.items()},
            "items": {f"{x},{y}": items for (x, y), items in self.items_on_conveyors.items() if items}
        }

    def load_save_data(self, data):
        """Load save data for conveyors and items."""
        self.conveyors.clear()
        self.items_on_conveyors.clear()

        conveyors_data = data.get("conveyors", {})
        for key, c_data in conveyors_data.items():
            x_str, y_str = key.split(',')
            self.conveyors[(int(x_str), int(y_str))] = c_data

        items_data = data.get("items", {})
        for key, i_data in items_data.items():
            x_str, y_str = key.split(',')
            self.items_on_conveyors[(int(x_str), int(y_str))] = i_data
