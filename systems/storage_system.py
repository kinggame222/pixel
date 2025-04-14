import json
import os
import uuid
from core import config

class StorageSystem:
    def __init__(self, get_block_at, set_block_at, multi_block_system=None):
        # Store references to world interaction functions
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        self.multi_block_system = multi_block_system
        
        # Dictionary to track storages: {(x, y): StorageData}
        self.storages = {}
        
        # Dictionary to map storage IDs to positions: {storage_id: (x, y)}
        # This helps maintain persistence when loading/saving
        self.storage_ids = {}
        
        # Get storage block IDs with fallbacks
        self.storage_chest_id = getattr(config, "STORAGE_CHEST", 16)
    
    def register_storage(self, x, y):
        """Register a new storage at the given position."""
        # Check if this is an origin block from the multi-block system
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
            
        if origin:
            x, y = origin  # Use the origin coordinates
            
        # Larger chests have more capacity
        capacity = 200  # For 3x3 storage chests
        
        # Generate a unique ID for this storage
        storage_id = str(uuid.uuid4())
        
        self.storages[(x, y)] = {
            "items": {},  # Dictionary of {item_id: count}
            "capacity": capacity,
            "used_space": 0,
            "linked_storages": [],  # List of (x, y) positions of linked storages
            "id": storage_id  # Add unique ID for persistence
        }
        
        # Map ID to position for quick lookups
        self.storage_ids[storage_id] = (x, y)
        
        print(f"Storage registered at ({x}, {y}) with ID {storage_id}")
        return True
    
    def is_storage_position(self, x, y):
        """Check if there is a storage at the given position."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        return (x, y) in self.storages or self.get_block_at(x, y) == self.storage_chest_id
    
    def get_storage_at(self, x, y):
        """Get the storage at the given position."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) in self.storages:
            return self.storages[(x, y)]
        return None
    
    def add_item_to_storage(self, x, y, item_id, count=1):
        """Add an item to the storage at the given position."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) not in self.storages:
            self.register_storage(x, y)
        
        storage = self.storages[(x, y)]
        
        # Check if there's space available
        if storage["used_space"] + count > storage["capacity"]:
            return False
        
        # Add item to storage
        if item_id in storage["items"]:
            storage["items"][item_id] += count
        else:
            storage["items"][item_id] = count
        
        storage["used_space"] += count
        return True
    
    def take_item_from_storage(self, x, y, item_id, count=1):
        """Take an item from the storage at the given position."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) not in self.storages:
            return None
        
        storage = self.storages[(x, y)]
        
        # Check if the item exists and has enough count
        if item_id not in storage["items"] or storage["items"][item_id] < count:
            return None
        
        # Take the item
        storage["items"][item_id] -= count
        storage["used_space"] -= count
        
        # Remove the item entry if count is 0
        if storage["items"][item_id] == 0:
            del storage["items"][item_id]
        
        return (item_id, count)
    
    def get_available_space(self, x, y):
        """Get the available space in the storage at the given position."""
        # Check if this is part of a multi-block
        origin = None
        if self.multi_block_system:
            origin = self.multi_block_system.get_multi_block_origin(x, y)
        
        if origin:
            x, y = origin
            
        if (x, y) not in self.storages:
            return 0
        
        storage = self.storages[(x, y)]
        return storage["capacity"] - storage["used_space"]
    
    def save_to_file(self, filename="storage_data.json"):
        """Save all storage data to a JSON file."""
        storage_data = {}
        
        for pos, storage in self.storages.items():
            x, y = pos
            storage_id = storage.get("id")
            
            if not storage_id:
                # Generate an ID if one doesn't exist
                storage_id = str(uuid.uuid4())
                storage["id"] = storage_id
                self.storage_ids[storage_id] = pos
                
            # Convert items dictionary keys to strings for JSON
            items_dict = {str(item_id): count for item_id, count in storage["items"].items()}
            
            # Save essential data
            storage_data[storage_id] = {
                "position": [x, y],
                "items": items_dict,
                "capacity": storage["capacity"],
                "used_space": storage["used_space"]
            }
        
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Save to file
        filepath = os.path.join(data_dir, filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(storage_data, f)
            print(f"Storage data saved to {filepath}")
            return True
        except Exception as e:
            print(f"Error saving storage data: {e}")
            return False
    
    def load_from_file(self, filename="storage_data.json"):
        """Load all storage data from a JSON file."""
        # Reset current data
        self.storages = {}
        self.storage_ids = {}
        
        # Create data directory path
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        filepath = os.path.join(data_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"No storage data file found at {filepath}")
            return False
            
        try:
            with open(filepath, 'r') as f:
                storage_data = json.load(f)
                
            for storage_id, data in storage_data.items():
                # Get position
                x, y = data["position"]
                
                # Verify there's actually a storage block at this position
                if self.get_block_at(x, y) != self.storage_chest_id:
                    print(f"Warning: No storage chest found at {x}, {y}, skipping...")
                    continue
                    
                # Convert item IDs back to integers
                items = {int(item_id): count for item_id, count in data["items"].items()}
                
                # Create storage entry
                self.storages[(x, y)] = {
                    "items": items,
                    "capacity": data["capacity"],
                    "used_space": data["used_space"],
                    "linked_storages": [],  # Reset linked storages
                    "id": storage_id
                }
                
                # Add to ID mapping
                self.storage_ids[storage_id] = (x, y)
            
            print(f"Loaded {len(self.storages)} storage chests from {filepath}")
            return True
            
        except Exception as e:
            print(f"Error loading storage data: {e}")
            return False

    def get_all_storage_data(self):
        """Returns all storage data in a serializable format."""
        serializable_data = {}
        for (x, y), data in self.storages.items():
            # Convert tuple key (x, y) to string "x,y" for JSON compatibility
            key = f"{x},{y}"
            # Ensure item IDs in items dict are strings for JSON keys
            string_items = {str(item_id): count for item_id, count in data["items"].items()}
            serializable_data[key] = {
                "id": str(data["id"]),  # Store UUID as string
                "items": string_items
            }
        return serializable_data

    def load_all_storage_data(self, data):
        """Loads storage data from a dictionary (usually from JSON)."""
        self.storages.clear()  # Clear existing data
        for key, storage_data in data.items():
            try:
                x_str, y_str = key.split(',')
                x, y = int(x_str), int(y_str)
                origin = (x, y)

                # Convert item ID keys back to integers
                loaded_items = {int(item_id_str): count for item_id_str, count in storage_data.get("items", {}).items()}

                self.storages[origin] = {
                    "id": uuid.UUID(storage_data.get("id", str(uuid.uuid4()))),  # Load UUID or generate new if missing
                    "items": loaded_items
                }
            except Exception as e:
                print(f"Error loading storage data for key '{key}': {e}")
        print(f"Finished loading data for {len(self.storages)} storage units.")
