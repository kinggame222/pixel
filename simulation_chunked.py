import random
import config
import numpy as np

def update_chunk_animations(current_time_ms, falling_animations, get_block_at, set_block_at, next_active_columns):
    """
    Updates the positions of falling blocks based on their animations for a chunked world.
    Removes animations that have completed.
    """
    completed_animations = []
    for idx, anim in enumerate(falling_animations):
        progress = (current_time_ms - anim["start_time"]) / anim["duration"]
        if 0 <= progress <= 1:
            # Calculate the new y position based on the animation progress
            start_row, end_row, col = anim["start_row"], anim["end_row"], anim["col"]
            current_row = start_row + (end_row - start_row) * progress
            current_row = int(current_row)  # Ensure it's an integer for indexing

            # If the block has moved to a new row, update the blocks
            if current_row != anim["current_row"]:
                # Clear the previous position
                set_block_at(col, anim["current_row"], config.EMPTY)
                # Set the new position
                set_block_at(col, current_row, anim["block_type"])
                # Update the current row in the animation
                anim["current_row"] = current_row

            # Mark the column as active for the next frame
            next_active_columns.add(col)
        else:
            # Animation is complete
            start_row, end_row, col = anim["start_row"], anim["end_row"], anim["col"]
            set_block_at(col, anim["current_row"], config.EMPTY)
            set_block_at(col, end_row, anim["block_type"])
            completed_animations.append(idx)

    # Remove completed animations in reverse order to avoid index issues
    for idx in sorted(completed_animations, reverse=True):
        del falling_animations[idx]

    return falling_animations, set(), next_active_columns

def run_chunk_gravity_simulation(active_columns, get_block_at, set_block_at, falling_animations, 
                           animating_sources, current_time_ms, next_active_columns):
    """Runs gravity simulation for the given columns in a chunked world."""
    # This function would need to be more complex for a chunked world
    # For now, we'll just return the input values
    return falling_animations, animating_sources, next_active_columns
