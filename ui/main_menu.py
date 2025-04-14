import pygame

class MainMenu:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font = pygame.font.SysFont("Consolas", 40)
        self.title_font = pygame.font.SysFont("Consolas", 72)
        self.buttons = {}
        self.update_screen_size(screen_width, screen_height) # Initial setup

    def update_screen_size(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Recalculate button positions
        button_width = 250
        button_height = 60
        spacing = 20 # Space between buttons
        
        # Center buttons horizontally
        button_x = (self.screen_width - button_width) // 2
        
        # Position buttons vertically, centered around the middle of the screen
        total_button_height = (button_height * 3) + (spacing * 2) # 3 buttons now
        start_y = (self.screen_height - total_button_height) // 2
        
        self.buttons = {
            "Start Game": pygame.Rect(button_x, start_y, button_width, button_height),
            "Settings": pygame.Rect(button_x, start_y + button_height + spacing, button_width, button_height), # New Settings button
            "Quit": pygame.Rect(button_x, start_y + 2 * (button_height + spacing), button_width, button_height) # Adjusted Quit button position
        }

    def draw(self, screen):
        screen.fill((20, 20, 50))  # Dark blue background

        # Draw Title
        title_text = self.title_font.render("Pixel Game", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.screen_width // 2, self.screen_height // 4))
        screen.blit(title_text, title_rect)

        # Draw Buttons
        for text, rect in self.buttons.items():
            # Simple button styling
            mouse_pos = pygame.mouse.get_pos()
            is_hovering = rect.collidepoint(mouse_pos)
            
            button_color = (100, 100, 150) if is_hovering else (70, 70, 120)
            pygame.draw.rect(screen, button_color, rect, border_radius=10)
            
            button_text = self.font.render(text, True, (255, 255, 255))
            text_rect = button_text.get_rect(center=rect.center)
            screen.blit(button_text, text_rect)

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                mouse_pos = event.pos
                for text, rect in self.buttons.items():
                    if rect.collidepoint(mouse_pos):
                        if text == "Start Game":
                            return "Start Game"
                        elif text == "Settings": # Handle Settings click
                            return "Open Settings" 
                        elif text == "Quit":
                            return "Quit"
        return None
