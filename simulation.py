import random
import config
import numpy as np

def update_animations(current_time_ms, falling_animations, grid, next_active_columns):
    """Met à jour les animations de chute et place les blocs à leur destination."""
    new_anims = []
    animating_sources = set()
    completed_this_frame = []
    for anim in falling_animations:
        progress = (current_time_ms - anim["start_time"]) / anim["duration"]
        if progress >= 1.0:
            completed_this_frame.append(anim)
        else:
            new_anims.append(anim)
            animating_sources.add(anim["src"])

    for anim in completed_this_frame:
         dst_row, dst_col = anim["dest"]
         if 0 <= dst_row < config.GRID_HEIGHT and 0 <= dst_col < config.GRID_WIDTH:
              if grid[dst_row, dst_col] == config.EMPTY:
                 grid[dst_row, dst_col] = config.GRAVEL
                 # Mark column active for next frame (still needed for landing)
                 next_active_columns.add(dst_col)
                 if dst_col > 0: next_active_columns.add(dst_col - 1)
                 if dst_col < config.GRID_WIDTH - 1: next_active_columns.add(dst_col + 1)

    falling_animations = new_anims
    return falling_animations, animating_sources, grid, next_active_columns

def run_gravity_simulation(active_columns, grid, falling_animations, animating_sources, current_time_ms, next_active_columns):
    """Simule la gravité pour les colonnes actives."""
    columns_to_check = sorted(list(active_columns))
    grid_width = config.GRID_WIDTH
    grid_height = config.GRID_HEIGHT

    for c in columns_to_check:
        if not (0 <= c < grid_width): continue

        # Early exit: Check if the column contains any gravel
        if config.GRAVEL not in grid[:, c]:
            continue

        can_check_left = c > 0
        can_check_right = c < grid_width - 1

        for r in range(grid_height - 2, -1, -1):
            if (r, c) in animating_sources: continue
            if grid[r, c] == config.GRAVEL:
                if grid[r + 1, c] == config.EMPTY:
                    grid[r, c] = config.EMPTY
                    new_anim = {"src": (r, c), "dest": (r + 1, c), "start_time": current_time_ms, "duration": config.ANIM_DURATION}
                    falling_animations.append(new_anim)
                    animating_sources.add(new_anim["src"])
                    next_active_columns.add(c)
                elif grid[r + 1, c] != config.EMPTY:
                    possibilities = []
                    if can_check_left and grid[r + 1, c - 1] == config.EMPTY and grid[r, c - 1] == config.EMPTY: possibilities.append((r + 1, c - 1))
                    if can_check_right and grid[r + 1, c + 1] == config.EMPTY and grid[r, c + 1] == config.EMPTY: possibilities.append((r + 1, c + 1))
                    if possibilities:
                        dest = random.choice(possibilities)
                        grid[r, c] = config.EMPTY
                        new_anim = {"src": (r, c), "dest": dest, "start_time": current_time_ms, "duration": config.ANIM_DURATION}
                        falling_animations.append(new_anim)
                        animating_sources.add(new_anim["src"])
                        next_active_columns.add(c)
                        next_active_columns.add(dest[1])

    return grid, falling_animations, animating_sources, next_active_columns

