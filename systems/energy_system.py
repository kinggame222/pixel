import pygame
import time
from core import config

class EnergySystem:
    def __init__(self):
        self.generators = {}  # {(x, y): generator_data}
        self.consumers = {}  # {(x, y): consumer_data}
        self.grid = {}  # {(x, y): grid_connection_data}
        
        # Add new block types to blocks.json
        self.coal_generator_id = getattr(config, "COAL_GENERATOR", 20)
        self.solar_panel_id = getattr(config, "SOLAR_PANEL", 21)
        self.power_line_id = getattr(config, "POWER_LINE", 22)
        self.battery_id = getattr(config, "BATTERY", 23)
        
    def create_generator(self, x, y, gen_type="coal"):
        """Create a new power generator"""
        output = 100 if gen_type == "coal" else 50  # Coal produces more power than solar
        
        self.generators[(x, y)] = {
            "type": gen_type,
            "output": output,  # Energy units per second
            "fuel": 0 if gen_type == "solar" else 60,  # Solar doesn't need fuel
            "max_fuel": 100,
            "connected_to": []
        }
        return True
    
    def create_consumer(self, x, y, machine_type, consumption):
        """Register a machine as an energy consumer"""
        self.consumers[(x, y)] = {
            "type": machine_type,
            "consumption": consumption,  # Energy units per second
            "connected_to": [],
            "active": False  # Whether it's currently receiving enough power
        }
        return True
    
    def connect_to_grid(self, pos):
        """Connect a position to the power grid"""
        self.grid[pos] = {
            "connected_to": []
        }
        
        # Connect to adjacent grid points
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            adjacent = (pos[0] + dx, pos[1] + dy)
            if adjacent in self.grid:
                self.grid[pos]["connected_to"].append(adjacent)
                self.grid[adjacent]["connected_to"].append(pos)
                
        return True
    
    def update(self, dt):
        """Update energy production and consumption"""
        # Calculate total energy production
        total_production = 0
        for pos, generator in self.generators.items():
            if generator["type"] == "coal" and generator["fuel"] > 0:
                production = generator["output"] * dt
                generator["fuel"] -= dt  # Consume fuel
                total_production += production
            elif generator["type"] == "solar":
                # Solar panels only work during daytime
                # Implement day/night cycle for this
                total_production += generator["output"] * dt
        
        # Calculate total energy demand
        total_demand = 0
        for pos, consumer in self.consumers.items():
            total_demand += consumer["consumption"] * dt
        
        # Distribute energy
        if total_production >= total_demand:
            # Enough energy for everyone
            for pos, consumer in self.consumers.items():
                consumer["active"] = True
        else:
            # Not enough energy - prioritize consumers
            # Sort by position for now (simple priority)
            sorted_consumers = sorted(self.consumers.items())
            remaining_energy = total_production
            
            for pos, consumer in sorted_consumers:
                needed = consumer["consumption"] * dt
                if needed <= remaining_energy:
                    consumer["active"] = True
                    remaining_energy -= needed
                else:
                    consumer["active"] = False
    
    def add_fuel(self, pos, fuel_amount):
        """Add fuel to a generator"""
        if pos in self.generators and self.generators[pos]["type"] == "coal":
            self.generators[pos]["fuel"] = min(
                self.generators[pos]["max_fuel"],
                self.generators[pos]["fuel"] + fuel_amount
            )
            return True
        return False
