import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import AzureOpenAI
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import googlemaps
from math import sin, cos, sqrt, atan2, radians

gmaps = googlemaps.Client(key='')
# Initialize the Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint="https://qcri-llm-rag-3.openai.azure.com/",
    api_key="",
    api_version="2024-05-01-preview",
    azure_deployment="gpt-35-turbo",
)

# Provide the model deployment name you want to use for this example

deployment_name = "gpt-35-turbo"

# Simplified weather data
WEATHER_DATA = {
    "tokyo": {"temperature": "10", "unit": "celsius"},
    "san francisco": {"temperature": "72", "unit": "fahrenheit"},
    "paris": {"temperature": "22", "unit": "celsius"}
}

# Simplified timezone data
TIMEZONE_DATA = {
    "tokyo": "Asia/Tokyo",
    "san francisco": "America/Los_Angeles",
    "paris": "Europe/Paris"
}


def get_travel_info(origin_address: str, destination_address: str, mode: str = "driving"):
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


def get_place_info(location_address):
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


def distance(loc1: dict, loc2: dict) -> float:
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


def nearby_places(query: str, location: str, type: str) -> str:
    """
    Returns a string containing information on geospatial places based on a query and location.

    Args:
        query (str): The search term to look for geospatial places (e.g. "coffee shop", "restaurant").
        location (str): The name of the current location (e.g. Ibn Sina Hospital, Dhaka).
        type (str): The type of place to search for, such as "restaurant", "cafe", or "bar".

    Returns:
        str: A string containing information on the geospatial places, including the name, rating, number of ratings, and distance from the current location.
    """
    location_geocode = geocode(location)
    places_results = gmaps.places(
        query=query,
        location=location_geocode,
        type=type
    )
    all_poi = places_results["results"]
    extract_information = f"There are some {type} distance from the current location {location} in below:\n"
    # location_geocode = {'lat': location_geocode[0], 'lng': location_geocode[1]}
    for poi in all_poi:
        dist = distance(loc1=poi['geometry']['location'], loc2=location_geocode)
        rating = poi['rating'] if 'rating' in poi.keys() else 0
        total_user = poi['user_ratings_total'] if 'user_ratings_total' in poi.keys() else 0
        extract_information = extract_information + f"{poi['name']} ( distance: {dist} kilometers, rating:{rating}, total reviewer:{total_user})\n"
    return extract_information


def geocode(address: str) -> tuple:
    """
    Returns a tuple containing the latitude and longitude coordinates for a given address.

    Args:
        address (str): The address to geocode.

    Returns:
        tuple: A tuple containing the latitude and longitude coordinates in the format (lat, lng).
    """
    geocode_result = gmaps.geocode(address)
    return geocode_result[0]["geometry"]["location"]


def directions(origin: str, destination: str, mode: str = None, waypoints: list = None,
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


def trip(current_location: str, visiting_places: list[str], travel_mode: str = "driving"):
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
        place_info = get_place_info(loc)
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
            travel_time_text, travel_distance_text = get_travel_info(origin, destination, travel_mode)
            place_info_str += f"The travel time(distance) from {origin} to {destination} is {travel_time_text} ({travel_distance_text})\n"
    # print(place_info_str)
    return place_info_str


def run_conversation(query):
    # Initial user message
    messages = [
        {"role": "system",
         "content": "As a system prompt, you are an agent that can direct the corresponding function call based on the user's question and retrieve the requested information. Your task-txt-chatgpt is to fetch the information and provide it to the user. You are not expected to answer the question directly. The user will provide you with a question, and your role is to retrieve the relevant information using the appropriate function."},
        {"role": "user",
         "content": query}]

    # Define the functions for the model
    tools = [
        {
            "type": "function",
            "function": {
                "name": "nearby_places",
                "description": "Get information on geospatial places based on a query and location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search term to look for geospatial places (e.g. 'coffee shop', 'restaurant')",
                        },
                        "location": {
                            "type": "string",
                            "description": "The name of the current location in california. So must include california in the type",
                        },
                        "type": {
                            "type": "string",
                            "description": "The type of place to search for, such as 'restaurant', 'cafe', or 'bar'.",
                        },
                    },
                    "required": ["query", "location", "type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "directions",
                "description": "Get information on directions from an origin to a destination",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "The starting location for the directions.",
                        },
                        "destination": {
                            "type": "string",
                            "description": "The destination for the directions.",
                        },
                        "mode": {
                            "type": "string",
                            "description": "The mode of transportation to use for the directions, such as 'driving', 'walking', or 'transit'.",
                        },
                        "waypoints": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "A list of locations to visit along the route.",
                        },
                        "alternatives": {
                            "type": "boolean",
                            "description": "Whether to return multiple possible routes.",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "trip",
                "description": "Returns a string containing the location information and travel time and distance between the locations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_location": {
                            "type": "string",
                            "description": "The starting location of the trip."
                        },
                        "visiting_places": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "A list of locations to visit."
                        },
                        "travel_mode": {
                            "type": "string",
                            "description": "The mode of travel, defaults to 'driving'.",
                            "enum": [
                                "driving",
                                "walking",
                                "bicycling",
                                "transit"
                            ]
                        }
                    },
                    "required": [
                        "current_location",
                        "visiting_places"
                    ]
                },
                "returns": {
                    "type": "string",
                    "description": "A string containing the location information and travel time and distance between the locations."
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_place_info",
                "description": "Get details of a place, including its name, address, rating, types, opening hours, and whether it is currently open.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location_address": {
                            "type": "string",
                            "description": "The address or name of the location to search for.",
                        }
                    },
                    "required": ["location_address"]
                },
            }
        }
    ]

    # First API call: Ask the model to use the functions
    response = client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    # Process the model's response
    response_message = response.choices[0].message
    messages.append(response_message)

    print("Model's response:")
    print(response_message)
    # --- Parallel Tool Call Execution ---

    if response_message.tool_calls:
        print("Initiating parallel tool calls...")
        # Dictionary to store futures associated with their tool_call for later mapping
        futures = {}
        # Use ThreadPoolExecutor to manage threads
        # Max workers can be adjusted based on the expected number of concurrent I/O operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                print(f"Submitting {function_name} for parallel execution with args: {function_args}")

                # Submit each tool call to the thread pool
                if function_name == "nearby_places":
                    future = executor.submit(
                        nearby_places,
                        query=function_args.get("query"),
                        location=function_args.get("location"),
                        type=function_args.get("type")
                    )
                elif function_name == "directions":
                    future = executor.submit(
                        directions,
                        origin=function_args.get("origin"),
                        destination=function_args.get("destination"),
                        mode=function_args.get("mode"),
                        waypoints=function_args.get("waypoints"),
                        alternatives=function_args.get("alternatives")
                    )
                elif function_name == "trip":
                    future = executor.submit(
                        trip,
                        current_location=function_args.get("current_location"),
                        visiting_places=function_args.get("visiting_places"),
                        travel_mode=function_args.get("travel_mode"),
                    )
                elif function_name == "get_place_info":
                    future = executor.submit(
                        get_place_info,
                        location_address=function_args.get("location_address")
                    )
                else:
                    # Handle unknown function gracefully, perhaps in the main thread or with a mock future
                    future = executor.submit(lambda: json.dumps({"error": f"Unknown function: {function_name}"}))

                # Store the future along with the original tool_call object
                futures[future] = tool_call

        # Collect results as they complete (or in order of submission if not using as_completed)
        # as_completed yields futures as they finish, which is efficient for I/O-bound tasks.
        print("\nWaiting for parallel tool calls to complete...")
        for future in as_completed(futures):
            tool_call = futures[future]  # Get the original tool_call associated with this future
            function_name = tool_call.function.name
            function_response = future.result()  # Get the result of the function call

            print(f"Received response for {function_name} (ID: {tool_call.id})")

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            })
        print("All parallel tool calls completed.")

    else:
        print("No tool calls were made by the model.")

    return messages

    # Handle function calls
    # if response_message.tool_calls:
    #     with ThreadPoolExecutor(max_workers=5) as executor:
    #             for tool_call in response_message.tool_calls:
    #                 function_name = tool_call.function.name
    #                 function_args = json.loads(tool_call.function.arguments)
    #                 print(f"Function call: {function_name}")
    #                 print(f"Function arguments: {function_args}")
    #
    #                 if function_name == "nearby_places":
    #                     function_response = nearby_places(
    #                         query=function_args.get("query"),
    #                         location=function_args.get("location"),
    #                         # region=function_args.get("region"),
    #                         type=function_args.get("type")
    #                     )
    #
    #                 elif function_name == "directions":
    #                     function_response = directions(
    #                         origin=function_args.get("origin"),
    #                         destination=function_args.get("destination"),
    #                         mode=function_args.get("mode"),
    #                         waypoints=function_args.get("waypoints"),
    #                         alternatives=function_args.get("alternatives")
    #                     )
    #
    #                 elif function_name == "trip":
    #                     function_response = trip(
    #                         current_location=function_args.get("current_location"),
    #                         visiting_places=function_args.get("visiting_places"),
    #                         travel_mode=function_args.get("travel_mode"),
    #                     )
    #
    #                 elif function_name == "get_place_info":
    #                     function_response = get_place_info(
    #                         location_address=function_args.get("location_address")
    #                     )
    #
    #                 else:
    #                     function_response = json.dumps({"error": "Unknown function"})
    #
    #                 # print(function_response)
    #                 messages.append({
    #                     "tool_call_id": tool_call.id,
    #                     "role": "tool",
    #                     "name": function_name,
    #                     "content": function_response,
    #                 })
    # else:
    #     print("No tool calls were made by the model.")
    #
    #     # Second API call: Get the final response from the model
    # # final_response = client.chat.completions.create(
    # #     model=deployment_name,
    # #     messages=messages,
    # # )
    #
    # # return final_response.choices[0].message.content
    # return function_response


if __name__ == "__main__":
    # print(run_conversation("I'm currently in Vancouver, BC, Canada and interested in outdoor activities. What is the nearest park or nature reserve in this area ?"))
    # print(get_place_info("Dhaka"))
    # print(get_travel_info(origin_address="Amsterdam ", destination_address="canal cruise"))
    # print(directions(origin="Mittelpunkt Deutschlandsn Vogtei Germany", destination="Wildkatzendorf Hutscheroda Horselberg-Hainich Germany", waypoints=None, alternatives=True))
    # print(nearby_places(query="Count how many 7-Eleven locations are in near Yushima, Tokyo, Japan", location="Yushima, Tokyo, Japan", type="7-Eleven locations"))
    # print(get_place_info(location_address="Sheraton Chengdu Lido, 15 Section 1, Renmin Middle Road, Qingyang District, Chengdu, Sichuan, China"))
    # print(nearby_places(query="ATMs near Burton", location="Burton, California", type="ATM"))
    print(directions(origin="Rydges Wellington, Wellington 6011, New Zealand", destination="Victoria University of Wellington, Wellington 6012, New Zealand", mode="driving", waypoints=None,alternatives=False))
