import os
import requests
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from octotools.tools.base import BaseTool

from dotenv import load_dotenv
import googlemaps

gmaps = googlemaps.Client(key='AIzaSyC8EPK5_SZ999QHQGlIOu48HgiB2Uql0hI')
load_dotenv()


class Directions_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Directions Tool",
            tool_description="A tool that performs Google Map searches based on a given text query.",
            tool_version="1.0.0",
            input_types={
                "origin": "str - The starting location for the directions.",
                "destination": "str - The starting location for the directions.",
                "mode": "str -The mode of transportation to use for the directions, such as 'driving', 'walking', or 'transit'.",
                "waypoints": "array- A list of locations to visit along the route.",
                "alternatives": "boolean- Whether to return multiple possible routes.",
            },
            output_type="str - A string containing the location information and travel time and distance between the locations.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Python programming")',
                    "description": "Perform a Google search for 'Python programming' and return the default number of results."
                },
                {
                    "command": 'execution = tool.execute(origin = "South Wind Motel", destination = "Brassica in Bexley", mode = "walking", waypoints = None, alternatives = True)',
                    "description": "Perform a Directions tools search for the route from South Wind Motel to Brassica in Bexley by walking"
                },
            ],
        )
        # self.api_key = os.getenv("GOOGLE_API_KEY")
        self.api_key = os.getenv("GOOGLE_MAP_API_KEY") # NOTE: Replace with your own API key (Ref: https://developers.google.com/custom-search/v1/introduction)

    def directions(self, origin: str, destination: str, mode: str = None, waypoints: list = None,
                   alternatives: bool = True) -> str:
        """
        Returns a dictionary containing information on the directions from an origin to a destination.

        Args:
            origin (str): The starting location for the directions.
            destination (str): The destination for the directions.
            mode (str): The mode of transportation to use for the directions, such as "driving", "walking", or "transit".
            waypoints (list): A list of locations to visit along the route.
            alternatives (bool): Whether to return multiple possible routes.

        Returns:
            str: A string containing information on the directions, including the number of routes and details on each route.
        """
        # origin = "D03 Flame Tree Ridge", destination = "Aster Cedars Hospital, Jebel Ali", mode = "driving", waypoints = None, alternatives = True
        # waypoints = None
        # alternatives = True
        all_routes = gmaps.directions(
            origin=origin, destination=destination, mode=mode, waypoints=waypoints, alternatives=alternatives
        )
        extract_information = f"There are total {len(all_routes)} routes from {origin} to {destination}. The route information is provided below:\n\n"
        num = 0
        for route in all_routes:
            num += 1
            dist = route["legs"][0]["distance"]["text"]
            duration = route["legs"][0]["duration"]["text"]
            via = route["summary"]
            extract_information += f"Route {num}:(VIA) {via} ({dist}, {duration})\nDetails steps are provided below: \n"
            for step in route["legs"][0]["steps"]:
                s_dist = step["distance"]["text"]
                s_duration = step["duration"]["text"]
                html_content = step["html_instructions"]
                soup = BeautifulSoup(html_content, 'html.parser')
                # Extract the text from the HTML content
                s_text = soup.get_text()
                extract_information += f"{s_text} ({s_dist}, {s_duration}) \n"
            extract_information += "\n"
        return extract_information

    def execute(self, origin: str, destination: str, mode: str = None, waypoints: list = None,
                   alternatives: bool = True) -> List[Dict[str, Any]]:
        """
        Executes a Trip Tool based on the provided Information.

        Args:
            origin (str): The starting location for the directions.
            destination (str): The destination for the directions.
            mode (str): The mode of transportation to use for the directions, such as "driving", "walking", or "transit".
            waypoints (list): A list of locations to visit along the route.
            alternatives (bool): Whether to return multiple possible routes.

        Returns:
            str: A string containing information on the directions, including the number of routes and details on each route.
        """
        if not self.api_key:
            return [{"error": "Google MAP API key is not set. Please set the GOOGLE_API_KEY environment variable."}]

        try:
            results = self.directions(origin=origin, destination=destination, mode=mode, waypoints=waypoints, alternatives=alternatives)
            print(results)
            if results:
                return [results]
            else:
                return [{"error": "No results found."}]
        except Exception as e:
            return [{"error": f"An error occurred: {str(e)}"}]

    def get_metadata(self):
        """
        Returns the metadata for the Google_Search_Tool.

        Returns:
            dict: A dictionary containing the tool's metadata.
        """
        metadata = super().get_metadata()
        return metadata


if __name__ == "__main__":
    # Test command:
    """
    Run the following commands in the terminal to test the script:

    export GOOGLE_API_KEY=your_api_key_here
    cd coordinatoragent/tools/google_search
    python tool.py
    """

    # Example usage of the Google_Search_Tool
    tool = Directions_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Execute the tool to perform a Google search
    origin = "South Wind Motel"
    destination = "Brassica in Bexley"
    mode = "walking"
    waypoints = None
    alternatives = True
    try:
        execution = tool.execute(origin=origin, destination=destination, mode=mode, waypoints=waypoints, alternatives=alternatives)
        print("\nExecution Result:")
        # print(f"current location: {current_location}, visiting places: {visiting_places}, travel_mode: {travel_mode}")
        print(f"Number of results: {len(execution)}")
        print(f"results: {execution[0]}")
    except Exception as e:
        print(f"Execution failed: {e}")

    print("Done!")
