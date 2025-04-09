import json

# --- Configuration du Jeu ---

PIXEL_SIZE = 4

PLAYER_WIDTH = 4 * PIXEL_SIZE
PLAYER_HEIGHT = 5 * PIXEL_SIZE
PLAYER_SPEED = 500

ANIM_DURATION = 100

# --- Chunk Management ---
CHUNK_SIZE = 16  # Size of each chunk (in blocks)

# --- Load Block Properties from JSON ---
with open("blocks.json", "r") as f:
    BLOCK_PROPERTIES = json.load(f)

# --- Create a dictionary to map block IDs to properties ---
BLOCKS = {block["id"]: block for block in BLOCK_PROPERTIES}

# --- Dynamically Create Constants for Block IDs ---
globals().update({block["name"].upper(): block["id"] for block in BLOCK_PROPERTIES})

# These will be automatically generated from blocks.json now:
# ORE_PROCESSOR = 12
# IRON_BAR = 13
# DIAMOND_CRYSTAL = 14

# --- Couleurs ---
COLOR_FPS = (255, 255, 0)
COLOR_PLAYER = (0, 0, 255)

# --- Configuration Pygame ---
WINDOW_TITLE = "Pixel Mining - Modular"
FPS_CAP = 60
GRAVITY = 500
JUMP_SPEED = -300
