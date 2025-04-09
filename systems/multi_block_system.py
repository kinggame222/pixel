from core import config

class MultiBlockSystem:
    def __init__(self, get_block_at, set_block_at):
        """System to manage blocks that span multiple tiles.
        
        Args:
            get_block_at: Function to get block at a position
            set_block_at: Function to set block at a position
        """
        self.get_block_at = get_block_at
        self.set_block_at = set_block_at
        
        # Dictionary to store multi-block metadata: {(origin_x, origin_y): {"type": block_id, "size": (width, height)}}
        self.multi_blocks = {}
        
        # Dictionary to store child block mappings: {(child_x, child_y): (origin_x, origin_y)}
        # Used to find the origin block when clicking on any part of a multi-block
        self.child_to_origin = {}
        
        # Define the size of multi-blocks by type
        self.block_sizes = {
            config.CONVEYOR_BELT: (2, 2),
            config.VERTICAL_CONVEYOR: (2, 2),
            config.ITEM_EXTRACTOR: (2, 2),
            config.STORAGE_CHEST: (3, 3)
        }
    
    def register_multi_block(self, x, y, block_type):
        """Register a new multi-block structure at the given origin position."""
        if block_type not in self.block_sizes:
            return False
        
        width, height = self.block_sizes[block_type]
        
        # Check if the area is free
        for dx in range(width):
            for dy in range(height):
                check_x, check_y = x + dx, y + dy
                if self.get_block_at(check_x, check_y) != config.EMPTY:
                    return False
        
        # Area is free, place the blocks
        self.multi_blocks[(x, y)] = {
            "type": block_type,
            "size": (width, height)
        }
        
        # Place blocks and register child mappings
        for dx in range(width):
            for dy in range(height):
                child_x, child_y = x + dx, y + dy
                self.set_block_at(child_x, child_y, block_type)
                
                # Main block at origin, others are mapped to origin
                if dx > 0 or dy > 0:  # Not the origin
                    self.child_to_origin[(child_x, child_y)] = (x, y)
        
        return True
    
    def get_multi_block_origin(self, x, y):
        """Get the origin position of a multi-block from any of its blocks."""
        if (x, y) in self.multi_blocks:
            return (x, y)  # This is already an origin
        elif (x, y) in self.child_to_origin:
            return self.child_to_origin[(x, y)]
        return None
    
    def is_multi_block(self, x, y):
        """Check if the position is part of a multi-block structure."""
        return (x, y) in self.multi_blocks or (x, y) in self.child_to_origin
    
    def remove_multi_block(self, x, y):
        """Remove a multi-block structure given any position within it."""
        origin = self.get_multi_block_origin(x, y)
        if not origin:
            return False
        
        # Get block data
        block_data = self.multi_blocks.get(origin)
        if not block_data:
            return False
        
        width, height = block_data["size"]
        
        # Remove all blocks and child mappings
        for dx in range(width):
            for dy in range(height):
                child_x, child_y = origin[0] + dx, origin[1] + dy
                
                # Remove from child mappings
                self.child_to_origin.pop((child_x, child_y), None)
                
                # Set to empty in world
                self.set_block_at(child_x, child_y, config.EMPTY)
        
        # Remove multi-block entry
        self.multi_blocks.pop(origin)
        return True

    def get_connection_points(self, x, y, block_type):
        """Get potential connection points for a multi-block."""
        origin = self.get_multi_block_origin(x, y)
        if not origin:
            return []
        
        # Get block data
        block_data = self.multi_blocks.get(origin)
        if not block_data:
            return []
        
        width, height = block_data["size"]
        x, y = origin
        
        # Define connection points based on block type
        connection_points = []
        
        if block_type == config.CONVEYOR_BELT:
            # For conveyor belt, connections depend on direction
            direction = 0  # Default direction is right
            
            # Look up the direction if this conveyor is registered in the conveyor system
            from systems.conveyor_system import conveyor_system
            if hasattr(conveyor_system, 'conveyors') and (x, y) in conveyor_system.conveyors:
                direction = conveyor_system.conveyors[(x, y)].get("direction", 0)
            
            # Add input/output points based on direction
            if direction == 0:  # Right
                connection_points.append({"type": "input", "pos": (x-1, y)})
                connection_points.append({"type": "output", "pos": (x+width, y)})
            elif direction == 1:  # Down
                connection_points.append({"type": "input", "pos": (x, y-1)})
                connection_points.append({"type": "output", "pos": (x, y+height)})
            elif direction == 2:  # Left
                connection_points.append({"type": "input", "pos": (x+width, y)})
                connection_points.append({"type": "output", "pos": (x-1, y)})
            elif direction == 3:  # Up
                connection_points.append({"type": "input", "pos": (x, y+height)})
                connection_points.append({"type": "output", "pos": (x, y-1)})
                
        elif block_type == config.STORAGE_CHEST:
            # Storage chest has input/output points on all sides
            connection_points.extend([
                {"type": "io", "pos": (x-1, y+height//2)},  # Left
                {"type": "io", "pos": (x+width, y+height//2)},  # Right
                {"type": "io", "pos": (x+width//2, y-1)},  # Top
                {"type": "io", "pos": (x+width//2, y+height)}  # Bottom
            ])
            
        elif block_type == config.ITEM_EXTRACTOR:
            # Extractor has specific input/output sides
            connection_points.append({"type": "input", "pos": (x-1, y)})
            connection_points.append({"type": "output", "pos": (x+width, y)})
            
        return connection_points
