from octotools.tools import _maps
from octotools.tools.base import BaseTool


class POI_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="POI_Tool",
            tool_description=(
                "Retrieves detailed information about a given place using the Place Details API, including address, "
                "rating, opening hours, contact information, services and reviews."
            ),
            tool_version="1.0.0",
            input_types={"location_address": "str - The address or name of the location to search for."},
            output_type="str - Detailed information about the place.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(location_address="Cafe Jannat, Lalbagh, Dhaka")',
                    "description": "Details of Cafe Jannat in Lalbagh, Dhaka.",
                },
            ],
        )

    def execute(self, location_address):
        return _maps.run(_maps.map_tools.place_info, location_address)

    def get_metadata(self):
        return super().get_metadata()


if __name__ == "__main__":
    print(POI_Tool().execute("Great Russell St, London")[0])
