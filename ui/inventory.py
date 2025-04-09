import pygame
from core import config
from world.block_utils import get_block_name, get_block_color

class Inventory:
    def __init__(self, size=9):
        self.size = size
        self.slots = [None] * size  # List to store items (block_type, count)
        self.selected_slot = 0
        self.font = pygame.font.SysFont("Consolas", 14)
        
        # Drag and drop system
        self.dragged_item = None
        self.drag_source = None
        self.drag_slot = None

    def add_item(self, block_type, count=1):
        """Add an item to the inventory."""
        # Check if the block_type is already in the inventory
        for i in range(self.size):
            if self.slots[i] is not None and self.slots[i][0] == block_type:
                self.slots[i] = (block_type, self.slots[i][1] + count)
                return True

        # If the block_type is not in the inventory, add it to the first empty slot
        for i in range(self.size):
            if self.slots[i] is None:
                self.slots[i] = (block_type, count)
                return True

        # If the inventory is full, return False
        return False

    def remove_item(self, slot, count=1):
        """Remove an item from the inventory."""
        if 0 <= slot < self.size and self.slots[slot] is not None:
            block_type, current_count = self.slots[slot]
            if current_count > count:
                self.slots[slot] = (block_type, current_count - count)
                return block_type, count
            else:
                removed_item = self.slots[slot]
                self.slots[slot] = None
                return removed_item
        return None

    def get_selected_item(self):
        """Get the currently selected item."""
        return self.slots[self.selected_slot]

    def select_slot(self, slot):
        """Select a slot in the inventory."""
        if 0 <= slot < self.size:
            self.selected_slot = slot

    def start_drag(self, mouse_x, mouse_y, screen_width, screen_height):
        """Start dragging an item from the inventory slot under the mouse cursor."""
        slot_size = 50
        slot_spacing = 5
        hotbar_x = screen_width // 2 - (self.size * (slot_size + slot_spacing) // 2)
        hotbar_y = screen_height - 50  # Near the bottom of the screen

        # Check if clicking on a slot in the hotbar
        for i in range(self.size):
            x = hotbar_x + i * (slot_size + slot_spacing)
            y = hotbar_y
            
            # If the mouse is over this slot and the slot has an item
            if (x <= mouse_x <= x + slot_size and 
                y <= mouse_y <= y + slot_size and 
                self.slots[i] is not None):
                
                # Start dragging this item
                self.dragged_item = self.slots[i]
                self.drag_source = "inventory"
                self.drag_slot = i
                # Remove from inventory temporarily
                self.slots[i] = None
                return True
                
        return False

    def drop_item(self, mouse_x, mouse_y, screen_width, screen_height):
        """Drop a dragged item into an inventory slot."""
        if self.dragged_item is None:
            return False
            
        slot_size = 50
        slot_spacing = 5
        hotbar_x = screen_width // 2 - (self.size * (slot_size + slot_spacing) // 2)
        hotbar_y = screen_height - 50  # Near the bottom of the screen

        # Check for dropping on hotbar
        for i in range(self.size):
            x = hotbar_x + i * (slot_size + slot_spacing)
            y = hotbar_y
            
            if (x <= mouse_x <= x + slot_size and 
                y <= mouse_y <= y + slot_size):
                
                # Handle merging or swapping with existing item
                if self.slots[i] is None:
                    # Empty slot - just place the item
                    self.slots[i] = self.dragged_item
                elif self.slots[i][0] == self.dragged_item[0]:
                    # Same item type - merge
                    self.slots[i] = (self.slots[i][0], self.slots[i][1] + self.dragged_item[1])
                else:
                    # Different item - swap
                    temp = self.slots[i]
                    self.slots[i] = self.dragged_item
                    self.dragged_item = temp
                    return False  # Item is still being dragged
                
                # Item was placed in inventory
                self.dragged_item = None
                self.drag_source = None
                self.drag_slot = None
                return True
                
        # Item wasn't dropped on an inventory slot
        return False

    def cancel_drag(self):
        """Cancel dragging and return the item to its original slot."""
        if self.dragged_item is not None and self.drag_source == "inventory" and self.drag_slot is not None:
            self.slots[self.drag_slot] = self.dragged_item
            self.dragged_item = None
            self.drag_source = None
            self.drag_slot = None
    
    def draw(self, screen, screen_width, screen_height):
        """Draw the inventory on the screen."""
        slot_size = 50
        slot_spacing = 5
        hotbar_x = screen_width // 2 - (self.size * (slot_size + slot_spacing) // 2)
        hotbar_y = screen_height - 50  # Near the bottom of the screen

        for i in range(self.size):
            x = hotbar_x + i * (slot_size + slot_spacing)
            y = hotbar_y

            # Draw slot background
            if i == self.selected_slot:
                pygame.draw.rect(screen, (150, 150, 150), (x, y, slot_size, slot_size))  # Highlight selected slot
            else:
                pygame.draw.rect(screen, (50, 50, 50), (x, y, slot_size, slot_size))

            # If we're dragging an item and hovering over this slot, highlight it as drop target
            mouse_x, mouse_y = pygame.mouse.get_pos()
            if self.dragged_item and x <= mouse_x <= x + slot_size and y <= mouse_y <= y + slot_size:
                pygame.draw.rect(screen, (100, 200, 100), (x, y, slot_size, slot_size), 2)  # Green highlight

            # Draw item in slot (if not being dragged from this slot)
            if self.slots[i] is not None and not (self.drag_source == "inventory" and self.drag_slot == i):
                block_type, count = self.slots[i]

                if block_type in config.BLOCKS:
                    block_color = config.BLOCKS[block_type]["color"]
                    pygame.draw.rect(screen, block_color, (x + 5, y + 5, slot_size - 10, slot_size - 10))  # Draw block color
                    item_name = config.BLOCKS[block_type]["name"]
                    
                    # Draw item name above the slot
                    name_surface = self.font.render(item_name, True, (255, 255, 255))
                    
                    # Create background for text to improve readability
                    name_width = name_surface.get_width()
                    name_height = name_surface.get_height()
                    bg_rect = pygame.Rect(
                        x + (slot_size - name_width) // 2 - 2,  # Center horizontally with 2px padding
                        y - name_height - 5,  # Position above slot with 5px gap
                        name_width + 4,  # Add 4px padding (2px on each side)
                        name_height
                    )
                    
                    # Draw semi-transparent background for text
                    bg_surface = pygame.Surface((bg_rect.width, bg_rect.height))
                    bg_surface.set_alpha(180)  # Semi-transparent
                    bg_surface.fill((30, 30, 30))  # Dark gray
                    screen.blit(bg_surface, bg_rect.topleft)
                    
                    # Draw name text
                    screen.blit(name_surface, (x + (slot_size - name_width) // 2, y - name_height - 5))
                else:
                    item_name = "Unknown"
                    name_surface = self.font.render(item_name, True, (255, 100, 100))  # Red for unknown items
                    screen.blit(name_surface, (x + (slot_size - name_surface.get_width()) // 2, y - name_surface.get_height() - 5))

                # Draw count at the bottom
                count_surface = self.font.render(str(count), True, (255, 255, 255))
                count_rect = count_surface.get_rect(center=(x + slot_size // 2, y + slot_size - 10))  # Position at the bottom
                screen.blit(count_surface, count_rect)

    def draw_dragged_item(self, screen):
        """Draw the item being dragged."""
        if self.dragged_item:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            block_type, count = self.dragged_item
            
            # Draw item centered on mouse
            slot_size = 40  # Slightly smaller than inventory slots
            rect = pygame.Rect(
                mouse_x - slot_size // 2,
                mouse_y - slot_size // 2,
                slot_size,
                slot_size
            )
            
            # Draw block
            if block_type in config.BLOCKS:
                block_color = config.BLOCKS[block_type]["color"]
                pygame.draw.rect(screen, block_color, rect)
                
                # Draw count
                count_surface = self.font.render(str(count), True, (255, 255, 255))
                count_rect = count_surface.get_rect(center=(mouse_x, mouse_y + slot_size // 3))
                screen.blit(count_surface, count_rect)
