import random
import config
import numpy as np

def update_animations(current_time_ms, falling_animations, grid, next_active_columns):
    """
    Updates the positions of falling blocks based on their animations.
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

            # If the block has moved to a new row, update the grid
            if current_row != anim["current_row"]:
                # Clear the previous position
                grid[anim["current_row"], col] = config.EMPTY
                # Set the new position
                grid[current_row, col] = anim["block_type"]
                # Update the current row in the animation
                anim["current_row"] = current_row

            # Mark the column as active for the next frame
            next_active_columns.add(col)
        else:
            # Animation is complete
            start_row, end_row, col = anim["start_row"], anim["end_row"], anim["col"]
            grid[anim["current_row"], col] = config.EMPTY
            grid[end_row, col] = anim["block_type"]
            completed_animations.append(idx)

    # Remove completed animations in reverse order to avoid index issues
    for idx in sorted(completed_animations, reverse=True):
        del falling_animations[idx]

    return falling_animations, set(), grid, next_active_columns

def run_gravity_simulation(active_columns, grid, falling_animations, animating_sources,
                           current_time_ms, next_active_columns):
    """Runs the gravity simulation for the given columns."""
    new_falling_animations = []
    for col in list(active_columns):  # Iterate over a copy to allow modification
        # Find the topmost empty block in the column
        topmost_empty = -1
        for r in range(config.GRID_HEIGHT):
            if grid[r, col] == config.EMPTY:
                topmost_empty = r
                break

        if topmost_empty == -1:
            continue  # No empty blocks in this column

        # Find the topmost solid block above the empty block
        topmost_solid = -1
        for r in range(topmost_empty - 1, -1, -1):
            if grid[r, col] != config.EMPTY:
                topmost_solid = r
                break

        if topmost_solid == -1:
            continue  # No solid blocks above the empty block

        # If the block is not already animating, start a new animation
        if (topmost_solid, col) not in animating_sources:
            block_type = grid[topmost_solid, col]
            # Clear the block from its original position
            # grid[topmost_solid, col] = config.EMPTY # Moved to animation update

            # Add a new animation to the list
            animation = {
                "start_time": current_time_ms,
                "duration": 200,  # Duration of the animation in ms
                "start_row": topmost_solid,
                "end_row": topmost_empty,
                "current_row": topmost_solid,
                "col": col,
                "block_type": block_type
            }
            falling_animations.append(animation)
            new_falling_animations.append(animation)

            # Add the block to the set of animating sources
            animating_sources.add((topmost_solid, col))

            # Mark the column as active for the next frame
            next_active_columns.add(col)

    return grid, falling_animations, animating_sources, next_active_columns

