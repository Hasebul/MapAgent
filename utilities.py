import time
import random
import requests
import os
import openai
from openai import OpenAI
import json
import base64
import googlemaps
import func_timeout
import requests
import numpy as np

from bs4 import BeautifulSoup
from typing import Union, Any
from math import isclose
from openai import AzureOpenAI
from math import sin, cos, sqrt, atan2, radians
from datetime import datetime

from fuzzywuzzy import fuzz

gmaps = googlemaps.Client(key='')


def safe_execute(code_string: str, keys=None):
    def execute(x):
        try:
            exec(x)
            locals_ = locals()
            if keys is None:
                return locals_.get('ans', None)
            else:
                return [locals_.get(k, None) for k in keys]
        except Exception:
            return None

    try:
        ans = func_timeout.func_timeout(1, execute, args=(code_string,))
    except func_timeout.FunctionTimedOut:
        ans = None
    return ans


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
        week_oh = ""
        for i in weekdays_opening_hours:
            week_oh += i + "\n"
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
            'weekdays_opening_hours': week_oh,
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
    waypoints = None
    alternatives = True
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


def get_codex_response(prompt, api_key, engine="code-davinci-002", temperature=0, max_tokens=256, top_p=1, n=1,
                       patience=10, sleep_time=0):
    while patience > 0:
        patience -= 1
        try:
            response = openai.Completion.create(engine=engine,
                                                prompt=prompt,
                                                api_key=api_key,
                                                temperature=temperature,
                                                max_tokens=max_tokens,
                                                top_p=top_p,
                                                n=n,
                                                stop=['\n\n'],
                                                frequency_penalty=0,
                                                presence_penalty=0)
            prediction = response["choices"][0]["text"].strip()
            if prediction != "" and prediction != None:
                return prediction
        except Exception as e:
            print(e)
            if sleep_time > 0:
                time.sleep(sleep_time)
    return ""


def get_gpt3_response(prompt, api_key, engine="text-davinci-002", temperature=0, max_tokens=256, top_p=1, n=1,
                      patience=100, sleep_time=0):
    while patience > 0:
        patience -= 1
        try:
            response = openai.Completion.create(engine=engine,
                                                prompt=prompt,
                                                api_key=api_key,
                                                temperature=temperature,
                                                max_tokens=max_tokens,
                                                top_p=top_p,
                                                n=n,
                                                stop=['\n\n'],
                                                frequency_penalty=0,
                                                presence_penalty=0)
            prediction = response["choices"][0]["text"].strip()
            if prediction != "" and prediction != None:
                return prediction
        except Exception as e:
            print(e)
            if sleep_time > 0:
                time.sleep(sleep_time)
    return ""


# def get_chat_response(messages, api_key, model="gpt-3.5-turbo", temperature=0, max_tokens=256, n=1, patience=100, sleep_time=0):
#     while patience > 0:
#         patience -= 1
#         try:
#             response = openai.ChatCompletion.create(model=model,
#                                                 messages=messages,
#                                                 api_key=api_key,
#                                                 temperature=temperature,
#                                                 max_tokens=max_tokens,
#                                                 n=n)
#             if n == 1:
#                 prediction = response['choices'][0]['message']['content'].strip()
#                 if prediction != "" and prediction != None:
#                     return prediction
#             else:
#                 prediction = [choice['message']['content'].strip() for choice in response['choices']]
#                 if prediction[0] != "" and prediction[0] != None:
#                     return prediction
#
#         except Exception as e:
#             print(e)
#             if sleep_time > 0:
#                 time.sleep(sleep_time)
#     return ""


def get_chat_response(messages, api_key, model="gpt-3.5-turbo", temperature=0, max_tokens=256, n=1, patience=100,
                      sleep_time=0):
    while patience > 0:
        patience -= 1
        try:
            # their gpt
            # response = openai.ChatCompletion.create(model=model,
            #                                     messages=messages,
            #                                     api_key=api_key,
            #                                     temperature=temperature,
            #                                     max_tokens=max_tokens,
            #                                     n=n)
            # if n == 1:
            #     prediction = response['choices'][0]['message']['content'].strip()
            #     if prediction != "" and prediction != None:
            #         return prediction
            # else:
            #     prediction = [choice['message']['content'].strip() for choice in response['choices']]
            #     if prediction[0] != "" and prediction[0] != None:
            #         return prediction
            # Azure
            client = AzureOpenAI(
                azure_endpoint="https://qcri-llm-rag-3.openai.azure.com/",
                api_key="",
                api_version="2024-05-01-preview",

            )
            response = client.chat.completions.create(
                model="gpt-35-turbo",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                n=n
            )
            if n == 1:
                prediction = response.choices[0].message.content.strip()
                if prediction != "" and prediction != None:
                    return prediction
            else:
                prediction = [choice.message.content.strip() for choice in response.choices]
                if prediction[0] != "" and prediction[0] != None:
                    return prediction

        except Exception as e:
            print(e)
            if sleep_time > 0:
                time.sleep(sleep_time)
    return ""


def get_qwen_response(messages, api_key, model="gpt-3.5-turbo", temperature=0, max_tokens=256, n=1, patience=100,
                      sleep_time=0):
    while patience > 0:
        patience -= 1
        try:
            # their gpt
            # response = openai.ChatCompletion.create(model=model,
            #                                     messages=messages,
            #                                     api_key=api_key,
            #                                     temperature=temperature,
            #                                     max_tokens=max_tokens,
            #                                     n=n)
            # if n == 1:
            #     prediction = response['choices'][0]['message']['content'].strip()
            #     if prediction != "" and prediction != None:
            #         return prediction
            # else:
            #     prediction = [choice['message']['content'].strip() for choice in response['choices']]
            #     if prediction[0] != "" and prediction[0] != None:
            #         return prediction
            # Azure
            #
            client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key="",
            )
            response = (client.chat.completions.create(
                model="qwen/qwen-2.5-72b-instruct",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                n=n
            ))
            #     client.chat.completions.create(
            #     model="gpt-35-turbo",
            #     messages=messages,
            #     temperature=temperature,
            #     max_tokens=max_tokens,
            #     top_p=0.95,
            #     frequency_penalty=0,
            #     presence_penalty=0,
            #     stop=None,
            #     n=n
            # ))
            if n == 1:
                prediction = response.choices[0].message.content.strip()
                if prediction != "" and prediction != None:
                    return prediction
            else:
                prediction = [choice.message.content.strip() for choice in response.choices]
                if prediction[0] != "" and prediction[0] != None:
                    return prediction

        except Exception as e:
            print(e)
            if sleep_time > 0:
                time.sleep(sleep_time)
    return ""


def get_40_response(messages, api_key, model, temperature=0, max_tokens=256, n=1, patience=100,
                    sleep_time=0):
    # messages = [
    #     {
    #         "role": messages[0]['role'],
    #         "content": [
    #             {
    #                 "type": "text",
    #                 "text": messages[0]['content']
    #             }
    #         ]
    #     }
    # ]
    messages = [
        {"role": "system", "content": "You are a helpful, creative, and smart assistant."},
        {"role": "user", "content": messages},
    ]
    while patience > 0:
        patience -= 1
        try:
            # their gpt
            # response = openai.ChatCompletion.create(model=model,
            #                                     messages=messages,
            #                                     api_key=api_key,
            #                                     temperature=temperature,
            #                                     max_tokens=max_tokens,
            #                                     n=n)
            # if n == 1:
            #     prediction = response['choices'][0]['message']['content'].strip()
            #     if prediction != "" and prediction != None:
            #         return prediction
            # else:
            #     prediction = [choice['message']['content'].strip() for choice in response['choices']]
            #     if prediction[0] != "" and prediction[0] != None:
            #         return prediction
            # Azure
            client = AzureOpenAI(
                azure_endpoint="https://qcri-llm-rag-3.openai.azure.com/",
                api_key="",
                api_version="2024-05-01-preview",

            )
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
                n=n
            )
            if n == 1:
                prediction = response.choices[0].message.content.strip()
                if prediction != "" and prediction != None:
                    return prediction
            else:
                prediction = [choice.message.content.strip() for choice in response.choices]
                if prediction[0] != "" and prediction[0] != None:
                    return prediction

        except Exception as e:
            print(e)
            if sleep_time > 0:
                time.sleep(sleep_time)
    return ""


# def get_chat_response(messages, api_key, model="gpt-3.5-turbo", temperature=0, max_tokens=256, n=1, patience=100,
#                       sleep_time=0):  # gpt4
#     while patience > 0:
#
#         patience -= 1
#         try:
#
#             # Configuration
#             API_KEY = "01488083a8d243e684bd48a39152d90a"
#             # API_KEY = "YOUR_API_KEY"
#             # IMAGE_PATH = "YOUR_IMAGE_PATH"
#             # encoded_image = base64.b64encode(open(IMAGE_PATH, 'rb').read()).decode('ascii')
#             headers = {
#                 "Content-Type": "application/json",
#                 "api-key": API_KEY,
#             }
#
#             # Payload for the request
#             payload = {
#                 "messages": messages,
#                 "temperature": 0.7,
#                 "top_p": 0.95,
#                 "max_tokens": 1000
#             }
#             # GPT-35-TURBO-0125
#             ENDPOINT = "https://qcri-llm-rag-4.openai.azure.com/openai/deployments/GPT-4o/chat/completions?api-version=2024-02-15-preview"
#
#             # Send request
#             try:
#                 response = requests.post(ENDPOINT, headers=headers, json=payload)
#                 response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
#             except requests.RequestException as e:
#                 raise SystemExit(f"Failed to make the request. Error: {e}")
#             if n == 1:
#                 rep = response.json()
#                 prediction = rep["choices"][0]["message"]["content"].strip()
#                 # print(prediction)
#                 if prediction != "" and prediction != None:
#                     return prediction
#             else:
#                 prediction = [choice.message.content.strip() for choice in response.choices]
#                 if prediction[0] != "" and prediction[0] != None:
#                     return prediction
#
#         except Exception as e:
#             print(e)
#             if sleep_time > 0:
#                 time.sleep(sleep_time)
#     return ""


# def get_chat_response(messages, api_key, model="gpt-3.5-turbo", temperature=0, max_tokens=256, n=1, patience=100,
#                       sleep_time=0):  # gpt4
#     while patience > 0:
#
#         patience -= 1
#         try:
#
#
#             # Configuration
#             API_KEY = "154bfc83018f41f19341d76cefe5d95c"
#             # API_KEY = "YOUR_API_KEY"
#             # IMAGE_PATH = "YOUR_IMAGE_PATH"
#             # encoded_image = base64.b64encode(open(IMAGE_PATH, 'rb').read()).decode('ascii')
#             headers = {
#                 "Content-Type": "application/json",
#                 "api-key": API_KEY,
#             }
#
#             # Payload for the request
#             payload = {
#                 "messages": messages,
#                 "temperature": 0.7,
#                 "top_p": 0.95,
#                 "max_tokens": 1000
#             }
#             # GPT-35-TURBO-0125
#             ENDPOINT = "https://qcri-llm-rag-3.openai.azure.com/openai/deployments/gpt-35-turbo/chat/completions?api-version=2023-03-15-preview"
#
#             # Send request
#             try:
#                 response = requests.post(ENDPOINT, headers=headers, json=payload)
#                 response.raise_for_status()  # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
#             except requests.RequestException as e:
#                 raise SystemExit(f"Failed to make the request. Error: {e}")
#             if n == 1:
#                 rep = response.json()
#                 prediction = rep["choices"][0]["message"]["content"].strip()
#                 # print(prediction)
#                 if prediction != "" and prediction != None:
#                     return prediction
#             else:
#                 prediction = [choice.message.content.strip() for choice in response.choices]
#                 if prediction[0] != "" and prediction[0] != None:
#                     return prediction
#
#         except Exception as e:
#             print(e)
#             if sleep_time > 0:
#                 time.sleep(sleep_time)
#     return ""


def floatify_ans(ans):
    if ans is None:
        return None
    elif type(ans) == dict:
        ans = list(ans.values())[0]
    elif type(ans) == bool:
        ans = ans
    elif type(ans) in [list, tuple]:
        if not ans:
            return None
        else:
            try:
                ans = float(ans[0])
            except Exception:
                ans = str(ans[0])
    else:
        try:
            ans = float(ans)
        except Exception:
            ans = str(ans)
    return ans


def score_string_similarity(str1, str2):
    if str1 == str2:
        return 2.0
    elif " " in str1 or " " in str2:
        str1_split = str1.split(" ")
        str2_split = str2.split(" ")
        overlap = list(set(str1_split) & set(str2_split))
        return len(overlap) / max(len(str1_split), len(str2_split))
    else:
        return 0.0


def normalize_prediction_tabmwp(prediction, options=None, unit=None):
    # the numerical answer
    if isinstance(prediction, float):
        prediction = round(prediction, 3)
        return prediction

    # the string answer
    if isinstance(prediction, str):
        prediction = prediction.replace('$', '')
        if unit:
            prediction = prediction.replace(unit, '')
        prediction = prediction.strip().lower()

        if not options:
            # numeric answer: convert to float
            try:
                if '/' in prediction:
                    prediction = int(prediction.split('/')[0]) / int(prediction.split('/')[1])
                elif ',' in prediction:
                    prediction = float(prediction.replace(',', ''))
                elif '%' in prediction:
                    prediction = float(prediction.split('%')[0]) / 100
                else:
                    prediction = float(prediction)
            except Exception:
                pass

                # the string answer from choices
    if options:
        options = [x.lower() for x in options]
        if prediction is None:
            prediction = options[0]
        elif isinstance(prediction, str):
            if prediction not in options:
                # find the most similar option
                scores = [score_string_similarity(x, prediction) for x in options]
                max_idx = int(np.argmax(scores))  # json does not recognize NumPy data types
                prediction = options[max_idx]
    return prediction


def normalize_ground_tabmwp(gt_ans, ans_type=None):
    if ans_type in ['integer_number', 'decimal_number']:
        if '/' in gt_ans:
            gt_ans = int(gt_ans.split('/')[0]) / int(gt_ans.split('/')[1])
        elif ',' in gt_ans:
            gt_ans = float(gt_ans.replace(',', ''))
        elif '%' in gt_ans:
            gt_ans = float(gt_ans.split('%')[0]) / 100
        else:
            gt_ans = float(gt_ans)
    elif ans_type.endswith('_text'):
        gt_ans = str(gt_ans)
    else:
        raise ValueError(ans_type)
    return gt_ans


def normalize_ground_scienceqa(gt_ans):
    gt_ans = gt_ans.lower()
    return gt_ans


def normalize_prediction_scienceqa(prediction, options=None):
    # the string answer from choices
    if options:
        options = [x.lower() for x in options]
        if prediction is None:
            prediction = options[0]
        elif isinstance(prediction, str):
            if prediction not in options:
                # find the most similar option
                scores = [score_string_similarity(x, prediction) for x in options]
                max_idx = int(np.argmax(scores))  # json does not recognize NumPy data types
                prediction = options[max_idx]
    return prediction


def get_precision(gt_ans: float) -> int:
    precision = 5
    if '.' in str(gt_ans):
        precision = len(str(gt_ans).split('.')[-1])
    return precision


def safe_equal(prediction: Union[bool, float, str],
               reference: Union[float, str],
               include_percentage: bool = False,
               is_close: float = False) -> bool:
    if prediction is None:
        return False
    elif type(prediction) == bool:
        # bool questions
        if prediction:
            return reference == 'yes'
        else:
            return reference == 'no'
    elif type(reference) == str and type(prediction) == str:
        # string questions
        # string questions
        # prediction = prediction.strip().lower()
        # reference = reference.strip().lower()
        # return prediction == reference
        prediction = prediction.strip().lower()
        reference = reference.strip().lower()
        fuzzy_score = fuzz.ratio(prediction, reference)
        is_correct = False
        if fuzzy_score >= 30:
            is_correct = True
        return is_correct
    else:
        # number questions
        if include_percentage:
            gt_result = [reference / 100, reference, reference * 100]
        else:
            gt_result = [reference]
        for item in gt_result:
            try:
                if is_close:
                    if isclose(item, prediction, rel_tol=0.001):
                        return True
                precision = min(get_precision(prediction), get_precision(item))
                if round(prediction, precision) == round(item, precision):
                    return True
            except Exception:
                continue
        return False


def _validate_server(address):
    if not address:
        raise ValueError('Must provide a valid server for search')
    if address.startswith('http://') or address.startswith('https://'):
        return address
    PROTOCOL = 'http://'
    print(f'No protocol provided, using "{PROTOCOL}"')
    return f'{PROTOCOL}{address}'


def call_bing_search(endpoint, bing_api_key, query, count):
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}
    params = {"q": query, "textDecorations": True,
              "textFormat": "HTML", "count": count, "mkt": "en-GB"}
    try:
        server = _validate_server(endpoint)  # server address
        server_response = requests.get(server, headers=headers, params=params)
        resp_status = server_response.status_code
        if resp_status == 200:
            result = server_response.json()
            return result
    except:
        pass

    return None


def parse_bing_result(result):
    responses = []
    try:
        value = result["webPages"]["value"]
    except:
        return responses

    for i in range(len(value)):
        snippet = value[i]['snippet'] if 'snippet' in value[i] else ""
        snippet = snippet.replace("<b>", "").replace("</b>", "").strip()
        if snippet != "":
            responses.append(snippet)

    return responses
