from octotools.tools import _maps
from octotools.tools.base import BaseTool


class Trip_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Trip_Tool",
            tool_description=(
                "Retrieves information about locations and the travel routes between them. Combines the Place "
                "Details and Directions APIs: place metadata (address, rating, opening hours) of every location and "
                "the travel time and distance between every ordered pair of locations."
            ),
            tool_version="1.0.0",
            input_types={
                "current_location": "str - The starting location of the trip.",
                "visiting_places": "list[str] - A list of locations to visit.",
                "travel_mode": "str - The mode of travel: 'driving' (default), 'walking', 'bicycling' or 'transit'.",
            },
            output_type="str - Location information and the travel time and distance between the locations.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(current_location="Indira Road, Dhaka", visiting_places=["Military Museum Dhaka", "Multiplan Center"], travel_mode="driving")',
                    "description": "Place details of the three places and the driving time/distance between each pair.",
                },
            ],
        )

    def execute(self, current_location, visiting_places, travel_mode="driving"):
        return _maps.run(_maps.map_tools.trip, current_location, visiting_places, travel_mode)

    def get_metadata(self):
        return super().get_metadata()


if __name__ == "__main__":
    print(Trip_Tool().execute("Indira Road, Dhaka", ["Military Museum Dhaka", "Multiplan Center"], "driving")[0])
