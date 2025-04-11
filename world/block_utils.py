from core import config
from world.chunks import get_block_at, set_block_at

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

def apply_gravity(block_x, block_y):
    """Applique la gravité à un bloc si nécessaire."""
    block_type = get_block_at(block_x, block_y)
    
    # Vérifier si le bloc est affecté par la gravité
    if block_type in config.BLOCKS and config.BLOCKS[block_type]["gravity"]:
        # Vérifier le bloc en dessous
        below_block = get_block_at(block_x, block_y + 1)
        if below_block == config.EMPTY:
            # Déplacer le bloc vers le bas
            set_block_at(block_x, block_y + 1, block_type)
            set_block_at(block_x, block_y, config.EMPTY)
            return True  # La gravité a été appliquée
    return False
