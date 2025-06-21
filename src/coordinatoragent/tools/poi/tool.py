import os
import requests
from typing import List, Dict, Any

from octotools.tools.base import BaseTool
from datetime import datetime

from dotenv import load_dotenv
import googlemaps

gmaps = googlemaps.Client(key='AIzaSyC8EPK5_SZ999QHQGlIOu48HgiB2Uql0hI')
load_dotenv()


class POI_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Poi Tool",
            tool_description="A tool that performs Google Map searches based on a given text query.",
            tool_version="1.0.0",
            input_types={
                "location_address": "str - The address or name of the location to search for."
            },
            output_type="str - A string containing the location information and travel time and distance between the locations.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Python programming")',
                    "description": "Perform a Google search for 'Python programming' and return the default number of results."
                },
                {
                    "command": 'execution = tool.execute(location_address=Cafe Jannat, Lalbagh, Dhaka)',
                    "description": "Perform a POI tools search for the place info for Cafe Jannat, Lalbagh, Dhaka"
                },
            ],
        )
        # self.api_key = os.getenv("GOOGLE_API_KEY")
        self.api_key = os.getenv("GOOGLE_MAP_API_KEY") # NOTE: Replace with your own API key (Ref: https://developers.google.com/custom-search/v1/introduction)


    def get_place_info(self,location_address):
        """
        Returns the details of a place, including its name, address, rating, types,
        opening hours, and whether it is currently open.

        Parameters:
            location_address (str): The address or name of the location to search for.

        Returns:
            dict: A dictionary containing the place details.
        """
        place_result = gmaps.places(location_address)
        if len(place_result['results']) == 0:
            print("No results found for location", location_address)
        else:
            place_id = place_result['results'][0]['place_id']
        place_result = gmaps.place(place_id)
        if len(place_result['result']) == 0:
            print("No results found for location", location_address)
        else:
            place = place_result['result']
            name = place['name']
            address = place['formatted_address']
            rating = place['rating'] if 'rating' in place else 'N/A'
            types = place['types']
            if "current_opening_hours" in place.keys():
                opening_hours = place["current_opening_hours"]
            elif "opening_hours" in place.keys():
                opening_hours = place["opening_hours"]
            else:
                opening_hours = {}
            is_open_now = opening_hours['open_now'] if 'open_now' in opening_hours else 'N/A'
            weekdays_opening_hours = opening_hours["weekday_text"] if opening_hours else 'N/A'
            place_info = {
                'name': name,
                'address': address,
                'rating': rating,
                'types': types,
                'serves_beer': "YES" if place.get('serves_beer', False) else "NO",
                "serves_breakfast": "YES" if place.get("serves_breakfast", False) else "NO",
                "serves_brunch": "YES" if place.get("serves_brunch", False) else "NO",
                "serves_dinner": "YES" if place.get("serves_dinner", False) else "NO",
                "serves_lunch": "YES" if place.get("serves_lunch", False) else "NO",
                "serves_vegetarian_food": "YES" if place.get("serves_vegetarian_food", False) else "NO",
                "serves_wine": "YES" if place.get("serves_wine", False) else "NO",
                "reservable": "YES" if place.get("reservable", False) else "NO",
                "wheelchair_accessible_entrance": "YES" if place.get("wheelchair_accessible_entrance", False) else "NO",
                "user_ratings_total": place.get("user_ratings_total", 0),
                "price_level": {1: "Inexpensive", 2: "Moderate", 3: "Expensive", 4: "Very Expensive"}.get(
                    place.get("price_level", 0), "Unknown"),
                'is_open_now': is_open_now,
                'weekdays_opening_hours': weekdays_opening_hours,
            }
            return place_info


    def execute(self, location_address) -> List[Dict[str, Any]]:
        """
        Executes a Trip Tool based on the provided Information.

        Parameters:
            location_address (str): The address or name of the location to search for.

        Returns:
            str: A string containing the location information and travel time and distance between the locations.
        """
        if not self.api_key:
            return [{"error": "Google MAP API key is not set. Please set the GOOGLE_API_KEY environment variable."}]

        try:
            results = self.get_place_info(location_address)
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
    tool = POI_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Execute the tool to perform a Google search
    location_address = "Great Russell St, London"
    try:
        execution = tool.execute(location_address=location_address)
        print("\nExecution Result:")
        print(f"current location: {location_address}")
        print(f"Number of results: {len(execution)}")
        print(f"results: {execution[0]}")
    except Exception as e:
        print(f"Execution failed: {e}")

    print("Done!")
