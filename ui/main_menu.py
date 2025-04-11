import pygame

class MainMenu:
    def __init__(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font = pygame.font.SysFont("Arial", 36)
        self.title_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.options = ["Start Game", "Quit"]
        self.selected_option = 0

    def draw(self, screen):
        """Draw the main menu."""
        screen.fill((30, 30, 30))  # Background color

        # Draw title
        title_surface = self.title_font.render("Main Menu", True, (255, 255, 255))
        screen.blit(title_surface, ((self.screen_width - title_surface.get_width()) // 2, 100))

        # Draw options
        for i, option in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected_option else (150, 150, 150)
            option_surface = self.font.render(option, True, color)
            screen.blit(option_surface, ((self.screen_width - option_surface.get_width()) // 2, 200 + i * 50))

    def handle_input(self, event):
        """Handle user input for menu navigation."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_option = (self.selected_option - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected_option = (self.selected_option + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                return self.options[self.selected_option]
        return None
