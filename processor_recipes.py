import config

class ProcessorRecipes:
    """Class to manage crafting recipes for the ore processor"""
    
    def __init__(self):
        """Initialize the crafting recipes dictionary"""
        # Format: input_block_id: (output_block_id, processing_time, output_count)
        self.recipes = {
            config.IRON_ORE: {
                "output": config.IRON_BAR,
                "time": 5.0,         # Processing time in seconds
                "count": 1,          # Number of output items produced
                "description": "Iron Ore → Iron Bar",
                "required_input": 1   # Number of input items required
            },
            config.DIAMOND_ORE: {
                "output": config.DIAMOND_CRYSTAL,
                "time": 10.0,        # Diamonds take longer to process
                "count": 1,
                "description": "Diamond Ore → Diamond Crystal",
                "required_input": 1
            },
            config.STONE: {
                "output": config.GRAVEL,
                "time": 3.0,
                "count": 2,          # Get 2 gravel from 1 stone
                "description": "Stone → Gravel (x2)",
                "required_input": 1
            },
            config.GRAVEL: {
                "output": config.SAND,
                "time": 2.0,
                "count": 1,
                "description": "Gravel → Sand",
                "required_input": 1
            }
        }
        
    def can_process(self, block_type):
        """Check if a block type can be processed"""
        return block_type in self.recipes
        
    def get_recipe(self, block_type):
        """Get the recipe for a specific block type"""
        return self.recipes.get(block_type, None)
        
    def get_processing_time(self, block_type):
        """Get the processing time for a specific block type"""
        recipe = self.get_recipe(block_type)
        if recipe:
            return recipe["time"]
        return 0
        
    def get_output(self, block_type):
        """Get the output block type for a specific input block type"""
        recipe = self.get_recipe(block_type)
        if recipe:
            return recipe["output"]
        return None
        
    def get_output_count(self, block_type):
        """Get the number of output items produced"""
        recipe = self.get_recipe(block_type)
        if recipe:
            return recipe["count"]
        return 0
        
    def get_required_input(self, block_type):
        """Get the number of input items required"""
        recipe = self.get_recipe(block_type)
        if recipe:
            return recipe["required_input"]
        return 0
        
    def get_description(self, block_type):
        """Get the recipe description"""
        recipe = self.get_recipe(block_type)
        if recipe:
            return recipe["description"]
        return "Unknown Recipe"
        
    def get_all_recipes(self):
        """Get all available recipes"""
        return self.recipes

# Create a global instance that can be imported
processor_recipes = ProcessorRecipes()
