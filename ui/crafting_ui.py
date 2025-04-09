import pygame
from core import config

class CraftingUI:
    def __init__(self, screen_width, screen_height, block_surfaces):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.block_surfaces = block_surfaces
        
        # UI dimensions
        self.ui_width = 320
        self.ui_height = 260
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        
        # Slot dimensions
        self.slot_size = 40
        self.slot_spacing = 5
        
        # Calculate crafting grid position
        self.grid_start_x = self.ui_x + 30
        self.grid_start_y = self.ui_y + 60
        
        # Output slot position
        self.output_slot_x = self.ui_x + 230
        self.output_slot_y = self.ui_y + 100
        
        # Initialize font for UI text
        self.font = pygame.font.SysFont("Arial", 16)
        self.title_font = pygame.font.SysFont("Arial", 20, bold=True)
        
        # Close button properties
        self.close_button_size = 20
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5  # Top-right corner
        self.close_button_y = self.ui_y + 5

    def update_screen_size(self, screen_width, screen_height):
        """Update UI positioning when screen size changes."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        self.grid_start_x = self.ui_x + 30
        self.grid_start_y = self.ui_y + 60
        self.output_slot_x = self.ui_x + 230
        self.output_slot_y = self.ui_y + 100
        
        # Update close button position
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5
        self.close_button_y = self.ui_y + 5

    def draw(self, screen, table_data, dragged_item=None):
        """Draw the crafting table UI."""
        # Draw background panel
        pygame.draw.rect(screen, (70, 70, 70), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height))
        pygame.draw.rect(screen, (100, 100, 100), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height), 2)
        
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
        
        # Draw title
        title = self.title_font.render("Crafting Table", True, (255, 255, 255))
        screen.blit(title, (self.ui_x + (self.ui_width - title.get_width()) // 2, self.ui_y + 20))
        
        # Draw 3x3 crafting grid
        for y in range(3):
            for x in range(3):
                slot_x = self.grid_start_x + x * (self.slot_size + self.slot_spacing)
                slot_y = self.grid_start_y + y * (self.slot_size + self.slot_spacing)
                
                # Draw slot background
                pygame.draw.rect(screen, (50, 50, 50), 
                                (slot_x, slot_y, self.slot_size, self.slot_size))
                
                # Draw highlight if dragging over this slot
                mouse_x, mouse_y = pygame.mouse.get_pos()
                if dragged_item and self.is_point_in_slot(mouse_x, mouse_y, slot_x, slot_y):
                    pygame.draw.rect(screen, (100, 200, 100), 
                                    (slot_x, slot_y, self.slot_size, self.slot_size), 2)
                
                # Draw item in slot if it exists
                if table_data and table_data["grid"][y][x]:
                    block_type, count = table_data["grid"][y][x]
                    
                    if block_type in self.block_surfaces:
                        # Draw block
                        block_surface = pygame.transform.scale(
                            self.block_surfaces[block_type], 
                            (self.slot_size - 10, self.slot_size - 10)
                        )
                        screen.blit(block_surface, (slot_x + 5, slot_y + 5))
                        
                        # Draw count if more than 1
                        if count > 1:
                            count_text = self.font.render(str(count), True, (255, 255, 255))
                            screen.blit(count_text, (slot_x + self.slot_size - count_text.get_width() - 5, 
                                                   slot_y + self.slot_size - count_text.get_height() - 5))
        
        # Draw arrow
        arrow_x = self.grid_start_x + 3 * (self.slot_size + self.slot_spacing) + 5
        arrow_y = self.grid_start_y + self.slot_size
        
        pygame.draw.polygon(screen, (200, 200, 200), [
            (arrow_x, arrow_y),
            (arrow_x + 30, arrow_y),
            (arrow_x + 40, arrow_y + 10),
            (arrow_x + 30, arrow_y + 20),
            (arrow_x, arrow_y + 20),
            (arrow_x + 10, arrow_y + 10)
        ])
        
        # Draw output slot
        pygame.draw.rect(screen, (70, 50, 50), 
                        (self.output_slot_x, self.output_slot_y, self.slot_size, self.slot_size))
        
        # Draw output item if it exists
        if table_data and table_data["output"]:
            block_type, count = table_data["output"]
            
            if block_type in self.block_surfaces:
                # Draw block
                block_surface = pygame.transform.scale(
                    self.block_surfaces[block_type], 
                    (self.slot_size - 10, self.slot_size - 10)
                )
                screen.blit(block_surface, (self.output_slot_x + 5, self.output_slot_y + 5))
                
                # Draw count if more than 1
                if count > 1:
                    count_text = self.font.render(str(count), True, (255, 255, 255))
                    screen.blit(count_text, (self.output_slot_x + self.slot_size - count_text.get_width() - 5, 
                                           self.output_slot_y + self.slot_size - count_text.get_height() - 5))
        
        # Draw recipe information
        if table_data and table_data["output"]:
            block_type, count = table_data["output"]
            if block_type in config.BLOCKS:
                info_text = f"Creates: {config.BLOCKS[block_type]['name']}"
                info_surface = self.font.render(info_text, True, (220, 220, 110))
                screen.blit(info_surface, (self.ui_x + (self.ui_width - info_surface.get_width()) // 2, 
                                         self.ui_y + self.ui_height - 40))
    
    def is_point_in_ui(self, x, y):
        """Check if a point is within the UI area."""
        return (self.ui_x <= x <= self.ui_x + self.ui_width and 
                self.ui_y <= y <= self.ui_y + self.ui_height)
    
    def is_point_in_slot(self, point_x, point_y, slot_x, slot_y):
        """Check if a point is within a specific slot."""
        return (slot_x <= point_x <= slot_x + self.slot_size and 
                slot_y <= point_y <= slot_y + self.slot_size)
    
    def get_slot_at_position(self, x, y):
        """Return which slot (if any) is at the given position."""
        # Check if point is in crafting grid
        for grid_y in range(3):
            for grid_x in range(3):
                slot_x = self.grid_start_x + grid_x * (self.slot_size + self.slot_spacing)
                slot_y = self.grid_start_y + grid_y * (self.slot_size + self.slot_spacing)
                
                if self.is_point_in_slot(x, y, slot_x, slot_y):
                    return ("grid", grid_x, grid_y)
        
        # Check if point is in output slot
        if self.is_point_in_slot(x, y, self.output_slot_x, self.output_slot_y):
            return ("output", 0, 0)
            
        return None

    def is_close_button_clicked(self, x, y):
        """Check if the close button was clicked"""
        return (self.close_button_x <= x <= self.close_button_x + self.close_button_size and
                self.close_button_y <= y <= self.close_button_y + self.close_button_size)
