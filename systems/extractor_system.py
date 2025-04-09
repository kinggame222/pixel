import time
import random
from core import config

class ExtractorSystem:
    def __init__(self, get_block_at, set_block_at, storage_system, conveyor_system, multi_block_system=None):
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        self.storage_system = storage_system
        self.conveyor_system = conveyor_system
        self.multi_block_system = multi_block_system
        
        # Dictionnaire pour suivre tous les extracteurs actifs
        self.extractors = {}  # {(x, y): { "last_extraction": timestamp, "interval": seconds }}
        
        # Configuration des extracteurs
        self.extraction_interval = 2.0  # Temps en secondes entre chaque extraction
        self.extractor_id = config.ITEM_EXTRACTOR
    
    def register_extractor(self, x, y):
        """Enregistre un nouvel extracteur à la position donnée."""
        # Si nous utilisons le système multi-blocs, obtenons l'origine
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
            
        if origin:
            x, y = origin
        
        # Ajouter l'extracteur avec un temps d'extraction initial aléatoire
        # pour éviter que tous les extracteurs fonctionnent en même temps
        self.extractors[(x, y)] = {
            "last_extraction": time.time() - random.random() * self.extraction_interval,
            "interval": self.extraction_interval,
            "direction": 0  # 0:droite, 1:bas, 2:gauche, 3:haut
        }
        print(f"Extracteur enregistré à ({x}, {y})")
        return True
    
    def set_direction(self, x, y, direction):
        """Définit la direction d'extraction (0-3)."""
        if (x, y) in self.extractors:
            self.extractors[(x, y)]["direction"] = direction % 4
            return True
        return False
    
    def update(self, dt):
        """Met à jour tous les extracteurs, extrait les items et les place sur les convoyeurs."""
        current_time = time.time()
        
        for pos, extractor in self.extractors.items():
            x, y = pos
            # Vérifier si c'est le moment d'extraire
            if current_time - extractor["last_extraction"] >= extractor["interval"]:
                # Chercher un coffre de stockage adjacent
                storage_pos = self._find_adjacent_storage(x, y)
                if storage_pos:
                    # Trouver un convoyeur dans la direction d'extraction
                    conveyor_pos = self._find_conveyor_in_direction(x, y, extractor["direction"])
                    if conveyor_pos:
                        # Extraire un item du stockage et le placer sur le convoyeur
                        item_extracted = self._extract_and_place(storage_pos, conveyor_pos)
                        if item_extracted:
                            # Mise à jour du temps de dernière extraction
                            extractor["last_extraction"] = current_time
    
    def _find_adjacent_storage(self, x, y):
        """Trouve un stockage adjacent à l'extracteur."""
        # L'extracteur est de taille 2x2, vérifier autour de lui
        width, height = 2, 2  # Taille standard de l'extracteur
        
        # Vérifier les quatre côtés de l'extracteur
        directions = [
            [(x-1, y), (x-1, y+1)],  # Gauche
            [(x+width, y), (x+width, y+1)],  # Droite
            [(x, y-1), (x+1, y-1)],  # Haut
            [(x, y+height), (x+1, y+height)]  # Bas
        ]
        
        for points in directions:
            for px, py in points:
                if self.get_block_at(px, py) == config.STORAGE_CHEST:
                    # Trouver l'origine du coffre si c'est un multi-bloc
                    if self.multi_block_system:
                        origin = self.multi_block_system.get_multi_block_origin(px, py)
                        if origin:
                            return origin
                    return (px, py)
        return None
    
    def _find_conveyor_in_direction(self, x, y, direction):
        """Trouve un convoyeur dans la direction spécifiée."""
        width, height = 2, 2  # Taille standard de l'extracteur
        
        if direction == 0:  # Droite
            check_pos = (x + width, y)
        elif direction == 1:  # Bas
            check_pos = (x, y + height)
        elif direction == 2:  # Gauche
            check_pos = (x - 1, y)
        elif direction == 3:  # Haut
            check_pos = (x, y - 1)
        else:
            return None
            
        check_x, check_y = check_pos
        block = self.get_block_at(check_x, check_y)
        
        if block == config.CONVEYOR_BELT or block == config.VERTICAL_CONVEYOR:
            # Si c'est un multi-bloc, obtenir l'origine
            if self.multi_block_system:
                origin = self.multi_block_system.get_multi_block_origin(check_x, check_y)
                if origin:
                    return origin
            return check_pos
        return None
    
    def _extract_and_place(self, storage_pos, conveyor_pos):
        """Extrait un item du stockage et le place sur le convoyeur."""
        # Vérifier si le stockage contient des items
        storage_data = self.storage_system.get_storage_at(*storage_pos)
        if not storage_data or not storage_data["items"]:
            return False
            
        # Prendre le premier item disponible
        item_id, count = next(iter(storage_data["items"].items()))
        
        # Extraire un seul item
        extracted_item = self.storage_system.take_item_from_storage(*storage_pos, item_id, 1)
        if not extracted_item:
            return False
            
        # Placer l'item sur le convoyeur
        placed = self.conveyor_system.place_item_on_conveyor(*conveyor_pos, item_id, 1)
        
        if not placed:
            # Si on ne peut pas placer sur le convoyeur, remettre dans le stockage
            self.storage_system.add_item_to_storage(*storage_pos, item_id, 1)
            return False
            
        return True
