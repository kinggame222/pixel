from core import config

def is_solid_block(block_type):
    """Checks if the given block type is solid."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type]["solid"]
    return False

def is_breakable(block_type):
    """Checks if the given block type is breakable."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type].get("breakable", True)
    return True

def get_block_hardness(block_type):
    """Returns the hardness of the given block type."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type].get("hardness", 1)
    return 1

def get_block_name(block_type):
    """Returns the name of the given block type."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type].get("name", "Unknown")
    return "Unknown"

def get_block_color(block_type):
    """Returns the color of the given block type."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type].get("color", (0, 0, 0))
    return (0, 0, 0)

def is_machine(block_type):
    """Checks if the given block type is a machine."""
    if block_type in config.BLOCKS:
        return config.BLOCKS[block_type].get("is_machine", False)
    return False
