import pygame
from core import config

class StorageUI:
    def __init__(self, screen_width, screen_height, block_surfaces):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.block_surfaces = block_surfaces
        
        # UI dimensions
        self.ui_width = 400
        self.ui_height = 300
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        
        # Scroll position
        self.scroll_offset = 0
        
        # Slot dimensions
        self.slot_size = 40
        self.slots_per_row = 8
        
        # Close button properties
        self.close_button_size = 20
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5
        self.close_button_y = self.ui_y + 5
        
        # Initialize font for UI text
        self.font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 20, bold=True)
        
    def update_screen_size(self, screen_width, screen_height):
        """Update UI positioning when screen size changes."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5
        self.close_button_y = self.ui_y + 5
        
    def draw(self, screen, storage_data, dragged_item=None):
        """Draw the storage UI."""
        # Draw background panel
        pygame.draw.rect(screen, (70, 70, 70), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height))
        pygame.draw.rect(screen, (100, 100, 100), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height), 2)
        
        # Draw title
        title = self.title_font.render("Storage Chest", True, (255, 255, 255))
        screen.blit(title, (self.ui_x + (self.ui_width - title.get_width()) // 2, self.ui_y + 15))
        
        # Draw close button (X) in the top-right corner
        pygame.draw.rect(screen, (200, 70, 70), 
                       (self.close_button_x, self.close_button_y, self.close_button_size, self.close_button_size))
        
        # Draw the X
        pygame.draw.line(screen, (255, 255, 255),
                       (self.close_button_x + 4, self.close_button_y + 4),
                       (self.close_button_x + self.close_button_size - 4, self.close_button_y + self.close_button_size - 4), 2)
        pygame.draw.line(screen, (255, 255, 255),
                       (self.close_button_x + self.close_button_size - 4, self.close_button_y + 4),
                       (self.close_button_x + 4, self.close_button_y + self.close_button_size - 4), 2)
        
        # Draw capacity info
        if storage_data:
            used = storage_data["used_space"]
            capacity = storage_data["capacity"]
            capacity_text = f"Storage: {used}/{capacity}"
            cap_surface = self.font.render(capacity_text, True, (255, 255, 255))
            screen.blit(cap_surface, (self.ui_x + 10, self.ui_y + 20))
            
            # Draw storage grid
            grid_start_x = self.ui_x + 20
            grid_start_y = self.ui_y + 50
            
            # Draw items in storage
            slot_index = 0
            for item_id, count in storage_data["items"].items():
                row = slot_index // self.slots_per_row
                col = slot_index % self.slots_per_row
                
                slot_x = grid_start_x + col * (self.slot_size + 5)
                slot_y = grid_start_y + row * (self.slot_size + 5)
                
                # Draw slot background
                pygame.draw.rect(screen, (50, 50, 50), (slot_x, slot_y, self.slot_size, self.slot_size))
                
                # Draw item
                if item_id in self.block_surfaces:
                    # Scale the block to fit the slot
                    item_surface = pygame.transform.scale(
                        self.block_surfaces[item_id],
                        (self.slot_size - 10, self.slot_size - 10)
                    )
                    screen.blit(item_surface, (slot_x + 5, slot_y + 5))
                else:
                    # Draw a colored square if texture isn't available
                    if item_id in config.BLOCKS:
                        item_color = config.BLOCKS[item_id]["color"]
                        pygame.draw.rect(screen, item_color, (slot_x + 5, slot_y + 5, self.slot_size - 10, self.slot_size - 10))
                
                # Draw item count
                count_text = self.font.render(str(count), True, (255, 255, 255))
                screen.blit(count_text, (slot_x + self.slot_size - count_text.get_width() - 3, 
                                        slot_y + self.slot_size - count_text.get_height()))
                
                # Highlight slot if dragged item is hovering over it
                if dragged_item:
                    mouse_x, mouse_y = pygame.mouse.get_pos()
                    if (slot_x <= mouse_x <= slot_x + self.slot_size and 
                        slot_y <= mouse_y <= slot_y + self.slot_size):
                        pygame.draw.rect(screen, (100, 200, 100), 
                                        (slot_x, slot_y, self.slot_size, self.slot_size), 2)
                
                slot_index += 1
    
    def get_slot_at_position(self, x, y, storage_data):
        """Return the item at the given position, or None if no item."""
        if not storage_data:
            return None
            
        grid_start_x = self.ui_x + 20
        grid_start_y = self.ui_y + 50
        
        # Calculate which slot was clicked
        col = (x - grid_start_x) // (self.slot_size + 5)
        row = (y - grid_start_y) // (self.slot_size + 5)
        
        if col < 0 or col >= self.slots_per_row:
            return None
            
        slot_index = row * self.slots_per_row + col
        
        # Get the item at this index
        items = list(storage_data["items"].items())
        if 0 <= slot_index < len(items):
            return items[slot_index]
            
        return None
    
    def is_point_in_ui(self, x, y):
        """Check if a point is within the UI area."""
        return (self.ui_x <= x <= self.ui_x + self.ui_width and 
                self.ui_y <= y <= self.ui_y + self.ui_height)
    
    def is_close_button_clicked(self, x, y):
        """Check if the close button was clicked."""
        return (self.close_button_x <= x <= self.close_button_x + self.close_button_size and
                self.close_button_y <= y <= self.close_button_y + self.close_button_size)
