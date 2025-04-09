import json

# --- Configuration du Jeu ---

GRID_WIDTH = 1000  # Increased width
GRID_HEIGHT = 400 # Increased height
PIXEL_SIZE = 4

PLAYER_WIDTH = 4 * PIXEL_SIZE
PLAYER_HEIGHT = 5 * PIXEL_SIZE
PLAYER_SPEED = 200

ANIM_DURATION = 100

# --- Chunk Management ---
CHUNK_SIZE = 16  # Size of each chunk (in blocks)

# --- Load Block Properties from JSON ---
with open("blocks.json", "r") as f:
    BLOCK_PROPERTIES = json.load(f)

# --- Create a dictionary to map block IDs to properties ---
BLOCKS = {block["id"]: block for block in BLOCK_PROPERTIES}

# --- Constants for Block IDs ---
EMPTY = 0
GRAVEL = 1
STONE = 2
DIRT = 3
SAND = 4
WOOD = 5
IRON_ORE = 6
DIAMOND_ORE = 7
WATER = 8

# --- Couleurs ---
COLOR_FPS = (255, 255, 0)
COLOR_PLAYER = (0, 0, 255)

# --- Configuration Pygame ---
WINDOW_TITLE = "Pixel Mining - Modular"
FPS_CAP = 300
GRAVITY = 500
JUMP_SPEED = -300
