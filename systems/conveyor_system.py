import pygame
import time
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
        
        # Get conveyor block IDs with fallbacks
        self.conveyor_id = getattr(config, "CONVEYOR_BELT", 17)
        self.vertical_conveyor_id = getattr(config, "VERTICAL_CONVEYOR", 18)
        self.extractor_id = getattr(config, "ITEM_EXTRACTOR", 19)
        
        # Conveyor belt speed (fractional distance per second)
        self.speed = 0.5  # Items move 50% of a belt per second
        
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
        print(f"Conveyor registered at ({x}, {y}) with direction {direction}")
        return True
    
    def place_item_on_conveyor(self, x, y, item_id, count=1):
        """Place an item on a conveyor belt."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) in self.conveyors:
            item = ConveyorItem(item_id, count)
            self.conveyors[(x, y)]["items"].append(item)
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
        current_time = time.time()
        
        # Process each conveyor
        for pos, conveyor in self.conveyors.items():
            # Skip if no items on this conveyor
            if not conveyor["items"]:
                continue
            
            x, y = pos
            direction = conveyor["direction"]
            next_pos = self.get_next_position(x, y, direction)
            
            # Process items from end to beginning (to avoid conflicts)
            items_to_remove = []
            
            for i, item in enumerate(reversed(conveyor["items"])):
                item_index = len(conveyor["items"]) - 1 - i
                
                # Move the item along the belt
                if item.advance(self.speed * dt):
                    # Item reached the end of this conveyor
                    if next_pos:
                        # Check destination type
                        dest_block = self.get_block_at(*next_pos)
                        
                        if dest_block == self.conveyor_id or dest_block == self.vertical_conveyor_id:
                            # Transfer to next conveyor if it exists in our system
                            if next_pos in self.conveyors:
                                # Check if the next conveyor has space
                                next_conveyor = self.conveyors[next_pos]
                                if not next_conveyor["items"] or next_conveyor["items"][0].position > 0.2:
                                    # Reset position and add to next conveyor
                                    item.position = 0.0
                                    next_conveyor["items"].insert(0, item)
                                    items_to_remove.append(item_index)
                        
                        # Handle storage destination
                        elif storage_system and dest_block == storage_system.storage_chest_id:
                            # Try to add to storage
                            if storage_system.add_item_to_storage(*next_pos, item.item_id, item.count):
                                items_to_remove.append(item_index)
                        
                        # Handle machine destination (like ore processor)
                        elif machine_system and dest_block == machine_system.ore_processor_id:
                            if machine_system.add_item_to_machine(next_pos, item.item_id, item.count):
                                items_to_remove.append(item_index)
            
            # Remove items that were transferred
            for index in sorted(items_to_remove, reverse=True):
                if 0 <= index < len(conveyor["items"]):
                    conveyor["items"].pop(index)
    
    def draw_items(self, screen, camera_x, camera_y, block_surfaces):
        """Draw items on conveyor belts."""
        for (x, y), conveyor in self.conveyors.items():
            # Get conveyor size from multi-block system if available
            conveyor_width, conveyor_height = 2, 2  # Default to 2x2
            
            for item in conveyor["items"]:
                # Calculate item position on the belt
                if conveyor["direction"] == 0:  # Right
                    item_x = x * config.PIXEL_SIZE + item.position * conveyor_width * config.PIXEL_SIZE
                    item_y = y * config.PIXEL_SIZE + config.PIXEL_SIZE / 2
                elif conveyor["direction"] == 1:  # Down
                    item_x = x * config.PIXEL_SIZE + config.PIXEL_SIZE / 2
                    item_y = y * config.PIXEL_SIZE + item.position * conveyor_height * config.PIXEL_SIZE
                elif conveyor["direction"] == 2:  # Left
                    item_x = x * config.PIXEL_SIZE + (1 - item.position) * conveyor_width * config.PIXEL_SIZE
                    item_y = y * config.PIXEL_SIZE + config.PIXEL_SIZE / 2
                elif conveyor["direction"] == 3:  # Up
                    item_x = x * config.PIXEL_SIZE + config.PIXEL_SIZE / 2
                    item_y = y * config.PIXEL_SIZE + (1 - item.position) * conveyor_height * config.PIXEL_SIZE
                
                # Draw the item (adjust based on your rendering system)
                screen_x = item_x - camera_x
                screen_y = item_y - camera_y
                
                # Draw a small square representing the item
                item_size = int(config.PIXEL_SIZE * 0.6)  # Slightly smaller than a block
                
                if item.item_id in block_surfaces:
                    # Draw using the block's texture but smaller
                    surface = pygame.transform.scale(block_surfaces[item.item_id], (item_size, item_size))
                    screen.blit(surface, (screen_x + (config.PIXEL_SIZE - item_size) // 2, 
                                         screen_y + (config.PIXEL_SIZE - item_size) // 2))
                else:
                    # Fallback: draw a colored square
                    item_color = (255, 255, 255)  # Default white
                    if item.item_id in config.BLOCKS:
                        item_color = config.BLOCKS[item.item_id]["color"]
                    
                    pygame.draw.rect(screen, item_color, (
                        screen_x + (config.PIXEL_SIZE - item_size) // 2, 
                        screen_y + (config.PIXEL_SIZE - item_size) // 2, 
                        item_size, item_size
                    ))
