import os
import requests
from typing import List, Dict, Any

from octotools.tools.base import BaseTool
from datetime import datetime

from dotenv import load_dotenv
import googlemaps

gmaps = googlemaps.Client(key='AIzaSyC8EPK5_SZ999QHQGlIOu48HgiB2Uql0hI')
load_dotenv()


class Trip_Tool(BaseTool):
    def __init__(self):
        super().__init__(
            tool_name="Trip Tool",
            tool_description="A tool that performs Google Map searches based on a given text query.",
            tool_version="1.0.0",
            input_types={
                "current_location": "str - The starting location of the trip.",
                "visiting_places": "array - A list of locations to visit.",
                "travel_mode": "str -The mode of travel, defaults to 'driving'."
            },
            output_type="str - A string containing the location information and travel time and distance between the locations.",
            demo_commands=[
                {
                    "command": 'execution = tool.execute(query="Python programming")',
                    "description": "Perform a Google search for 'Python programming' and return the default number of results."
                },
                {
                    "command": 'execution = tool.execute(current_location=Dhaka, visiting_places=[Lalbagh, BUET], travel_mode=driving)',
                    "description": "Perform a Trip tools search for near Dhaka to visit two palces lalbagh and BUet by driving"
                },
            ],
        )
        # self.api_key = os.getenv("GOOGLE_API_KEY")
        self.api_key = os.getenv("GOOGLE_MAP_API_KEY") # NOTE: Replace with your own API key (Ref: https://developers.google.com/custom-search/v1/introduction)
        self.cx = os.getenv("GOOGLE_CX") # NOTE: Replace with your own custom search (Ref: https://programmablesearchengine.google.com/controlpanel/all)
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def get_travel_info(self,origin_address: str, destination_address: str, mode: str = "driving"):
        """
        Returns the travel time and distance between two addresses.

        Parameters:
            origin_address (str): The starting address of the journey.
            destination_address (str): The destination address of the journey.
            mode (str): The driving mood of the journey

        Returns:
            tuple: A tuple containing the travel time and distance in text format.
        """
        now = datetime.now()
        directions_result = gmaps.directions(origin=origin_address,
                                             destination=destination_address,
                                             mode=mode,
                                             departure_time=now)
        travel_time_text = directions_result[0]['legs'][0]['duration']['text']
        travel_distance_text = directions_result[0]['legs'][0]['distance']['text']
        return travel_time_text, travel_distance_text

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

    def trip(self, current_location: str, visiting_places: list[str], travel_mode: str = "driving"):
        """
        Returns a string containing the location information and travel time and distance between the locations.

        Parameters:
            current_location (str): The starting location of the trip.
            visiting_places (list): A list of locations to visit.
            travel_mode (str): The mode of travel, defaults to "driving".

        Returns:
            str: A string containing the location information and travel time and distance between the locations.
        """
        all_locations = [current_location] + visiting_places
        place_info_str = 'All Location Info: \n'
        for loc in all_locations:
            place_info_str += loc + ' \n'
            place_info = self.get_place_info(loc)
            place_info_str += f"Name: {place_info['name']}\nAddress: {place_info['address']}\nRating: {place_info['rating']}\nTypes: {', '.join(place_info['types'])}\nIs Open Now: {place_info['is_open_now']}\nWeekday Opening Hours:\n"
            if place_info['weekdays_opening_hours'] == 'N/A':
                place_info_str += f"- {'Unknown'}\n"
            else:
                for weekday_open_hours in place_info['weekdays_opening_hours']:
                    place_info_str += f"- {weekday_open_hours}\n"
        for i in range(0, len(all_locations)):
            for j in range(0, len(all_locations)):
                origin = all_locations[i]
                destination = all_locations[j]
                if origin == destination:
                    continue
                travel_time_text, travel_distance_text = self.get_travel_info(origin, destination, travel_mode)
                place_info_str += f"The travel time(distance) from {origin} to {destination} is {travel_time_text} ({travel_distance_text})\n"
        # print(place_info_str)
        return place_info_str

    # def google_search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
    #     """
    #     Performs a Google search using the provided query.
    #
    #     Parameters:
    #         query (str): The search query.
    #         num_results (int): The number of search results to return.
    #
    #     Returns:
    #         Dict[str, Any]: The raw search results from the Google API.
    #     """
    #     params = {
    #         'q': query,
    #         'key': self.api_key,
    #         'cx': self.cx,
    #         'num': num_results
    #     }
    #
    #     response = requests.get(self.base_url, params=params)
    #     return response.json()

    def execute(self, current_location: str, visiting_places: list[str], travel_mode: str = "driving") -> List[str]:
        """
        Executes a Trip Tool based on the provided Information.

        Parameters:
            current_location (str): The starting location of the trip.
            visiting_places (list): A list of locations to visit.
            travel_mode (str): The mode of travel, defaults to "driving".

        Returns:
            str: A string containing the location information and travel time and distance between the locations.
        """
        if not self.api_key:
            return [{"error": "Google MAP API key is not set. Please set the GOOGLE_API_KEY environment variable."}]

        try:
            results = self.trip(current_location,visiting_places,travel_mode)
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
    tool = Trip_Tool()

    # Get tool metadata
    metadata = tool.get_metadata()
    print(metadata)

    # Execute the tool to perform a Google search
    current_location ="Indira Road, Dhaka"
    visiting_places = ["Military Museum Dhaka", "Multiplan Center", "Sonali Bank, BUET"]
    travel_mode = "driving"
    try:
        execution = tool.execute(current_location=current_location, visiting_places=visiting_places, travel_mode=travel_mode)
        print("\nExecution Result:")
        print(f"current location: {current_location}, visiting places: {visiting_places}, travel_mode: {travel_mode}")
        print(f"Number of results: {len(execution)}")
        print(f"results: {execution[0]}")
    except Exception as e:
        print(f"Execution failed: {e}")

    print("Done!")
