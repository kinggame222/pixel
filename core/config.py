import json
import os
import time

# --- Game Configuration ---

PIXEL_SIZE = 4
SEED = int(time.time())  # Seed for world generation (non-deterministic)
PLAYER_WIDTH = 4 * PIXEL_SIZE
PLAYER_HEIGHT = 5 * PIXEL_SIZE
PLAYER_SPEED = 500

ANIM_DURATION = 100

# --- Chunk Management ---
CHUNK_SIZE = 16  # Size of each chunk (in blocks)

# --- Graphics Settings ---
WINDOW_TITLE = "Pixel Mining - Modular"
FPS_CAP = 60

# --- Physics ---
GRAVITY = 500
JUMP_SPEED = -300
JETPACK_SPEED = 500

# --- Paths ---
# Get the base directory (pixel folder)
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Look for blocks.json in the project root directory instead of 'assets'
BLOCKS_PATH = os.path.join(BASE_PATH, "blocks.json")

# --- Block Constants ---
# Load block properties from JSON
try:
    with open(BLOCKS_PATH, "r") as f:
        BLOCK_PROPERTIES = json.load(f)
    print(f"Successfully loaded blocks from {BLOCKS_PATH}")
except FileNotFoundError:
    print(f"Error: blocks.json not found at {BLOCKS_PATH}")
    # Provide default block properties in case the file is missing
    BLOCK_PROPERTIES = [
        {
            "id": 0,
            "name": "empty",
            "color": [0, 0, 0],
            "solid": False
        },
        {
            "id": 12,
            "name": "ore_processor",
            "color": [150, 100, 200],
            "solid": True,
            "is_machine": True
        }
    ]

# --- Create a dictionary to map block IDs to properties ---
BLOCKS = {block["id"]: block for block in BLOCK_PROPERTIES}

# --- Dynamically Create Constants for Block IDs ---
# For example, EMPTY = 0, STONE = 1, etc.
for block in BLOCK_PROPERTIES:
    globals()[block["name"].upper()] = block["id"]

# Make sure ORE_PROCESSOR is defined
if "ORE_PROCESSOR" not in globals():
    print("Warning: ORE_PROCESSOR not found in blocks.json, using default ID 12")
    globals()["ORE_PROCESSOR"] = 12

# Add Snow Block ID
SNOW_BLOCK = 20

# --- Colors ---
COLOR_FPS = (255, 255, 0)
COLOR_PLAYER = (0, 0, 255)
