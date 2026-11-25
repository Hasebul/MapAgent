"""The four MapTools of MapAgent (Section 3.4, Table 11 and Appendix C).

Each tool composes one or more primitive Google Maps APIs and returns plain text that is handed to the
downstream modules:

* Trip      - Place Details + Directions: place metadata for every stop and the travel time/distance between
              every ordered pair of stops.
* Route     - Directions: distance, duration and step-by-step instructions (all legs, all alternatives).
* Nearby    - Geocoding + Places search: points of interest within a radius (20 km by default).
* PlaceInfo - Places search + Place Details: address, rating, opening hours, contact info, services, reviews.

Tools do not raise on ordinary failures (unknown place, no route, bad argument): the failure is returned as
text so that one bad call does not abort the whole query. Fatal Google Maps errors (invalid key, exhausted
quota) are propagated as :class:`~mapagent.map_tools.client.MapsAuthError`.
"""

from __future__ import annotations

import inspect
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

from .client import MapsAuthError, MapsClient, is_fatal_maps_error

EARTH_RADIUS_KM = 6371.0
DEFAULT_NEARBY_RADIUS_KM = 20.0
MAX_PLACES_RADIUS_M = 50_000  # upper bound accepted by the Places API
TRIP_MAX_WORKERS = 8
TRAVEL_MODES = ("driving", "walking", "bicycling", "transit")
_TRAVEL_MODE_ALIASES = {
    "drive": "driving", "car": "driving", "by car": "driving", "auto": "driving", "taxi": "driving",
    "motorcycle": "driving", "motorbike": "driving",
    "walk": "walking", "foot": "walking", "on foot": "walking", "pedestrian": "walking",
    "bike": "bicycling", "bicycle": "bicycling", "cycling": "bicycling", "cycle": "bicycling", "biking": "bicycling",
    "public transport": "transit", "public transit": "transit", "public transportation": "transit",
    "bus": "transit", "train": "transit", "subway": "transit", "metro": "transit", "rail": "transit", "tram": "transit",
}
PRICE_LEVELS = {0: "Free", 1: "Inexpensive", 2: "Moderate", 3: "Expensive", 4: "Very Expensive"}
_SERVICE_FIELDS = (
    ("serves_breakfast", "Serves Breakfast"),
    ("serves_brunch", "Serves Brunch"),
    ("serves_lunch", "Serves Lunch"),
    ("serves_dinner", "Serves Dinner"),
    ("serves_vegetarian_food", "Serves Vegetarian Food"),
    ("serves_beer", "Serves Beer"),
    ("serves_wine", "Serves Wine"),
    ("dine_in", "Dine In"),
    ("takeout", "Takeout"),
    ("delivery", "Delivery"),
    ("reservable", "Reservable"),
    ("wheelchair_accessible_entrance", "Wheelchair Accessible Entrance"),
)
MAX_REVIEWS = 3
MAX_REVIEW_CHARS = 300


# --------------------------------------------------------------------------- helpers
def normalize_travel_mode(mode: Optional[str]) -> str:
    """Map free-form travel modes ("car", "on foot", "bus", ...) to a Directions API mode."""
    if not mode:
        return "driving"
    value = str(mode).strip().lower()
    if value in TRAVEL_MODES:
        return value
    return _TRAVEL_MODE_ALIASES.get(value, "driving")


def haversine_km(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Great-circle distance in kilometers between two ``{"lat": .., "lng": ..}`` points."""
    lat1, lon1, lat2, lon2 = map(radians, (a["lat"], a["lng"], b["lat"], b["lng"]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * atan2(sqrt(h), sqrt(1 - h))


def html_to_text(html: str) -> str:
    text = BeautifulSoup(html or "", "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def format_distance(meters: float) -> str:
    return f"{meters / 1000:.1f} km" if meters >= 1000 else f"{int(round(meters))} m"


def format_duration(seconds: float) -> str:
    minutes = max(int(round(seconds / 60.0)), 1)
    if minutes < 60:
        return f"{minutes} min" if minutes == 1 else f"{minutes} mins"
    hours, minutes = divmod(minutes, 60)
    text = f"{hours} hour" + ("s" if hours != 1 else "")
    if minutes:
        text += f" {minutes} min" + ("s" if minutes != 1 else "")
    return text


def _dedupe(items: Iterable[str]) -> List[str]:
    seen, result = set(), []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            continue
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [v for v in value if isinstance(v, str)]


def _positive_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _normalize_place_type(place_type: Optional[str]) -> Optional[str]:
    """Google place types are lower-case words joined by underscores (e.g. ``police_station``)."""
    if not place_type:
        return None
    value = re.sub(r"[\s\-]+", "_", str(place_type).strip().lower())
    return value if re.fullmatch(r"[a-z_]+", value) else None


def _guarded(function: Callable[..., Any], *args: Any) -> Tuple[Any, Optional[str]]:
    """Run ``function`` and return ``(result, None)`` or ``(None, error message)``."""
    try:
        return function(*args), None
    except Exception as exc:  # noqa: BLE001 - reported as text
        if is_fatal_maps_error(exc):
            raise MapsAuthError(str(exc)) from exc
        return None, f"{type(exc).__name__}: {exc}"


def find_place(maps: MapsClient, query: str) -> Optional[Dict[str, Any]]:
    """Text Search followed by Place Details for the best match."""
    query = (query or "").strip()
    if not query:
        return None
    candidates = (maps.places(query=query) or {}).get("results") or []
    if not candidates:
        return None
    details = (maps.place(candidates[0]["place_id"]) or {}).get("result") or {}
    return details or candidates[0]


def locate(maps: MapsClient, location: str) -> Optional[Dict[str, float]]:
    """Coordinates of an address or a place name (Geocoding, falling back to a Places text search)."""
    geocoded = maps.geocode(location) or []
    if geocoded:
        return geocoded[0]["geometry"]["location"]
    candidates = (maps.places(query=location) or {}).get("results") or []
    if candidates and candidates[0].get("geometry"):
        return candidates[0]["geometry"]["location"]
    return None


def format_place(place: Dict[str, Any], *, detailed: bool = False) -> str:
    """Human-readable place description (format of the paper's examples, Appendix E)."""
    hours = place.get("current_opening_hours") or place.get("opening_hours") or {}
    weekday_text = hours.get("weekday_text") or []
    lines = [
        f"Name: {place.get('name', 'N/A')}",
        f"Address: {place.get('formatted_address') or place.get('vicinity') or 'N/A'}",
        f"Rating: {place.get('rating', 'N/A')}",
        f"Types: {', '.join(place.get('types') or []) or 'N/A'}",
        f"Is Open Now: {hours.get('open_now', 'N/A')}",
        "Weekday Opening Hours:",
    ]
    lines.extend(f"- {day}" for day in weekday_text)
    if not weekday_text:
        lines.append("- Unknown")
    if detailed:
        lines.append(f"Number of Ratings: {place.get('user_ratings_total', 0)}")
        lines.append(f"Price Level: {PRICE_LEVELS.get(place.get('price_level'), 'Unknown')}")
        for key, label in _SERVICE_FIELDS:
            if key in place:  # only report attributes Google actually provides
                lines.append(f"{label}: {'Yes' if place[key] else 'No'}")
        phone = place.get("international_phone_number") or place.get("formatted_phone_number")
        if phone:
            lines.append(f"Phone: {phone}")
        if place.get("website"):
            lines.append(f"Website: {place['website']}")
        if place.get("business_status"):
            lines.append(f"Business Status: {place['business_status']}")
        reviews = place.get("reviews") or []
        if reviews:
            lines.append("Reviews:")
            for review in reviews[:MAX_REVIEWS]:
                text = re.sub(r"\s+", " ", review.get("text") or "").strip()
                if len(text) > MAX_REVIEW_CHARS:
                    text = text[:MAX_REVIEW_CHARS].rstrip() + "..."
                when = review.get("relative_time_description", "")
                lines.append(f"- ({review.get('rating', 'N/A')}/5{', ' + when if when else ''}) {text}")
    return "\n".join(lines)


def travel_time_and_distance(maps: MapsClient, origin: str, destination: str, mode: str = "driving") -> Tuple[str, str]:
    """Duration and distance of the first route from ``origin`` to ``destination``."""
    mode = normalize_travel_mode(mode)
    request: Dict[str, Any] = {"origin": origin, "destination": destination, "mode": mode}
    if mode in ("driving", "transit"):
        request["departure_time"] = datetime.now()
    routes = maps.directions(**request)
    if not routes:
        raise LookupError(f"no {mode} route found")
    legs = routes[0].get("legs") or []
    if len(legs) == 1:
        return legs[0]["duration"]["text"], legs[0]["distance"]["text"]
    return _leg_totals(legs)


def _leg_totals(legs: Sequence[Dict[str, Any]]) -> Tuple[str, str]:
    seconds = sum(leg["duration"]["value"] for leg in legs)
    meters = sum(leg["distance"]["value"] for leg in legs)
    return format_duration(seconds), format_distance(meters)


def _step_text(step: Dict[str, Any]) -> str:
    text = html_to_text(step.get("html_instructions", "")) or step.get("travel_mode", "").title()
    line = f"{text} ({step['distance']['text']}, {step['duration']['text']})"
    transit = step.get("transit_details")
    if transit:
        vehicle = ((transit.get("line") or {}).get("vehicle") or {}).get("name", "Transit")
        name = (transit.get("line") or {}).get("short_name") or (transit.get("line") or {}).get("name", "")
        departure = (transit.get("departure_stop") or {}).get("name", "?")
        arrival = (transit.get("arrival_stop") or {}).get("name", "?")
        line += f" [{vehicle} {name}: {departure} -> {arrival}, {transit.get('num_stops', '?')} stops]"
    return line


# --------------------------------------------------------------------------- the four MapTools
def trip(maps: MapsClient, current_location: str, visiting_places: Sequence[str], travel_mode: str = "driving") -> str:
    """Trip Tool: place details of every stop + travel time/distance between every ordered pair of stops."""
    mode = normalize_travel_mode(travel_mode)
    locations = _dedupe([current_location, *_as_list(visiting_places)])
    if len(locations) < 2:
        return "Trip Tool needs a starting location and at least one other place to visit."
    pairs = [(a, b) for a in locations for b in locations if a != b]
    workers = max(1, min(TRIP_MAX_WORKERS, len(locations) + len(pairs)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        place_futures = [pool.submit(_guarded, find_place, maps, loc) for loc in locations]
        leg_futures = [pool.submit(_guarded, travel_time_and_distance, maps, a, b, mode) for a, b in pairs]
        places = [future.result() for future in place_futures]
        legs = [future.result() for future in leg_futures]

    lines = ["All Location Info:"]
    for location, (place, error) in zip(locations, places):
        lines.append(location)
        if place:
            lines.append(format_place(place))
        else:
            lines.append(f"No information found for this location{f' ({error})' if error else ''}.")
    lines.append(f"Travel mode: {mode}")
    for (origin, destination), (value, error) in zip(pairs, legs):
        if value:
            lines.append(f"The travel time(distance) from {origin} to {destination} is {value[0]} ({value[1]})")
        else:
            lines.append(f"The travel time(distance) from {origin} to {destination} is unavailable ({error}).")
    return "\n".join(lines)


def route(
    maps: MapsClient,
    origin: str,
    destination: str,
    mode: str = "driving",
    waypoints: Optional[Sequence[str]] = None,
    alternatives: Optional[bool] = True,
) -> str:
    """Route Tool: distance, duration and step-by-step directions of every returned route (all legs)."""
    mode = normalize_travel_mode(mode)
    stops = _dedupe(_as_list(waypoints)) or None
    routes = maps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        waypoints=stops,
        alternatives=True if alternatives is None else bool(alternatives),
    )
    if not routes:
        return f"No {mode} route was found from {origin} to {destination}."
    via = f" with waypoint(s) {', '.join(stops)}" if stops else ""
    count = len(routes)
    lines = [
        f"There are total {count} route{'s' if count != 1 else ''} from {origin} to {destination}{via} "
        f"(travel mode: {mode}). The route information is provided below:",
        "",
    ]
    for number, item in enumerate(routes, 1):
        legs = item.get("legs") or []
        if len(legs) == 1:
            distance, duration = legs[0]["distance"]["text"], legs[0]["duration"]["text"]
        else:
            duration, distance = _leg_totals(legs)
        lines.append(f"Route {number}:(VIA) {item.get('summary') or 'N/A'} ({distance}, {duration})")
        lines.append("Details steps are provided below:")
        for leg_number, leg in enumerate(legs, 1):
            if len(legs) > 1:
                lines.append(
                    f"Leg {leg_number}: {leg.get('start_address', '?')} -> {leg.get('end_address', '?')} "
                    f"({leg['distance']['text']}, {leg['duration']['text']})"
                )
            lines.extend(_step_text(step) for step in leg.get("steps") or [])
        lines.append("")
    return "\n".join(lines).rstrip()


def nearby(
    maps: MapsClient,
    query: str,
    location: str,
    type: Optional[str] = None,  # noqa: A002 - name used in the paper's tool signature
    radius: float = DEFAULT_NEARBY_RADIUS_KM,
) -> str:
    """Nearby Tool: points of interest within ``radius`` kilometers of ``location``."""
    radius_km = _positive_float(radius, DEFAULT_NEARBY_RADIUS_KM)
    center = locate(maps, location) if location else None
    if center is None:
        return f"Could not find the location {location!r}."
    place_type = _normalize_place_type(type)
    params = {
        "query": (query or type or "").strip() or "point of interest",
        "location": center,
        "radius": min(int(radius_km * 1000), MAX_PLACES_RADIUS_M),
    }
    results: List[Dict[str, Any]] = []
    if place_type:
        try:
            results = (maps.places(type=place_type, **params) or {}).get("results") or []
        except Exception as exc:  # noqa: BLE001 - an unsupported type is retried without it
            if is_fatal_maps_error(exc):
                raise MapsAuthError(str(exc)) from exc
            results = []
    if not results:
        results = (maps.places(**params) or {}).get("results") or []

    entries = []
    for poi in results:
        point = (poi.get("geometry") or {}).get("location")
        if point is None:
            continue
        distance = haversine_km(center, point)
        if distance <= radius_km:
            entries.append((poi, distance))

    label = (type or query or "places").strip()
    if not entries:
        return f"No {label} found within {radius_km:g} kilometers of the location {location}."
    lines = [f"There are some {label} within {radius_km:g} kilometers of the location {location}, as shown below:"]
    for poi, distance in entries:
        lines.append(
            f"{poi.get('name', 'Unknown')} ( distance: {distance:.3f} kilometers, rating:{poi.get('rating', 0)}, "
            f"total reviewer:{poi.get('user_ratings_total', 0)})"
        )
    return "\n".join(lines)


def place_info(maps: MapsClient, location_address: str) -> str:
    """PlaceInfo Tool: detailed information about a single place."""
    place = find_place(maps, location_address)
    if not place:
        return f"No place information was found for {location_address!r}."
    return f"Place information for {location_address}:\n" + format_place(place, detailed=True)


# --------------------------------------------------------------------------- registry and schemas
_TRAVEL_MODE_SCHEMA = {
    "type": "string",
    "enum": list(TRAVEL_MODES),
    "description": "The mode of travel, defaults to 'driving'.",
}


@dataclass(frozen=True)
class MapTool:
    name: str
    function: Callable[..., str]
    description: str
    parameters: Dict[str, Any]
    required: Tuple[str, ...]
    argument_aliases: Dict[str, str] = field(default_factory=dict)

    @property
    def schema(self) -> Dict[str, Any]:
        """OpenAI function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": self.parameters, "required": list(self.required)},
            },
        }


MAP_TOOLS: Dict[str, MapTool] = {
    tool.name: tool
    for tool in (
        MapTool(
            name="trip",
            function=trip,
            description=(
                "Trip Tool. Retrieves information about locations and the travel routes between them. Combines the "
                "Place Details and Directions APIs to fetch place metadata (address, rating, opening hours) of every "
                "location and the travel time and distance between every ordered pair of locations. Use it for "
                "multi-stop trips, the order of visits, round trips and itineraries."
            ),
            parameters={
                "current_location": {"type": "string", "description": "The starting location of the trip."},
                "visiting_places": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of locations to visit.",
                },
                "travel_mode": _TRAVEL_MODE_SCHEMA,
            },
            required=("current_location", "visiting_places"),
            argument_aliases={
                "mode": "travel_mode",
                "origin": "current_location",
                "start_location": "current_location",
                "places": "visiting_places",
                "destinations": "visiting_places",
            },
        ),
        MapTool(
            name="route",
            function=route,
            description=(
                "Route Tool. Fetches route information between two points using the Directions API, including the "
                "distance, the estimated travel time and the step-by-step navigation instructions of each route."
            ),
            parameters={
                "origin": {"type": "string", "description": "The starting location for the directions."},
                "destination": {"type": "string", "description": "The destination for the directions."},
                "mode": dict(_TRAVEL_MODE_SCHEMA, description="The mode of transportation, defaults to 'driving'."),
                "waypoints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional intermediate stops to visit along the route, in order.",
                },
                "alternatives": {
                    "type": "boolean",
                    "description": "Whether to return multiple possible routes (defaults to true).",
                },
            },
            required=("origin", "destination"),
            argument_aliases={"travel_mode": "mode", "start": "origin", "end": "destination"},
        ),
        MapTool(
            name="nearby",
            function=nearby,
            description=(
                "Nearby Tool. Identifies points of interest within a specified area around a location using the "
                "Nearby Search API. Returns place names, ratings, number of reviews and the distance from the "
                "location."
            ),
            parameters={
                "query": {
                    "type": "string",
                    "description": "The search term to look for geospatial places (e.g. 'coffee shop', 'restaurant').",
                },
                "location": {
                    "type": "string",
                    "description": "The name or address of the current location (e.g. 'Ibn Sina Hospital, Dhaka').",
                },
                "type": {
                    "type": "string",
                    "description": "The type of place to search for, such as 'restaurant', 'cafe', or 'hospital'.",
                },
                "radius": {
                    "type": "number",
                    "description": "Radius in kilometers of the circular area used for filtering, defaults to 20.",
                },
            },
            required=("query", "location"),
            argument_aliases={"place_type": "type", "radius_km": "radius", "keyword": "query", "near": "location"},
        ),
        MapTool(
            name="place_info",
            function=place_info,
            description=(
                "PlaceInfo Tool. Retrieves detailed information about a given place using the Place Details API, "
                "including address, rating, opening hours, contact information, services and reviews."
            ),
            parameters={
                "location_address": {
                    "type": "string",
                    "description": "The address or name of the location to search for.",
                },
            },
            required=("location_address",),
            argument_aliases={
                "location": "location_address",
                "address": "location_address",
                "name": "location_address",
                "place": "location_address",
                "query": "location_address",
            },
        ),
    )
}

TOOL_SCHEMAS: List[Dict[str, Any]] = [tool.schema for tool in MAP_TOOLS.values()]

# Function names used by the original release and by the OctoTools baseline.
TOOL_NAME_ALIASES = {
    "trip_tool": "trip",
    "route_tool": "route",
    "directions": "route",
    "directions_tool": "route",
    "nearby_tool": "nearby",
    "nearby_places": "nearby",
    "placeinfo": "place_info",
    "place_info_tool": "place_info",
    "get_place_info": "place_info",
    "poi": "place_info",
    "poi_tool": "place_info",
}


def canonical_tool_name(name: str) -> str:
    key = (name or "").strip().lower()
    return TOOL_NAME_ALIASES.get(key, key)


def run_map_tool(maps: MapsClient, name: str, arguments: Optional[Dict[str, Any]]) -> str:
    """Dispatch one tool call. Returns the tool output (or an error message) as text."""
    canonical = canonical_tool_name(name)
    tool = MAP_TOOLS.get(canonical)
    if tool is None:
        return f"Error: unknown map tool {name!r}. Available tools: {', '.join(MAP_TOOLS)}."
    signature = inspect.signature(tool.function).parameters
    kwargs: Dict[str, Any] = {}
    for key, value in (arguments or {}).items():
        key = tool.argument_aliases.get(key, key)
        if key in signature and key != "maps" and value is not None:
            kwargs[key] = value
    missing = [
        param
        for param, spec in signature.items()
        if param != "maps" and spec.default is inspect.Parameter.empty and param not in kwargs
    ]
    if missing:
        return f"Error: the {canonical} tool is missing required argument(s): {', '.join(missing)}."
    maps.usage.add_map_tool_call()
    try:
        return tool.function(maps, **kwargs)
    except MapsAuthError:
        raise
    except Exception as exc:  # noqa: BLE001 - reported to the agent as text
        if is_fatal_maps_error(exc):
            raise MapsAuthError(str(exc)) from exc
        return f"Error while running the {canonical} tool with {kwargs}: {type(exc).__name__}: {exc}"
