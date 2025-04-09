import json
import os
from core import config

class CraftingSystem:
    def __init__(self, get_block_at, set_block_at):
        # Store references to world interaction functions
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        
        # Dictionary to track crafting tables: {(x, y): TableData}
        self.tables = {}
        
        # Get crafting table block ID
        self.crafting_table_id = getattr(config, "CRAFTING_TABLE", 15)
        
        # Crafting table dimensions (1x1)
        self.table_size = (1, 1)
        
        # Load recipes from JSON file
        self.recipes = self.load_recipes()
        
        # Currently open crafting table position (for UI)
        self.active_table = None
        
        print(f"Crafting System initialized with table ID: {self.crafting_table_id}")
        print(f"Loaded {len(self.recipes)} crafting recipes")
        
    def load_recipes(self):
        """Load crafting recipes from JSON file."""
        recipes = []
        recipe_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.json")
        
        try:
            if os.path.exists(recipe_file):
                with open(recipe_file, "r") as f:
                    all_recipes = json.load(f)
                    
                # Extract crafting table recipes
                if "crafting_table" in all_recipes and "recipes" in all_recipes["crafting_table"]:
                    recipes = all_recipes["crafting_table"]["recipes"]
                    print(f"Successfully loaded {len(recipes)} crafting recipes from {recipe_file}")
            else:
                print(f"Recipe file not found at {recipe_file}, using fallback recipes")
        except Exception as e:
            print(f"Error loading crafting recipes: {e}, using fallback recipes")
            
        # Fallback recipes if file not found or error occurs
        if not recipes:
            wood_id = getattr(config, "WOOD", 5)
            crafting_table_id = self.crafting_table_id
            
            # Default recipes
            recipes = [
                {
                    "input": [{"id": wood_id, "count": 4}],
                    "output": {"id": crafting_table_id, "count": 1},
                    "description": "4 Wood → Crafting Table"
                }
            ]
            
        return recipes
        
    def register_table(self, x, y):
        """Register a new crafting table at the given position."""
        self.tables[(x, y)] = {
            "grid": [[None for _ in range(3)] for _ in range(3)],  # 3x3 crafting grid
            "output": None,  # Output slot
        }
        print(f"Crafting table registered at ({x}, {y})")
        return True
        
    def is_table_position(self, x, y):
        """Check if there is a crafting table at the given position."""
        return (x, y) in self.tables or self.get_block_at(x, y) == self.crafting_table_id
        
    def get_table_origin(self, x, y):
        """Get the origin position of a crafting table."""
        if (x, y) in self.tables:
            return (x, y)
            
        if self.get_block_at(x, y) == self.crafting_table_id:
            return (x, y)
            
        return None
        
    def open_table_ui(self, x, y):
        """Open the UI for interacting with a crafting table."""
        table_origin = self.get_table_origin(x, y)
        if table_origin:
            # Register the table if it doesn't exist yet
            if table_origin not in self.tables:
                self.register_table(*table_origin)
                
            self.active_table = table_origin
            return True
        return False
        
    def close_table_ui(self):
        """Close the crafting table UI."""
        self.active_table = None
        
    def add_item_to_grid(self, table_pos, slot_x, slot_y, block_type, count=1):
        """Add an item to the crafting grid."""
        if table_pos in self.tables:
            table = self.tables[table_pos]
            
            # Check grid bounds
            if 0 <= slot_x < 3 and 0 <= slot_y < 3:
                # Check if slot is empty or has same item
                if table["grid"][slot_y][slot_x] is None:
                    table["grid"][slot_y][slot_x] = (block_type, count)
                    self.update_recipe(table_pos)
                    return True
                elif table["grid"][slot_y][slot_x][0] == block_type:
                    # Add to existing stack
                    current_block, current_count = table["grid"][slot_y][slot_x]
                    table["grid"][slot_y][slot_x] = (current_block, current_count + count)
                    self.update_recipe(table_pos)
                    return True
                    
        return False
        
    def take_item_from_grid(self, table_pos, slot_x, slot_y):
        """Take an item from the crafting grid."""
        if table_pos in self.tables:
            table = self.tables[table_pos]
            
            # Check grid bounds
            if 0 <= slot_x < 3 and 0 <= slot_y < 3:
                if table["grid"][slot_y][slot_x] is not None:
                    item = table["grid"][slot_y][slot_x]
                    table["grid"][slot_y][slot_x] = None
                    self.update_recipe(table_pos)
                    return item
                    
        return None
        
    def take_output_item(self, table_pos):
        """Take the output item and consume crafting ingredients."""
        if table_pos in self.tables:
            table = self.tables[table_pos]
            
            if table["output"] is not None:
                output_item = table["output"]
                
                # Find the matching recipe to know how to consume ingredients
                for recipe in self.recipes:
                    if (recipe["output"]["id"] == output_item[0] and
                        recipe["output"]["count"] == output_item[1]):
                        
                        # Consume ingredients based on recipe
                        for ingredient in recipe["input"]:
                            ingredient_id = ingredient["id"]
                            ingredient_count = ingredient["count"]
                            
                            # Find this ingredient in the grid
                            for y in range(3):
                                for x in range(3):
                                    if (table["grid"][y][x] is not None and
                                        table["grid"][y][x][0] == ingredient_id):
                                        
                                        current_id, current_count = table["grid"][y][x]
                                        
                                        # Consume the ingredient
                                        if current_count > ingredient_count:
                                            table["grid"][y][x] = (current_id, current_count - ingredient_count)
                                        else:
                                            table["grid"][y][x] = None
                                            
                                        ingredient_count = 0
                                        break
                                        
                                if ingredient_count == 0:
                                    break
                
                # Clear output and update recipe
                table["output"] = None
                self.update_recipe(table_pos)
                
                return output_item
                
        return None
        
    def update_recipe(self, table_pos):
        """Check if the current grid matches any recipe and update the output slot."""
        if table_pos in self.tables:
            table = self.tables[table_pos]
            
            # Convert grid to format for recipe checking
            ingredient_counts = {}
            
            for y in range(3):
                for x in range(3):
                    if table["grid"][y][x] is not None:
                        block_id, count = table["grid"][y][x]
                        if block_id in ingredient_counts:
                            ingredient_counts[block_id] += count
                        else:
                            ingredient_counts[block_id] = count
            
            # Check if ingredients match any recipe
            for recipe in self.recipes:
                match = True
                
                # Check if we have all required ingredients
                for ingredient in recipe["input"]:
                    ingredient_id = ingredient["id"]
                    required_count = ingredient["count"]
                    
                    if (ingredient_id not in ingredient_counts or
                        ingredient_counts[ingredient_id] < required_count):
                        match = False
                        break
                        
                if match:
                    # Recipe matches! Set the output
                    output_id = recipe["output"]["id"]
                    output_count = recipe["output"]["count"]
                    table["output"] = (output_id, output_count)
                    return
                    
            # No recipe matches
            table["output"] = None
            
    def get_table_data(self, table_pos):
        """Get data about a specific crafting table."""
        return self.tables.get(table_pos, None)
        
    def get_active_table(self):
        """Get the position of the currently active crafting table for UI."""
        return self.active_table
