import config
import time
from processor_recipes import processor_recipes

class MachineSystem:
    def __init__(self, get_block_at, set_block_at):
        # Store references to world interaction functions
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        
        # Dictionary to track machines: {(x, y): MachineData}
        self.machines = {}
        
        # Machine dimensions
        self.machine_sizes = {
            config.ORE_PROCESSOR: (4, 6)  # 4 blocks wide, 6 blocks tall
        }
        
        # Currently open machine position (for UI)
        self.active_machine = None
    
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
                if processor_recipes.can_process(block_type):
                    self.start_processing(machine_pos)
                return True
            elif machine["input"][0] == block_type:
                machine["input"] = (block_type, machine["input"][1] + count)
                # Check if we were waiting for more input to start processing
                if machine["process_start"] is None and processor_recipes.can_process(block_type):
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
                 machine["output"][0] == processor_recipes.get_output(machine["input"][0])) and
                machine["process_start"] is None):
                
                input_type, input_count = machine["input"]
                
                # Check if we have a recipe for this input
                if processor_recipes.can_process(input_type):
                    # Check if we have enough input materials
                    required_input = processor_recipes.get_required_input(input_type)
                    if input_count >= required_input:
                        # Start processing
                        machine["process_start"] = time.time()
                        machine["process_duration"] = processor_recipes.get_processing_time(input_type)
                        return True
        
        return False
    
    def update(self):
        """Update all machines' processing status."""
        current_time = time.time()
        
        for pos, machine in list(self.machines.items()):
            # Skip machines that aren't processing
            if machine["process_start"] is None:
                # Check if we can start processing (might have been waiting for materials)
                if machine["input"] is not None and processor_recipes.can_process(machine["input"][0]):
                    self.start_processing(pos)
                continue
            
            # Check if processing is complete
            if current_time >= machine["process_start"] + machine["process_duration"]:
                input_type, input_count = machine["input"]
                
                # Check if we still have a valid recipe
                if processor_recipes.can_process(input_type):
                    # Get recipe details
                    output_type = processor_recipes.get_output(input_type)
                    output_count = processor_recipes.get_output_count(input_type)
                    required_input = processor_recipes.get_required_input(input_type)
                    
                    # Consume the input
                    if input_count > required_input:
                        machine["input"] = (input_type, input_count - required_input)
                    else:
                        machine["input"] = None
                    
                    # Generate output
                    if machine["output"] is None:
                        machine["output"] = (output_type, output_count)
                    elif machine["output"][0] == output_type:
                        # Add to existing output
                        machine["output"] = (output_type, machine["output"][1] + output_count)
                    
                    # Reset processing
                    machine["process_start"] = None
                    machine["process_duration"] = None
                    
                    # If there's still input and no output slot conflict, start processing again
                    if machine["input"] is not None and machine["input"][1] >= required_input:
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
