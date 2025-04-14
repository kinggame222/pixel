import random
import time
from core import config
from world.chunks import get_chunk_coords, mark_chunk_modified # Import necessary functions

class AutoMinerSystem:
    def __init__(self, get_block_at_func, set_block_at_func, storage_system):
        self.miners = {}  # (x, y): {"cooldown": 0.0, "radius": r, "base_cooldown": bc}
        self.get_block_at = get_block_at_func
        self.set_block_at = set_block_at_func
        self.storage_system = storage_system
        print("[AutoMinerSystem] Initialized.")

    def register_miner(self, x, y):
        """Registers an auto-miner when placed."""
        block_type = self.get_block_at(x, y)
        if block_type == config.AUTO_MINER:
            block_data = config.BLOCKS.get(block_type, {})
            radius = block_data.get("mining_radius", 1)
            base_cooldown = block_data.get("mining_cooldown", 5.0)
            self.miners[(x, y)] = {
                "cooldown": base_cooldown, # Start with cooldown ready? Or 0? Let's start ready.
                "radius": radius,
                "base_cooldown": base_cooldown
            }
            print(f"[AutoMinerSystem] Registered miner at ({x}, {y}) with radius {radius}, cooldown {base_cooldown}")
        else:
             print(f"[AutoMinerSystem] WARNING: Attempted to register non-miner block at ({x}, {y})")

    def unregister_miner(self, x, y):
        """Unregisters an auto-miner when broken."""
        if (x, y) in self.miners:
            del self.miners[(x, y)]
            print(f"[AutoMinerSystem] Unregistered miner at ({x}, {y})")

    def update(self, dt):
        """Updates all active auto-miners."""
        for (miner_x, miner_y), data in list(self.miners.items()): # Use list() for safe iteration if modifying dict
            data["cooldown"] -= dt
            if data["cooldown"] <= 0:
                mined_block = self.find_and_mine_block(miner_x, miner_y, data["radius"])
                if mined_block:
                    data["cooldown"] = data["base_cooldown"] # Reset cooldown only if mining occurred
                else:
                    # Optional: Small cooldown even if nothing found to prevent constant checking
                    data["cooldown"] = min(0.1, data["base_cooldown"] / 10)


    def find_and_mine_block(self, miner_x, miner_y, radius):
        """Scans the radius, mines a block, and handles the drop."""
        possible_targets = []
        # Scan in a square radius around the miner
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if dx == 0 and dy == 0: continue # Don't mine self

                target_x = miner_x + dx
                target_y = miner_y + dy

                block_type = self.get_block_at(target_x, target_y)

                # Check if block is minable
                if block_type != config.EMPTY and block_type != config.BEDROCK: # Add other unbreakable blocks if needed
                    block_data = config.BLOCKS.get(block_type)
                    if block_data and block_data.get("hardness", 1) >= 0: # Check hardness >= 0
                        possible_targets.append((target_x, target_y, block_type))

        if not possible_targets:
            return False # Nothing found to mine

        # --- Target Selection (Simple: random target) ---
        target_x, target_y, target_type = random.choice(possible_targets)
        # --- Could implement other strategies: closest, highest value, etc. ---

        print(f"[AutoMinerSystem] Miner at ({miner_x},{miner_y}) mining block {target_type} at ({target_x},{target_y})")

        # --- Mine the block ---
        if self.set_block_at(target_x, target_y, config.EMPTY):
            # --- Handle Drop ---
            dropped_item_id = target_type # Default drop is the block itself
            drop_data = config.BLOCKS.get(target_type, {}).get("drops")
            if drop_data:
                 # Simple drop logic: take the first drop type with probability 1.0, or default
                 found_drop = False
                 for drop_id_str, probability in drop_data.items():
                     if probability >= 1.0: # Prioritize guaranteed drops
                         try:
                             dropped_item_id = int(drop_id_str)
                             found_drop = True
                             break
                         except ValueError: continue
                 # If no guaranteed drop, maybe implement random chance later
                 # For now, if no guaranteed drop, it defaults to dropping itself (already set)

            # --- Output Drop (Try adjacent storage) ---
            output_success = False
            for dx_out, dy_out in [(0, 1), (1, 0), (0, -1), (-1, 0)]: # Check down, right, up, left
                check_x, check_y = miner_x + dx_out, miner_y + dy_out
                if self.storage_system.is_storage_position(check_x, check_y):
                    if self.storage_system.add_item_to_storage(check_x, check_y, dropped_item_id, 1):
                        print(f"[AutoMinerSystem] Outputted {dropped_item_id} to storage at ({check_x},{check_y})")
                        output_success = True
                        break # Stop checking once outputted

            if not output_success:
                print(f"[AutoMinerSystem] No adjacent storage found or storage full for drop {dropped_item_id}. Item lost.")
                # Future: Implement dropping item entities in the world

            return True # Mining occurred
        else:
            print(f"[AutoMinerSystem] Failed to set block at ({target_x},{target_y}) to EMPTY.")
            return False # Mining failed

    # --- Save/Load ---
    def get_save_data(self):
        return {f"{x},{y}": data for (x, y), data in self.miners.items()}

    def load_save_data(self, data):
        self.miners.clear()
        print("[AutoMinerSystem] Loading save data...")
        for key, m_data in data.items():
            try:
                x_str, y_str = key.split(',')
                # Ensure numeric fields are loaded correctly
                m_data["cooldown"] = float(m_data.get("cooldown", 0.0))
                m_data["radius"] = int(m_data.get("radius", 1))
                m_data["base_cooldown"] = float(m_data.get("base_cooldown", 5.0))
                self.miners[(int(x_str), int(y_str))] = m_data
            except Exception as e:
                print(f"Error loading auto-miner data for key {key}: {e}")
        print(f"[AutoMinerSystem] Loaded {len(self.miners)} miners.")

