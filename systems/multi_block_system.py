import pygame
from core import config

class MultiBlockSystem:
    def __init__(self, get_block_at_func, set_block_at_func):
        self.multi_block_origins = {}  # Maps (x, y) -> (origin_x, origin_y) for all parts
        self.multi_block_structures = {} # Maps (origin_x, origin_y) -> {"type": block_type, "size": (w, h), "parts": set([(x,y),...])}
        self.block_sizes = { # Store default sizes, load from config if possible
            block_id: data.get("size", (1, 1))
            for block_id, data in config.BLOCKS.items() if data.get("multi_block", False) or data.get("size", (1,1)) != (1,1)
        }
        # Ensure single blocks that need registration (like chests) are included if not already
        if config.STORAGE_CHEST not in self.block_sizes:
             self.block_sizes[config.STORAGE_CHEST] = config.BLOCKS.get(config.STORAGE_CHEST, {}).get("size", (1, 1))
        if config.CRAFTING_TABLE not in self.block_sizes:
             self.block_sizes[config.CRAFTING_TABLE] = config.BLOCKS.get(config.CRAFTING_TABLE, {}).get("size", (1, 1))
        # Add other necessary single blocks here if they interact with this system

        self.get_block_at = get_block_at_func
        self.set_block_at = set_block_at_func
        print(f"[MultiBlockSystem] Initialized with block sizes: {self.block_sizes}") # Debug print

    def register_multi_block(self, origin_x, origin_y, block_type):
        """Registers a multi-block structure at the given origin."""

        if block_type not in self.block_sizes:
            size = config.BLOCKS.get(block_type, {}).get("size")
            if size:
                 self.block_sizes[block_type] = size
            else:
                 return False

        width, height = self.block_sizes[block_type]

        parts = set()
        for dx in range(width):
            for dy in range(height):
                check_x = origin_x + dx
                check_y = origin_y + dy
                if (check_x, check_y) in self.multi_block_origins:
                    return False
                parts.add((check_x, check_y))

        # Register the structure
        structure_data = {
            "type": block_type,
            "size": (width, height),
            "parts": parts
        }
        self.multi_block_structures[(origin_x, origin_y)] = structure_data

        # Map all parts back to the origin
        for part_x, part_y in parts:
            self.multi_block_origins[(part_x, part_y)] = (origin_x, origin_y)

        return True

    def unregister_multi_block(self, any_x, any_y):
        """Removes a multi-block structure given any coordinate within it."""
        origin = self.get_multi_block_origin(any_x, any_y)
        if not origin:
            return False

        if origin in self.multi_block_structures:
            structure_data = self.multi_block_structures[origin]
            parts = structure_data.get("parts", set())

            # Remove parts from the origin mapping
            for part_x, part_y in parts:
                self.multi_block_origins.pop((part_x, part_y), None)

            # Remove the main structure data
            del self.multi_block_structures[origin]

            return True
        else:
             if (any_x, any_y) in self.multi_block_origins:
                 del self.multi_block_origins[(any_x, any_y)]
             return False


    def get_multi_block_origin(self, x, y):
        """Returns the origin (x, y) of the multi-block structure at the given coordinates, or None."""
        return self.multi_block_origins.get((x, y))

    def get_structure_at_origin(self, origin_x, origin_y):
        """Returns the structure data for the given origin, or None."""
        return self.multi_block_structures.get((origin_x, origin_y))

    def is_part_of_structure(self, x, y):
        """Checks if the given coordinates are part of any registered multi-block structure."""
        return (x, y) in self.multi_block_origins

    # Add methods to handle loading/saving if needed
    def get_save_data(self):
        # Return data needed for saving (e.g., the structures dict)
        # Convert sets to lists for JSON compatibility
        save_data = {}
        for origin, data in self.multi_block_structures.items():
            save_data[f"{origin[0]},{origin[1]}"] = {
                "type": data["type"],
                "size": data["size"],
                "parts": list(data["parts"]) # Convert set to list
            }
        return save_data

    def load_save_data(self, data):
        # Load data from a saved state
        self.multi_block_origins.clear()
        self.multi_block_structures.clear()
        loaded_count = 0
        for key, structure_data in data.items():
            try:
                origin_x_str, origin_y_str = key.split(',')
                origin = (int(origin_x_str), int(origin_y_str))
                parts = set(tuple(part) for part in structure_data["parts"]) # Convert list back to set of tuples
                self.multi_block_structures[origin] = {
                    "type": structure_data["type"],
                    "size": tuple(structure_data["size"]),
                    "parts": parts
                }
                # Rebuild the reverse mapping
                for part_x, part_y in parts:
                    self.multi_block_origins[(part_x, part_y)] = origin
                loaded_count += 1
            except Exception as e:
                print(f"Error loading multi-block structure with key {key}: {e}")
            except Exception as e:
                print(f"Error loading multi-block structure with key {key}: {e}")
        print(f"[MultiBlockSystem] Loaded {loaded_count} structures.") # Debug
