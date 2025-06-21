import os
import requests
from typing import List, Dict, Any

from octotools.tools.base import BaseTool
from datetime import datetime
from math import sin, cos, sqrt, atan2, radians

from dotenv import load_dotenv
import googlemaps

gmaps = googlemaps.Client(key='AIzaSyC8EPK5_SZ999QHQGlIOu48HgiB2Uql0hI')
load_dotenv()


class Nearby_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Nearby Tool",
            tool_description="A tool that performs Google Map searches based on a given text query.",
            tool_version="1.0.0",
            input_types={
                "query": "str - The search term to look for nearby places (e.g. 'coffee shop', 'restaurant')",
                "location": "str - The name of the current location (e.g. Ibn Sina Hospital, Dhaka).",
                "type": "str -The type of place to search for, such as 'restaurant', 'cafe', or 'bar'."
            },
            output_type="str - A string containing the location information and travel time and distance between the locations.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Python programming")',
                    "description": "Perform a Google search for 'Python programming' and return the default number of results."
                },
                {
                    "command": 'execution = tool.execute(query=what is the nearest hospital, location=Lalbagh,dhaka, type=hospital)',
                    "description": "Perform a Nearby tools search for nearest hospital at lalbagh Dhaka"
                },
            ],
        )
        self.api_key = os.getenv("GOOGLE_MAP_API_KEY")

    def distance(self,loc1: dict, loc2: dict) -> float:
        """
        Returns the distance between two locations in kilometers.

        Args:
            loc1 (dict): A dictionary containing the latitude and longitude coordinates of the first location in the format {"lat": lat, "lng": lng}.
            loc2 (dict): A dictionary containing the latitude and longitude coordinates of the second location in the format {"lat": lat, "lng": lng}.

        Returns:
            float: The distance between the two locations in kilometers.
        """
        # approximate radius of earth in km
        R = 6373.0
        lat1 = radians(loc1['lat'])
        lon1 = radians(loc1['lng'])
        lat2 = radians(loc2['lat'])
        lon2 = radians(loc2['lng'])

        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        distance = R * c
        return distance

    def geocode(self, address: str) -> tuple:
        """
        Returns a tuple containing the latitude and longitude coordinates for a given address.

        Args:
            address (str): The address to geocode.

        Returns:
            tuple: A tuple containing the latitude and longitude coordinates in the format (lat, lng).
        """
        geocode_result = gmaps.geocode(address)
        return geocode_result[0]["geometry"]["location"]

    def nearby_places(self, query: str, location: str, type: str) -> str:
        """
        Returns a string containing information on nearby places based on a query and location.

        Args:
            query (str): The search term to look for nearby places (e.g. "coffee shop", "restaurant").
            location (str): The name of the current location (e.g. Ibn Sina Hospital, Dhaka).
            type (str): The type of place to search for, such as "restaurant", "cafe", or "bar".

        Returns:
            str: A string containing information on the nearby places, including the name, rating, number of ratings, and distance from the current location.
        """
        location_geocode = self.geocode(location)
        places_results = gmaps.places(
            query=query,
            location=location_geocode,
            type=type
        )
        all_poi = places_results["results"]
        extract_information = f"There are some {type} distance from the current location {location} in below:\n"
        # location_geocode = {'lat': location_geocode[0], 'lng': location_geocode[1]}
        for poi in all_poi:
            dist = self.distance(loc1=poi['geometry']['location'], loc2=location_geocode)
            rating = poi['rating'] if 'rating' in poi.keys() else 0
            total_user = poi['user_ratings_total'] if 'user_ratings_total' in poi.keys() else 0
            extract_information = extract_information + f"{poi['name']} ( distance: {dist} kilometers, rating:{rating}, total reviewer:{total_user})\n"
        return extract_information

    def execute(self, query: str, location: str, type: str) -> List[Dict[str, Any]]:
        """
        Executes a Trip Tool based on the provided Information.

        Parameters:
            query (str): The search term to look for nearby places (e.g. "coffee shop", "restaurant").
            location (str): The name of the current location (e.g. Ibn Sina Hospital, Dhaka).
            type (str): The type of place to search for, such as "restaurant", "cafe", or "bar".

        Returns:
            str: A string containing information on the nearby places, including the name, rating, number of ratings, and distance from the current location.
        """
        if not self.api_key:
            return [{"error": "Google MAP API key is not set. Please set the GOOGLE_API_KEY environment variable."}]

        try:
            results = self.nearby_places(query, location, type)
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
    tool = Nearby_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Execute the tool to perform a Google search
    query = "Find all the Supermarkets"
    location ="Baridhara Diplomatic Zone"
    type = "Supermarket"
    try:
        execution = tool.execute(query=query, location=location, type=type)
        print("\nExecution Result:")
        print(f"query: {query}, location: {location}, type: {type}")
        print(f"Number of results: {len(execution)}")
        print(f"results: {execution[0]}")
    except Exception as e:
        print(f"Execution failed: {e}")

    print("Done!")
