import pygame
import config
from processor_recipes import processor_recipes

class MachineUI:
    def __init__(self, screen_width, screen_height, block_surfaces):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.block_surfaces = block_surfaces
        
        # UI dimensions
        self.ui_width = 300
        self.ui_height = 200
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        
        # Slot dimensions
        self.slot_size = 50
        self.input_slot_x = self.ui_x + 50
        self.input_slot_y = self.ui_y + 75
        self.output_slot_x = self.ui_x + 200
        self.output_slot_y = self.ui_y + 75
        
        # Machine preview size
        self.machine_preview_width = 80
        self.machine_preview_height = 120  # For 4x6 machine
        
        # Initialize font for UI text
        self.font = pygame.font.SysFont("Arial", 16)
    
    def update_screen_size(self, screen_width, screen_height):
        """Update UI positioning when screen size changes"""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        self.input_slot_x = self.ui_x + 50
        self.input_slot_y = self.ui_y + 75
        self.output_slot_x = self.ui_x + 200
        self.output_slot_y = self.ui_y + 75
    
    def draw(self, screen, machine_data, progress):
        """Draw the machine UI with input, output slots and progress bar"""
        # Draw background panel
        pygame.draw.rect(screen, (70, 70, 70), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height))
        pygame.draw.rect(screen, (100, 100, 100), 
                        (self.ui_x, self.ui_y, self.ui_width, self.ui_height), 2)
        
        # Draw machine preview at the top center
        preview_x = self.ui_x + (self.ui_width - self.machine_preview_width) // 2
        preview_y = self.ui_y + 20
        
        pygame.draw.rect(screen, (150, 100, 200), (preview_x, preview_y, self.machine_preview_width, self.machine_preview_height))
        pygame.draw.rect(screen, (100, 60, 140), (preview_x + 2, preview_y + 2, self.machine_preview_width - 4, self.machine_preview_height // 3))
        pygame.draw.rect(screen, (80, 80, 80), (preview_x + self.machine_preview_width // 4, preview_y + self.machine_preview_height // 2, 
                                       self.machine_preview_width // 2, self.machine_preview_height // 3))
        
        # Draw title
        title = self.font.render("Ore Processor", True, (255, 255, 255))
        screen.blit(title, (self.ui_x + (self.ui_width - title.get_width()) // 2, preview_y + self.machine_preview_height + 10))
        
        # Draw input slot (position below the preview)
        input_slot_y = preview_y + self.machine_preview_height + 40
        pygame.draw.rect(screen, (50, 50, 50), 
                        (self.input_slot_x, input_slot_y, self.slot_size, self.slot_size))
        
        # Draw output slot
        output_slot_y = input_slot_y
        pygame.draw.rect(screen, (50, 50, 50), 
                        (self.output_slot_x, output_slot_y, self.slot_size, self.slot_size))
        
        # Update instance variables to match the new positions
        self.input_slot_y = input_slot_y
        self.output_slot_y = output_slot_y
        
        # Draw labels
        input_label = self.font.render("Input", True, (255, 255, 255))
        output_label = self.font.render("Output", True, (255, 255, 255))
        screen.blit(input_label, (self.input_slot_x + (self.slot_size - input_label.get_width()) // 2, 
                                  self.input_slot_y - 20))
        screen.blit(output_label, (self.output_slot_x + (self.slot_size - output_label.get_width()) // 2, 
                                  self.output_slot_y - 20))
        
        # Draw recipe info if there's an input item
        if machine_data and machine_data["input"]:
            input_type = machine_data["input"][0]
            if processor_recipes.can_process(input_type):
                recipe_desc = processor_recipes.get_description(input_type)
                recipe_text = self.font.render(recipe_desc, True, (255, 255, 255))
                screen.blit(recipe_text, (self.ui_x + (self.ui_width - recipe_text.get_width()) // 2, 
                                        self.ui_y + self.ui_height - 40))
        
        # Draw progress bar below slots
        bar_width = 180
        bar_height = 15
        bar_x = self.ui_x + (self.ui_width - bar_width) // 2
        bar_y = self.output_slot_y + self.slot_size + 20
        
        # Draw background bar
        pygame.draw.rect(screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
        
        # Draw progress
        if progress > 0:
            filled_width = int(bar_width * progress)
            pygame.draw.rect(screen, (0, 200, 0), (bar_x, bar_y, filled_width, bar_height))
        
        # Draw items in slots if they exist
        if machine_data:
            # Draw input item
            if machine_data["input"]:
                block_type, count = machine_data["input"]
                if block_type in self.block_surfaces:
                    # Scale the block surface to fit the slot
                    block_surface = pygame.transform.scale(
                        self.block_surfaces[block_type], 
                        (self.slot_size - 10, self.slot_size - 10)
                    )
                    screen.blit(block_surface, (self.input_slot_x + 5, self.input_slot_y + 5))
                    
                    # Draw count
                    count_text = self.font.render(str(count), True, (255, 255, 255))
                    screen.blit(count_text, (self.input_slot_x + self.slot_size - count_text.get_width() - 5, 
                                           self.input_slot_y + self.slot_size - count_text.get_height() - 5))
            
            # Draw output item
            if machine_data["output"]:
                block_type, count = machine_data["output"]
                if block_type in self.block_surfaces:
                    # Scale the block surface to fit the slot
                    block_surface = pygame.transform.scale(
                        self.block_surfaces[block_type], 
                        (self.slot_size - 10, self.slot_size - 10)
                    )
                    screen.blit(block_surface, (self.output_slot_x + 5, self.output_slot_y + 5))
                    
                    # Draw count
                    count_text = self.font.render(str(count), True, (255, 255, 255))
                    screen.blit(count_text, (self.output_slot_x + self.slot_size - count_text.get_width() - 5, 
                                           self.output_slot_y + self.slot_size - count_text.get_height() - 5))
    
    def is_point_in_ui(self, x, y):
        """Check if a point is within the UI area"""
        return (self.ui_x <= x <= self.ui_x + self.ui_width and 
                self.ui_y <= y <= self.ui_y + self.ui_height)
    
    def get_slot_at_position(self, x, y):
        """Return which slot (if any) is at the given position"""
        if (self.input_slot_x <= x <= self.input_slot_x + self.slot_size and 
            self.input_slot_y <= y <= self.input_slot_y + self.slot_size):
            return "input"
        elif (self.output_slot_x <= x <= self.output_slot_x + self.slot_size and 
              self.output_slot_y <= y <= self.output_slot_y + self.slot_size):
            return "output"
        return None
