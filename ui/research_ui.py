import pygame
import json
import os
from core import config

class ResearchUI:
    def __init__(self, screen_width, screen_height, unlocked_tech=None):
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # UI dimensions
        self.ui_width = 800
        self.ui_height = 600
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        
        # Close button properties
        self.close_button_size = 20
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5
        self.close_button_y = self.ui_y + 5
        
        # Load tech tree
        self.tech_tree = self.load_tech_tree()
        
        # Track unlocked technologies
        self.unlocked_tech = unlocked_tech or {"basic"}  # Start with basic tech
        
        # UI state
        self.selected_tier = None
        self.selected_item = None
        self.scroll_offset = 0
        
        # Fonts
        self.title_font = pygame.font.SysFont("Arial", 24, bold=True)
        self.normal_font = pygame.font.SysFont("Arial", 16)
        self.small_font = pygame.font.SysFont("Arial", 14)
        
    def load_tech_tree(self):
        """Load the tech tree from JSON file"""
        tech_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tech_tree.json")
        
        try:
            if os.path.exists(tech_file):
                with open(tech_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading tech tree: {e}")
            
        # Fallback
        return {
            "tiers": {
                "basic": {
                    "name": "Basic Technology",
                    "requirements": [],
                    "unlocks": ["ore_processor"]
                }
            },
            "research_items": {
                "ore_processor": {
                    "name": "Ore Processor", 
                    "description": "Processes raw ores into refined metals",
                    "cost": {"iron_ore": 10, "stone": 20}
                }
            }
        }
    
    def update_screen_size(self, screen_width, screen_height):
        """Update UI positioning when screen size changes."""
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.ui_x = (screen_width - self.ui_width) // 2
        self.ui_y = (screen_height - self.ui_height) // 2
        self.close_button_x = self.ui_x + self.ui_width - self.close_button_size - 5
        self.close_button_y = self.ui_y + 5
    
    def draw(self, screen, inventory=None):
        """Draw the research UI"""
        # Draw background panel
        pygame.draw.rect(screen, (40, 40, 60), (self.ui_x, self.ui_y, self.ui_width, self.ui_height))
        pygame.draw.rect(screen, (80, 80, 100), (self.ui_x, self.ui_y, self.ui_width, self.ui_height), 2)
        
        # Draw title
        title = self.title_font.render("Research & Technology", True, (255, 255, 255))
        screen.blit(title, (self.ui_x + (self.ui_width - title.get_width()) // 2, self.ui_y + 15))
        
        # Draw close button
        pygame.draw.rect(screen, (200, 70, 70), 
                       (self.close_button_x, self.close_button_y, self.close_button_size, self.close_button_size))
        pygame.draw.line(screen, (255, 255, 255),
                       (self.close_button_x + 4, self.close_button_y + 4),
                       (self.close_button_x + self.close_button_size - 4, self.close_button_y + self.close_button_size - 4), 2)
        pygame.draw.line(screen, (255, 255, 255),
                       (self.close_button_x + self.close_button_size - 4, self.close_button_y + 4),
                       (self.close_button_x + 4, self.close_button_y + self.close_button_size - 4), 2)
        
        # Draw tech tiers on the left side
        self._draw_tech_tiers(screen)
        
        # Draw research items for selected tier
        if self.selected_tier:
            self._draw_research_items(screen)
        
        # Draw selected item details
        if self.selected_item:
            self._draw_item_details(screen, inventory)
    
    def _draw_tech_tiers(self, screen):
        """Draw the technology tier list"""
        tier_area = pygame.Rect(self.ui_x + 20, self.ui_y + 50, 200, self.ui_height - 70)
        pygame.draw.rect(screen, (50, 50, 70), tier_area)
        
        tier_y = tier_area.y + 10
        for tier_id, tier_data in self.tech_tree["tiers"].items():
            # Check if this tier is available
            available = True
            for req in tier_data["requirements"]:
                if req not in self.unlocked_tech:
                    available = False
                    break
            
            unlocked = tier_id in self.unlocked_tech
            
            # Choose color based on status
            if unlocked:
                color = (100, 255, 100)  # Green for unlocked
            elif available:
                color = (255, 255, 100)  # Yellow for available but not unlocked
            else:
                color = (150, 150, 150)  # Gray for unavailable
                
            # Highlight selected tier
            if tier_id == self.selected_tier:
                pygame.draw.rect(screen, (70, 70, 90), (tier_area.x, tier_y - 5, tier_area.width, 30))
                
            # Draw tier name
            tier_text = self.normal_font.render(tier_data["name"], True, color)
            screen.blit(tier_text, (tier_area.x + 10, tier_y))
            tier_y += 30
    
    def _draw_research_items(self, screen):
        """Draw the research items for the selected tier"""
        items_area = pygame.Rect(self.ui_x + 240, self.ui_y + 50, 
                                self.ui_width - 260, (self.ui_height - 70) // 2)
        pygame.draw.rect(screen, (50, 50, 70), items_area)
        
        # Get items for this tier
        tier_data = self.tech_tree["tiers"][self.selected_tier]
        unlocks = tier_data["unlocks"]
        
        # Draw items in a grid
        item_size = 80
        grid_cols = (items_area.width - 20) // item_size
        
        col, row = 0, 0
        for item_id in unlocks:
            if item_id in self.tech_tree["research_items"]:
                item_data = self.tech_tree["research_items"][item_id]
                
                # Calculate position
                item_x = items_area.x + 10 + col * item_size
                item_y = items_area.y + 10 + row * item_size
                
                # Draw item background
                pygame.draw.rect(screen, (60, 60, 80), (item_x, item_y, item_size - 10, item_size - 10))
                
                # Highlight if selected
                if item_id == self.selected_item:
                    pygame.draw.rect(screen, (100, 100, 140), (item_x, item_y, item_size - 10, item_size - 10), 2)
                
                # Draw item name
                item_text = self.small_font.render(item_data["name"], True, (255, 255, 255))
                screen.blit(item_text, (item_x + 5, item_y + 5))
                
                # Move to next position
                col += 1
                if col >= grid_cols:
                    col = 0
                    row += 1
    
    def _draw_item_details(self, screen, inventory):
        """Draw details for the selected research item"""
        details_area = pygame.Rect(self.ui_x + 240, self.ui_y + 50 + (self.ui_height - 70) // 2 + 10, 
                                 self.ui_width - 260, (self.ui_height - 70) // 2 - 10)
        pygame.draw.rect(screen, (50, 50, 70), details_area)
        
        if self.selected_item in self.tech_tree["research_items"]:
            item_data = self.tech_tree["research_items"][self.selected_item]
            
            # Draw item name
            name_text = self.normal_font.render(item_data["name"], True, (255, 255, 255))
            screen.blit(name_text, (details_area.x + 10, details_area.y + 10))
            
            # Draw description
            desc_text = self.small_font.render(item_data["description"], True, (200, 200, 200))
            screen.blit(desc_text, (details_area.x + 10, details_area.y + 40))
            
            # Draw required resources
            req_text = self.normal_font.render("Required Resources:", True, (255, 255, 255))
            screen.blit(req_text, (details_area.x + 10, details_area.y + 70))
            
            y_offset = 100
            can_unlock = True
            
            for resource, amount in item_data["cost"].items():
                resource_name = resource.replace("_", " ").title()
                
                # Check if player has enough resources
                has_enough = False
                if inventory:
                    for slot in inventory.slots:
                        if slot and hasattr(config, resource.upper()) and slot[0] == getattr(config, resource.upper()) and slot[1] >= amount:
                            has_enough = True
                            break
                
                if not has_enough:
                    can_unlock = False
                    
                color = (100, 255, 100) if has_enough else (255, 100, 100)
                req_text = self.small_font.render(f"{resource_name}: {amount}", True, color)
                screen.blit(req_text, (details_area.x + 20, details_area.y + y_offset))
                y_offset += 25
            
            # Draw research button
            button_rect = pygame.Rect(details_area.x + details_area.width - 150, 
                                     details_area.y + details_area.height - 50, 
                                     140, 40)
            
            if can_unlock:
                pygame.draw.rect(screen, (100, 200, 100), button_rect)
                button_text = self.normal_font.render("Research", True, (0, 0, 0))
            else:
                pygame.draw.rect(screen, (150, 150, 150), button_rect)
                button_text = self.normal_font.render("Research", True, (50, 50, 50))
                
            text_x = button_rect.x + (button_rect.width - button_text.get_width()) // 2
            text_y = button_rect.y + (button_rect.height - button_text.get_height()) // 2
            screen.blit(button_text, (text_x, text_y))
    
    def handle_click(self, x, y, inventory):
        """Handle mouse clicks on the UI"""
        # Check close button
        if (self.close_button_x <= x <= self.close_button_x + self.close_button_size and
            self.close_button_y <= y <= self.close_button_y + self.close_button_size):
            return "close"
            
        # Check tier selection
        tier_area = pygame.Rect(self.ui_x + 20, self.ui_y + 50, 200, self.ui_height - 70)
        if tier_area.collidepoint(x, y):
            tier_y = tier_area.y + 10
            for tier_id, tier_data in self.tech_tree["tiers"].items():
                if tier_area.y <= y < tier_area.y + 30:
                    # Check if this tier is available
                    available = True
                    for req in tier_data["requirements"]:
                        if req not in self.unlocked_tech:
                            available = False
                            break
                            
                    if available:
                        self.selected_tier = tier_id
                        self.selected_item = None  # Reset item selection
                    return None
                tier_y += 30
                
        # Check item selection if a tier is selected
        if self.selected_tier:
            items_area = pygame.Rect(self.ui_x + 240, self.ui_y + 50, 
                                    self.ui_width - 260, (self.ui_height - 70) // 2)
            if items_area.collidepoint(x, y):
                # Get items for this tier
                tier_data = self.tech_tree["tiers"][self.selected_tier]
                unlocks = tier_data["unlocks"]
                
                # Calculate grid
                item_size = 80
                grid_cols = (items_area.width - 20) // item_size
                
                rel_x = x - (items_area.x + 10)
                rel_y = y - (items_area.y + 10)
                
                col = rel_x // item_size
                row = rel_y // item_size
                
                index = row * grid_cols + col
                if 0 <= index < len(unlocks):
                    self.selected_item = unlocks[index]
                    return None
            
            # Check research button
            if self.selected_item:
                details_area = pygame.Rect(self.ui_x + 240, self.ui_y + 50 + (self.ui_height - 70) // 2 + 10, 
                                         self.ui_width - 260, (self.ui_height - 70) // 2 - 10)
                button_rect = pygame.Rect(details_area.x + details_area.width - 150, 
                                         details_area.y + details_area.height - 50, 
                                         140, 40)
                if button_rect.collidepoint(x, y):
                    # Try to unlock the research item
                    return self.try_unlock_item(inventory)
        
        return None
    
    def try_unlock_item(self, inventory):
        """Try to unlock the selected research item"""
        if not self.selected_item or self.selected_item not in self.tech_tree["research_items"]:
            return None
            
        item_data = self.tech_tree["research_items"][self.selected_item]
        
        # Check requirements
        for resource, amount in item_data["cost"].items():
            resource_id = getattr(config, resource.upper(), None)
            if resource_id is None:
                print(f"Unknown resource: {resource}")
                return None
                
            # Find this resource in inventory
            has_enough = False
            slot_idx = -1
            
            for i, slot in enumerate(inventory.slots):
                if slot and slot[0] == resource_id and slot[1] >= amount:
                    has_enough = True
                    slot_idx = i
                    break
                    
            if not has_enough:
                return "missing_resources"
                
            # Consume the resource
            inventory.remove_item(slot_idx, amount)
            
        # Unlock the item
        self.unlocked_tech.add(self.selected_item)
        
        # Also unlock the tier if it's not already
        for tier_id, tier_data in self.tech_tree["tiers"].items():
            if self.selected_item in tier_data["unlocks"]:
                self.unlocked_tech.add(tier_id)
                
        return "unlocked"
    
    def is_close_button_clicked(self, x, y):
        """Check if the close button was clicked"""
        return (self.close_button_x <= x <= self.close_button_x + self.close_button_size and
                self.close_button_y <= y <= self.close_button_y + self.close_button_size)
