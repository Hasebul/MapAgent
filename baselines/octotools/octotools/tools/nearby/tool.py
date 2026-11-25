from octotools.tools import _maps
from octotools.tools.base import BaseTool


class Nearby_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Nearby_Tool",
            tool_description=(
                "Identifies points of interest within a specified area around a location using the Nearby Search "
                "API. Returns place names, ratings, number of reviews and the distance from the location."
            ),
            tool_version="1.0.0",
            input_types={
                "query": "str - The search term to look for places (e.g. 'coffee shop', 'restaurant').",
                "location": "str - The name or address of the current location (e.g. 'Ibn Sina Hospital, Dhaka').",
                "type": "str - The type of place to search for, such as 'restaurant', 'cafe', or 'hospital' (optional).",
                "radius": "float - The radius in kilometers used for filtering (default: 20).",
            },
            output_type="str - The nearby places with their distance, rating and number of reviews.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="hospital", location="Lalbagh, Dhaka", type="hospital", radius=5)',
                    "description": "Hospitals within 5 km of Lalbagh, Dhaka.",
                },
            ],
        )

    def execute(self, query, location, type=None, radius=20.0):  # noqa: A002
        return _maps.run(_maps.map_tools.nearby, query, location, type, radius)

    def get_metadata(self):
        return super().get_metadata()


if __name__ == "__main__":
    print(Nearby_Tool().execute("supermarket", "Baridhara Diplomatic Zone, Dhaka", "supermarket", 3)[0])
