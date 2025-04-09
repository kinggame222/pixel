import pygame
from core import config

class ConveyorPlacementSystem:
    def __init__(self, get_block_at, set_block_at, multi_block_system, conveyor_system, inventory):
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        self.multi_block_system = multi_block_system
        self.conveyor_system = conveyor_system
        self.inventory = inventory
        
        # Modes de placement
        self.active = False  # Si le mode de placement est actif
        self.placement_mode = 0  # 0: ligne droite, 1: diagonale, 2: zig-zag
        self.direction = 0  # 0: droite, 1: bas, 2: gauche, 3: haut
        self.max_length = 20  # Longueur maximale de convoyeurs à placer
        self.preview_blocks = []  # Blocs à prévisualiser avant placement
        
    def toggle_active(self):
        """Active ou désactive le mode de placement rapide."""
        self.active = not self.active
        self.preview_blocks = []
        return self.active
        
    def cycle_mode(self):
        """Change le mode de placement."""
        self.placement_mode = (self.placement_mode + 1) % 3
        return ["Ligne Droite", "Diagonale", "Zig-Zag"][self.placement_mode]
        
    def set_direction(self, direction):
        """Définit la direction de placement (0-3)."""
        self.direction = direction % 4
        
    def calculate_preview(self, start_x, start_y):
        """Calcule les positions où les convoyeurs seraient placés."""
        self.preview_blocks = []
        
        # Vérifier le type de convoyeur sélectionné
        selected_item = self.inventory.get_selected_item()
        if not selected_item or (selected_item[0] != config.CONVEYOR_BELT 
                                and selected_item[0] != config.VERTICAL_CONVEYOR):
            return []
            
        block_type = selected_item[0]
        count_available = selected_item[1]
        
        # Obtenir la taille du convoyeur (généralement 2x2)
        width, height = self.multi_block_system.block_sizes.get(block_type, (2, 2))
        
        # Vérifier combien de convoyeurs peuvent être placés à partir de la position initiale
        positions = []
        
        # Calculer les positions en fonction du mode et de la direction
        if self.placement_mode == 0:  # Ligne droite
            dx, dy = 0, 0
            if self.direction == 0: dx = width  # Droite
            elif self.direction == 1: dy = height  # Bas
            elif self.direction == 2: dx = -width  # Gauche
            elif self.direction == 3: dy = -height  # Haut
            
            for i in range(min(self.max_length, count_available)):
                next_x = start_x + i * dx
                next_y = start_y + i * dy
                
                # Vérifier si l'espace est libre pour un bloc 2x2
                space_available = True
                for check_x in range(next_x, next_x + width):
                    for check_y in range(next_y, next_y + height):
                        if self.get_block_at(check_x, check_y) != config.EMPTY:
                            space_available = False
                            break
                    if not space_available:
                        break
                
                if space_available:
                    positions.append((next_x, next_y))
                else:
                    break
        
        elif self.placement_mode == 1:  # Diagonale
            dx, dy = 0, 0
            if self.direction == 0: dx, dy = width, height  # Diagonale bas-droite
            elif self.direction == 1: dx, dy = -width, height  # Diagonale bas-gauche
            elif self.direction == 2: dx, dy = -width, -height  # Diagonale haut-gauche
            elif self.direction == 3: dx, dy = width, -height  # Diagonale haut-droite
            
            for i in range(min(self.max_length, count_available)):
                next_x = start_x + i * dx
                next_y = start_y + i * dy
                
                # Vérifier si l'espace est libre
                space_available = True
                for check_x in range(next_x, next_x + width):
                    for check_y in range(next_y, next_y + height):
                        if self.get_block_at(check_x, check_y) != config.EMPTY:
                            space_available = False
                            break
                    if not space_available:
                        break
                
                if space_available:
                    positions.append((next_x, next_y))
                else:
                    break
        
        elif self.placement_mode == 2:  # Zig-zag
            horizontal = self.direction in [0, 2]  # Horizontal si direction est droite/gauche
            dx1, dy1 = (width if horizontal else 0), (0 if horizontal else height)
            if self.direction in [2, 3]:  # Inverser si gauche/haut
                dx1, dy1 = -dx1, -dy1
            
            # La seconde direction est perpendiculaire
            dx2, dy2 = (0 if horizontal else width), (height if horizontal else 0)
            if (self.direction == 1) or (self.direction == 2):  # Ajuster en fonction de la direction
                dx2, dy2 = -dx2, -dy2
            
            max_zigzag = min(self.max_length // 2, count_available // 2)
            for i in range(max_zigzag):
                # Premier segment du zig
                next_x = start_x + i * (dx1 + dx2)
                next_y = start_y + i * (dy1 + dy2)
                
                # Vérifier le premier bloc du zig
                space_available = True
                for check_x in range(next_x, next_x + width):
                    for check_y in range(next_y, next_y + height):
                        if self.get_block_at(check_x, check_y) != config.EMPTY:
                            space_available = False
                            break
                    if not space_available:
                        break
                
                if space_available:
                    positions.append((next_x, next_y))
                else:
                    break
                
                # Second segment du zag
                next_x = next_x + dx1
                next_y = next_y + dy1
                
                # Vérifier le second bloc du zag
                space_available = True
                for check_x in range(next_x, next_x + width):
                    for check_y in range(next_y, next_y + height):
                        if self.get_block_at(check_x, check_y) != config.EMPTY:
                            space_available = False
                            break
                    if not space_available:
                        break
                
                if space_available:
                    positions.append((next_x, next_y))
                else:
                    break
        
        self.preview_blocks = positions
        return positions
        
    def place_conveyors(self, start_x, start_y):
        """Place une série de convoyeurs à partir de la position initiale."""
        # Calculer d'abord où seront les convoyeurs
        self.calculate_preview(start_x, start_y)
        
        if not self.preview_blocks:
            return False
            
        # Récupérer le type de convoyeur et le nombre disponible
        selected_item = self.inventory.get_selected_item()
        if not selected_item:
            return False
            
        block_type = selected_item[0]
        count_available = selected_item[1]
        
        # Placer les convoyeurs un à un
        conveyors_placed = 0
        for x, y in self.preview_blocks:
            if conveyors_placed >= count_available:
                break
                
            # Utiliser le système multi-bloc pour placer le convoyeur
            if self.multi_block_system.register_multi_block(x, y, block_type):
                # Enregistrer avec la direction actuelle
                self.conveyor_system.register_conveyor(x, y, self.direction)
                conveyors_placed += 1
            else:
                break
                
        # Mettre à jour l'inventaire
        if conveyors_placed > 0:
            self.inventory.remove_item(self.inventory.selected_slot, conveyors_placed)
            return True
            
        return False
        
    def draw_preview(self, screen, camera_x, camera_y):
        """Dessine une prévisualisation des convoyeurs qui seraient placés."""
        if not self.active or not self.preview_blocks:
            return
            
        # Obtenir le type de bloc pour la prévisualisation
        selected_item = self.inventory.get_selected_item()
        if not selected_item:
            return
            
        block_type = selected_item[0]
        width, height = self.multi_block_system.block_sizes.get(block_type, (2, 2))
        
        for pos in self.preview_blocks:
            x, y = pos
            screen_x = x * config.PIXEL_SIZE - camera_x
            screen_y = y * config.PIXEL_SIZE - camera_y
            
            # Dessiner un cadre semi-transparent pour indiquer où seront placés les convoyeurs
            s = pygame.Surface((width * config.PIXEL_SIZE, height * config.PIXEL_SIZE), pygame.SRCALPHA)
            
            # Extraire la couleur du bloc et ajouter la transparence
            color = list(config.BLOCKS[block_type]["color"]) + [128]  # Alpha à 128 (semi-transparent)
            s.fill(color)
            
            # Dessiner une flèche pour indiquer la direction
            arrow_color = (0, 0, 0, 200)
            center_x = width * config.PIXEL_SIZE // 2
            center_y = height * config.PIXEL_SIZE // 2
            arrow_size = min(width, height) * config.PIXEL_SIZE // 3
            
            if self.direction == 0:  # Droite
                pygame.draw.polygon(s, arrow_color, [
                    (center_x, center_y - arrow_size//2),
                    (center_x + arrow_size, center_y),
                    (center_x, center_y + arrow_size//2)
                ])
            elif self.direction == 1:  # Bas
                pygame.draw.polygon(s, arrow_color, [
                    (center_x - arrow_size//2, center_y),
                    (center_x + arrow_size//2, center_y),
                    (center_x, center_y + arrow_size)
                ])
            elif self.direction == 2:  # Gauche
                pygame.draw.polygon(s, arrow_color, [
                    (center_x, center_y - arrow_size//2),
                    (center_x - arrow_size, center_y),
                    (center_x, center_y + arrow_size//2)
                ])
            elif self.direction == 3:  # Haut
                pygame.draw.polygon(s, arrow_color, [
                    (center_x - arrow_size//2, center_y),
                    (center_x + arrow_size//2, center_y),
                    (center_x, center_y - arrow_size)
                ])
                
            screen.blit(s, (screen_x, screen_y))
