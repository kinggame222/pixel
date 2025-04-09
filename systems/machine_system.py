import time
import json
import os
from core import config

class MachineSystem:
    def __init__(self, get_block_at, set_block_at):
        # Store references to world interaction functions
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        
        # Dictionary to track machines: {(x, y): MachineData}
        self.machines = {}
        
        # Make sure ORE_PROCESSOR exists in config
        self.ore_processor_id = getattr(config, "ORE_PROCESSOR", 12)
        
        # Machine dimensions
        self.machine_sizes = {
            self.ore_processor_id: (4, 6)  # 4 blocks wide, 6 blocks tall
        }
        
        # Load recipes from JSON file
        self.recipes = self.load_recipes()
        
        # Currently open machine position (for UI)
        self.active_machine = None
        
        print("Machine System initialized with ore processor ID:", self.ore_processor_id)
        print(f"Loaded {len(self.recipes)} recipes")
    
    def load_recipes(self):
        """Load recipes from JSON file."""
        recipes = {}
        recipe_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "recipes.json")
        
        try:
            if os.path.exists(recipe_file):
                with open(recipe_file, "r") as f:
                    all_recipes = json.load(f)
                    
                # Extract ore processor recipes
                if "ore_processor" in all_recipes and "recipes" in all_recipes["ore_processor"]:
                    for recipe in all_recipes["ore_processor"]["recipes"]:
                        input_id = recipe["input_id"]
                        recipes[input_id] = {
                            "output": recipe["output_id"],
                            "process_time": recipe["process_time"],
                            "output_count": recipe["output_count"],
                            "description": recipe.get("description", "")
                        }
                    print(f"Successfully loaded {len(recipes)} recipes from {recipe_file}")
            else:
                print(f"Recipe file not found at {recipe_file}, using fallback recipes")
        except Exception as e:
            print(f"Error loading recipes: {e}, using fallback recipes")
        
        # Fallback recipes if file not found or error occurs
        if not recipes:
            # Get block IDs for recipes with fallbacks
            iron_ore_id = getattr(config, "IRON_ORE", 6)
            iron_bar_id = getattr(config, "IRON_BAR", 13)
            diamond_ore_id = getattr(config, "DIAMOND_ORE", 7)
            diamond_crystal_id = getattr(config, "DIAMOND_CRYSTAL", 14)
            
            # Fallback recipes for processing ores
            recipes = {
                iron_ore_id: {
                    "output": iron_bar_id,
                    "process_time": 5.0,
                    "output_count": 1
                },
                diamond_ore_id: {
                    "output": diamond_crystal_id,
                    "process_time": 10.0,
                    "output_count": 1
                }
            }
            
        return recipes
    
    def register_machine(self, x, y):
        """Register a new machine at the given position."""
        self.machines[(x, y)] = {
            "input": None,  # (block_type, count)
            "output": None,  # (block_type, count)
            "process_start": None,  # Time when processing started
            "process_duration": None  # Duration of current process
        }
        print(f"Machine registered at ({x}, {y})")
        return True
    
    def get_machine_size(self, block_type):
        """Get the size of a machine type."""
        return self.machine_sizes.get(block_type, (1, 1))
    
    def remove_machine(self, x, y):
        """Remove a machine from the registry."""
        if (x, y) in self.machines:
            machine = self.machines.pop((x, y))
            # Return any items in the machine to be dropped
            items = []
            if machine["input"]:
                items.append(machine["input"])
            if machine["output"]:
                items.append(machine["output"])
            return items
        return []
    
    def is_machine_position(self, x, y):
        """Check if there is a machine at the given position."""
        # First check if this is the origin position of a machine
        if (x, y) in self.machines:
            return True
        
        # Then check if this position is within the bounds of a machine
        for machine_pos, _ in self.machines.items():
            machine_x, machine_y = machine_pos
            machine_type = self.get_block_at(machine_x, machine_y)
            width, height = self.get_machine_size(machine_type)
            
            if (machine_x <= x < machine_x + width and 
                machine_y <= y < machine_y + height):
                return True
        
        return False
    
    def get_machine_origin(self, x, y):
        """Get the origin position of a machine at the given position."""
        # If this is already the origin, return it
        if (x, y) in self.machines:
            return (x, y)
        
        # Otherwise check if this position is within a machine
        for machine_pos, _ in self.machines.items():
            machine_x, machine_y = machine_pos
            machine_type = self.get_block_at(machine_x, machine_y)
            
            # Make sure the block type exists and is valid
            if machine_type is None or machine_type not in self.machine_sizes:
                continue
                
            width, height = self.get_machine_size(machine_type)
            
            if (machine_x <= x < machine_x + width and 
                machine_y <= y < machine_y + height):
                return machine_pos
        
        return None
        
    def open_machine_ui(self, x, y):
        """Open the UI for interacting with a machine."""
        machine_origin = self.get_machine_origin(x, y)
        if machine_origin:
            self.active_machine = machine_origin
            return True
        return False
    
    def close_machine_ui(self):
        """Close the machine UI."""
        self.active_machine = None
    
    def add_item_to_machine(self, machine_pos, block_type, count=1):
        """Add an item to the input slot of a machine."""
        if machine_pos in self.machines:
            machine = self.machines[machine_pos]
            
            # Check if input slot is empty or has same item
            if machine["input"] is None:
                machine["input"] = (block_type, count)
                # Check if we can process this item and start processing if possible
                if block_type in self.recipes:
                    self.start_processing(machine_pos)
                return True
            elif machine["input"][0] == block_type:
                machine["input"] = (block_type, machine["input"][1] + count)
                # Check if we were waiting for more input to start processing
                if machine["process_start"] is None and block_type in self.recipes:
                    self.start_processing(machine_pos)
                return True
        return False
    
    def take_item_from_machine(self, machine_pos, output_slot=True):
        """Take an item from the machine (output slot by default)."""
        if machine_pos in self.machines:
            machine = self.machines[machine_pos]
            
            # Default to output slot, but allow taking from input if specified
            target_slot = "output" if output_slot else "input"
            
            if machine[target_slot] is not None:
                item = machine[target_slot]
                machine[target_slot] = None
                return item
        
        return None
    
    def start_processing(self, machine_pos):
        """Start processing the input item if a valid recipe exists."""
        if machine_pos in self.machines:
            machine = self.machines[machine_pos]
            
            # Check if machine has input but no output and isn't already processing
            if (machine["input"] and 
                (machine["output"] is None or 
                 machine["output"][0] == self.recipes.get(machine["input"][0], {}).get("output")) and
                machine["process_start"] is None):
                
                input_type, input_count = machine["input"]
                
                # Check if we have a recipe for this input
                if input_type in self.recipes:
                    # Start processing
                    machine["process_start"] = time.time()
                    machine["process_duration"] = self.recipes[input_type]["process_time"]
                    return True
        
        return False
    
    def update(self):
        """Update all machines' processing status."""
        current_time = time.time()
        
        for pos, machine in list(self.machines.items()):
            # Skip machines that aren't processing
            if machine["process_start"] is None:
                # Check if we can start processing (might have been waiting for materials)
                if machine["input"] is not None and machine["input"][0] in self.recipes:
                    self.start_processing(pos)
                continue
            
            # Check if processing is complete
            if current_time >= machine["process_start"] + machine["process_duration"]:
                input_type, input_count = machine["input"]
                
                # Check if we still have a valid recipe
                if input_type in self.recipes:
                    # Get recipe details
                    recipe = self.recipes[input_type]
                    
                    # Consume one input item
                    if input_count > 1:
                        machine["input"] = (input_type, input_count - 1)
                    else:
                        machine["input"] = None
                    
                    # Generate output
                    output_type = recipe["output"]
                    output_count = recipe["output_count"]
                    
                    if machine["output"] is None:
                        machine["output"] = (output_type, output_count)
                    elif machine["output"][0] == output_type:
                        machine["output"] = (output_type, machine["output"][1] + output_count)
                    else:
                        # Different output type - can't output
                        pass
                    
                    # Reset processing
                    machine["process_start"] = None
                    machine["process_duration"] = None
                    
                    # If there's still input and no output slot conflict, start processing again
                    if machine["input"] is not None:
                        self.start_processing(pos)
    
    def get_machine_data(self, machine_pos):
        """Get data about a specific machine."""
        return self.machines.get(machine_pos, None)
    
    def get_machine_progress(self, machine_pos):
        """Get the current processing progress of a machine (0.0 to 1.0)."""
        if machine_pos in self.machines:
            machine = self.machines[machine_pos]
            
            if machine["process_start"] is not None and machine["process_duration"] > 0:
                elapsed = time.time() - machine["process_start"]
                return min(1.0, elapsed / machine["process_duration"])
        
        return 0.0
    
    def get_active_machine(self):
        """Get the position of the currently active machine for UI."""
        return self.active_machine
