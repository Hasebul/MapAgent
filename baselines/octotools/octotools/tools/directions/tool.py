from octotools.tools import _maps
from octotools.tools.base import BaseTool


class Directions_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Directions_Tool",
            tool_description=(
                "Fetches route information between two points using the Directions API, including the distance, "
                "the estimated travel time and the step-by-step navigation instructions of each route."
            ),
            tool_version="1.0.0",
            input_types={
                "origin": "str - The starting location for the directions.",
                "destination": "str - The destination for the directions.",
                "mode": "str - The mode of transportation: 'driving' (default), 'walking', 'bicycling' or 'transit'.",
                "waypoints": "list[str] - Optional intermediate stops, in order (default: None).",
                "alternatives": "bool - Whether to return multiple possible routes (default: True).",
            },
            output_type="str - The routes with their distance, duration and step-by-step instructions.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(origin="South Wind Motel", destination="Brassica in Bexley", mode="walking")',
                    "description": "Walking routes from South Wind Motel to Brassica in Bexley.",
                },
                {
                    "command": 'execution = tool.execute(origin="Seabird Water Taxi", destination="Sierra Leone Grammar School", mode="driving", waypoints=["Cole Street Guesthouse"])',
                    "description": "Driving route with an intermediate stop.",
                },
            ],
        )

    def execute(self, origin, destination, mode="driving", waypoints=None, alternatives=True):
        return _maps.run(_maps.map_tools.route, origin, destination, mode, waypoints, alternatives)

    def get_metadata(self):
        return super().get_metadata()


if __name__ == "__main__":
    print(Directions_Tool().execute("South Wind Motel", "Brassica in Bexley", "walking")[0])
