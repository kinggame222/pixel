import pygame
import os  # Import os
import time  # Import time for default save names

class MainMenu:
    def __init__(self, screen_width, screen_height, saves_dir):  # Add saves_dir argument
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.saves_dir = saves_dir  # Store the saves directory path
        self.font = pygame.font.SysFont("Consolas", 30)  # Smaller font for save list
        self.title_font = pygame.font.SysFont("Consolas", 72)
        self.input_font = pygame.font.SysFont("Consolas", 36)

        self.menu_state = "main"  # "main", "load_game", "new_game"
        self.buttons = {}
        self.save_files = []
        self.save_file_buttons = {}  # Rects for clickable save file names
        self.selected_save_index = -1  # Index of the highlighted save file
        self.scroll_offset = 0  # For scrolling through save files
        self.visible_saves_count = 10  # Max saves to show at once

        # Input field for new game name
        self.new_game_input_rect = None
        self.new_game_name = ""
        self.input_active = False

        self.update_screen_size(screen_width, screen_height)  # Initial setup

    def scan_saves(self):
        """Scans the saves directory for .json files."""
        self.save_files = []
        try:
            if os.path.exists(self.saves_dir):
                for filename in os.listdir(self.saves_dir):
                    if filename.endswith(".json"):
                        self.save_files.append(filename)
                self.save_files.sort()  # Sort alphabetically
        except Exception as e:
            print(f"Error scanning saves directory '{self.saves_dir}': {e}")
        self.scroll_offset = 0  # Reset scroll on scan
        self._update_save_file_buttons()

    def _update_save_file_buttons(self):
        """Updates the positions of save file buttons based on scroll offset."""
        self.save_file_buttons = {}
        button_x = self.screen_width // 4  # Position list on the left
        button_width = self.screen_width // 2
        button_height = 40
        start_y = self.screen_height // 4 + 60  # Below title

        max_visible = min(len(self.save_files) - self.scroll_offset, self.visible_saves_count)

        for i in range(max_visible):
            index_in_full_list = self.scroll_offset + i
            save_name = self.save_files[index_in_full_list]
            rect = pygame.Rect(button_x, start_y + i * (button_height + 5), button_width, button_height)
            self.save_file_buttons[save_name] = rect

    def update_screen_size(self, screen_width, screen_height):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # --- Main Menu Buttons ---
        button_width = 300  # Wider buttons
        button_height = 60
        spacing = 20
        button_x = (self.screen_width - button_width) // 2
        total_button_height = (button_height * 3) + (spacing * 2)  # Load, New, Quit
        start_y = (self.screen_height - total_button_height) // 2 + 50  # Move down slightly

        self.main_menu_buttons = {
            "Load Game": pygame.Rect(button_x, start_y, button_width, button_height),
            "New Game": pygame.Rect(button_x, start_y + button_height + spacing, button_width, button_height),
            "Quit": pygame.Rect(button_x, start_y + 2 * (button_height + spacing), button_width, button_height)
        }

        # --- Load/New Game Screen Buttons ---
        back_button_width = 150
        back_button_height = 50
        self.back_button = pygame.Rect(20, self.screen_height - back_button_height - 20, back_button_width, back_button_height)
        # Specific buttons for load screen
        self.load_selected_button = pygame.Rect(self.screen_width - back_button_width - 200, self.screen_height - back_button_height - 20, back_button_width + 50, back_button_height)
        self.delete_selected_button = pygame.Rect(self.screen_width - back_button_width - 20, self.screen_height - back_button_height - 20, back_button_width, back_button_height)
        # Specific buttons for new game screen
        self.create_game_button = pygame.Rect(self.screen_width - back_button_width - 20, self.screen_height - back_button_height - 20, back_button_width, back_button_height)

        # --- New Game Input Field ---
        input_width = 400
        input_height = 50
        input_x = (self.screen_width - input_width) // 2
        input_y = self.screen_height // 2 - input_height // 2
        self.new_game_input_rect = pygame.Rect(input_x, input_y, input_width, input_height)

        # Update save file button positions if in load state
        if self.menu_state == "load_game":
            self._update_save_file_buttons()

    def draw(self, screen):
        screen.fill((20, 20, 50))  # Dark blue background

        # Draw Title (Common to all states)
        title_text = self.title_font.render("Pixel Game", True, (255, 255, 255))
        title_rect = title_text.get_rect(center=(self.screen_width // 2, self.screen_height // 5))  # Adjusted Y pos
        screen.blit(title_text, title_rect)

        mouse_pos = pygame.mouse.get_pos()

        if self.menu_state == "main":
            # Draw Main Menu Buttons
            for text, rect in self.main_menu_buttons.items():
                is_hovering = rect.collidepoint(mouse_pos)
                button_color = (100, 100, 150) if is_hovering else (70, 70, 120)
                pygame.draw.rect(screen, button_color, rect, border_radius=10)
                button_text = self.font.render(text, True, (255, 255, 255))
                text_rect = button_text.get_rect(center=rect.center)
                screen.blit(button_text, text_rect)

        elif self.menu_state == "load_game":
            # Draw Save Files List
            list_title = self.font.render("Select a World to Load:", True, (200, 200, 255))
            list_title_rect = list_title.get_rect(center=(self.screen_width // 2, self.screen_height // 4 + 20))
            screen.blit(list_title, list_title_rect)

            for i, (save_name, rect) in enumerate(self.save_file_buttons.items()):
                is_hovering = rect.collidepoint(mouse_pos)
                is_selected = (self.scroll_offset + i) == self.selected_save_index

                bg_color = (120, 120, 180) if is_selected else (100, 100, 150) if is_hovering else (70, 70, 120)
                text_color = (255, 255, 255)

                pygame.draw.rect(screen, bg_color, rect, border_radius=5)
                save_text = self.font.render(save_name.replace(".json", ""), True, text_color)
                text_rect = save_text.get_rect(midleft=(rect.left + 15, rect.centery))
                screen.blit(save_text, text_rect)

            # Draw Scroll Indicators if needed
            if len(self.save_files) > self.visible_saves_count:
                # Simple arrows or text indicators
                if self.scroll_offset > 0:
                    up_arrow = self.font.render("^", True, (200, 200, 200))
                    screen.blit(up_arrow, (self.screen_width // 2 - 10, self.screen_height // 4 + 40))
                if self.scroll_offset + self.visible_saves_count < len(self.save_files):
                    down_arrow = self.font.render("v", True, (200, 200, 200))
                    last_button_rect = list(self.save_file_buttons.values())[-1]
                    screen.blit(down_arrow, (self.screen_width // 2 - 10, last_button_rect.bottom + 5))

            # Draw Back Button
            is_hovering = self.back_button.collidepoint(mouse_pos)
            button_color = (150, 100, 100) if is_hovering else (120, 70, 70)
            pygame.draw.rect(screen, button_color, self.back_button, border_radius=10)
            button_text = self.font.render("Back", True, (255, 255, 255))
            text_rect = button_text.get_rect(center=self.back_button.center)
            screen.blit(button_text, text_rect)

            # Draw Load/Delete Buttons (only if a save is selected)
            if self.selected_save_index != -1:
                # Load Button
                is_hovering = self.load_selected_button.collidepoint(mouse_pos)
                button_color = (100, 150, 100) if is_hovering else (70, 120, 70)
                pygame.draw.rect(screen, button_color, self.load_selected_button, border_radius=10)
                button_text = self.font.render("Load World", True, (255, 255, 255))
                text_rect = button_text.get_rect(center=self.load_selected_button.center)
                screen.blit(button_text, text_rect)

                # Delete Button
                is_hovering = self.delete_selected_button.collidepoint(mouse_pos)
                button_color = (180, 80, 80) if is_hovering else (150, 50, 50)
                pygame.draw.rect(screen, button_color, self.delete_selected_button, border_radius=10)
                button_text = self.font.render("Delete", True, (255, 255, 255))
                text_rect = button_text.get_rect(center=self.delete_selected_button.center)
                screen.blit(button_text, text_rect)

        elif self.menu_state == "new_game":
            # Draw Prompt
            prompt_text = self.font.render("Enter New World Name:", True, (200, 200, 255))
            prompt_rect = prompt_text.get_rect(center=(self.screen_width // 2, self.screen_height // 2 - 60))
            screen.blit(prompt_text, prompt_rect)

            # Draw Input Box
            input_box_color = (200, 200, 200) if self.input_active else (150, 150, 150)
            pygame.draw.rect(screen, input_box_color, self.new_game_input_rect, border_radius=5)
            pygame.draw.rect(screen, (0, 0, 0), self.new_game_input_rect, width=2, border_radius=5)  # Border

            # Draw Text Input
            input_surface = self.input_font.render(self.new_game_name, True, (0, 0, 0))
            # Position text inside the input box
            screen.blit(input_surface, (self.new_game_input_rect.x + 10, self.new_game_input_rect.y + 5))

            # Draw Blinking Cursor (optional)
            if self.input_active and int(time.time() * 2) % 2 == 0:
                cursor_x = self.new_game_input_rect.x + 10 + input_surface.get_width()
                cursor_y_start = self.new_game_input_rect.y + 5
                cursor_y_end = self.new_game_input_rect.y + self.new_game_input_rect.height - 5
                pygame.draw.line(screen, (0, 0, 0), (cursor_x, cursor_y_start), (cursor_x, cursor_y_end), 2)

            # Draw Back Button
            is_hovering = self.back_button.collidepoint(mouse_pos)
            button_color = (150, 100, 100) if is_hovering else (120, 70, 70)
            pygame.draw.rect(screen, button_color, self.back_button, border_radius=10)
            button_text = self.font.render("Back", True, (255, 255, 255))
            text_rect = button_text.get_rect(center=self.back_button.center)
            screen.blit(button_text, text_rect)

            # Draw Create Button
            is_hovering = self.create_game_button.collidepoint(mouse_pos)
            button_color = (100, 150, 100) if is_hovering else (70, 120, 70)
            pygame.draw.rect(screen, button_color, self.create_game_button, border_radius=10)
            button_text = self.font.render("Create", True, (255, 255, 255))
            text_rect = button_text.get_rect(center=self.create_game_button.center)
            screen.blit(button_text, text_rect)

    def handle_input(self, event):
        if self.menu_state == "main":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                for text, rect in self.main_menu_buttons.items():
                    if rect.collidepoint(mouse_pos):
                        if text == "Load Game":
                            self.menu_state = "load_game"
                            self.scan_saves()
                            self.selected_save_index = -1  # Reset selection
                            return None  # Stay in menu
                        elif text == "New Game":
                            self.menu_state = "new_game"
                            self.new_game_name = f"World_{int(time.time()) % 10000}"  # Default name
                            self.input_active = True  # Activate input field
                            return None  # Stay in menu
                        elif text == "Quit":
                            return "Quit"  # Signal to main loop to quit

        elif self.menu_state == "load_game":
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos
                if event.button == 1:  # Left Click
                    # Check Back button
                    if self.back_button.collidepoint(mouse_pos):
                        self.menu_state = "main"
                        return None

                    # Check Load/Delete buttons (if a save is selected)
                    if self.selected_save_index != -1:
                        selected_save_name = self.save_files[self.selected_save_index]
                        if self.load_selected_button.collidepoint(mouse_pos):
                            return ("load_game", selected_save_name)  # Return action tuple
                        if self.delete_selected_button.collidepoint(mouse_pos):
                            # Ask for confirmation? For now, just delete.
                            return ("delete_game", selected_save_name)  # Return action tuple

                    # Check Save file list clicks
                    clicked_on_save = False
                    for i, (save_name, rect) in enumerate(self.save_file_buttons.items()):
                        if rect.collidepoint(mouse_pos):
                            self.selected_save_index = self.scroll_offset + i
                            clicked_on_save = True
                            break
                    # Deselect if clicking outside buttons/saves
                    if not clicked_on_save and not self.back_button.collidepoint(mouse_pos) \
                            and not (self.selected_save_index != -1 and (self.load_selected_button.collidepoint(mouse_pos) or self.delete_selected_button.collidepoint(mouse_pos))):
                        self.selected_save_index = -1

                elif event.button == 4:  # Scroll Up
                    if self.scroll_offset > 0:
                        self.scroll_offset -= 1
                        self._update_save_file_buttons()
                elif event.button == 5:  # Scroll Down
                    if self.scroll_offset + self.visible_saves_count < len(self.save_files):
                        self.scroll_offset += 1
                        self._update_save_file_buttons()

        elif self.menu_state == "new_game":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = event.pos
                # Check Back button
                if self.back_button.collidepoint(mouse_pos):
                    self.menu_state = "main"
                    self.input_active = False
                    return None
                # Check Create button
                if self.create_game_button.collidepoint(mouse_pos):
                    world_name = self.new_game_name.strip()
                    if world_name:
                        # Basic validation: replace invalid chars, ensure .json extension
                        valid_name = "".join(c for c in world_name if c.isalnum() or c in ('_', '-'))
                        if not valid_name:
                            valid_name = f"World_{int(time.time()) % 10000}"
                        save_name = valid_name + ".json"
                        # Check for overwrite? For now, allow it.
                        return ("new_game", save_name)  # Return action tuple
                    else:
                        # Maybe show an error message?
                        print("World name cannot be empty.")
                        return None

                # Check if clicking inside input box
                if self.new_game_input_rect.collidepoint(mouse_pos):
                    self.input_active = True
                else:
                    self.input_active = False

            elif event.type == pygame.KEYDOWN and self.input_active:
                if event.key == pygame.K_RETURN:
                    # Treat Enter like clicking Create button
                    world_name = self.new_game_name.strip()
                    if world_name:
                        valid_name = "".join(c for c in world_name if c.isalnum() or c in ('_', '-'))
                        if not valid_name:
                            valid_name = f"World_{int(time.time()) % 10000}"
                        save_name = valid_name + ".json"
                        return ("new_game", save_name)
                elif event.key == pygame.K_BACKSPACE:
                    self.new_game_name = self.new_game_name[:-1]
                else:
                    # Limit name length?
                    if len(self.new_game_name) < 30:
                        # Allow alphanumeric, underscore, hyphen
                        if event.unicode.isalnum() or event.unicode in ('_', '-'):
                            self.new_game_name += event.unicode

        return None  # No action taken or stay in menu
