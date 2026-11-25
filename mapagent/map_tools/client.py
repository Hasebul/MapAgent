"""Google Maps web-service client used by the MapTools.

The underlying ``googlemaps.Client`` is created only when MapAgent actually needs it, so importing the
package never requires an API key, and every web-service request is counted for the cost analysis.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from ..usage import UsageTracker

API_KEY_ENV_VARS = ("GOOGLE_MAPS_API_KEY", "GOOGLE_MAP_API_KEY")


class MapsAuthError(RuntimeError):
    """The Google Maps key is missing, invalid, or out of quota. Retrying will not help."""


def get_maps_api_key(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    for name in API_KEY_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value
    return None


def is_fatal_maps_error(exc: BaseException) -> bool:
    """Request denied / invalid key / exhausted daily quota."""
    if isinstance(exc, MapsAuthError):
        return True
    text = f"{getattr(exc, 'status', '')} {exc}".upper()
    return any(token in text for token in ("REQUEST_DENIED", "OVER_DAILY_LIMIT", "API KEY IS INVALID", "INVALID API KEY"))


class MapsClient:
    """Thin counting wrapper around ``googlemaps.Client``.

    ``gmaps_client`` can be any object exposing ``places``, ``place``, ``directions`` and ``geocode``
    (used by the offline tests).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        usage: Optional[UsageTracker] = None,
        timeout: int = 30,
        gmaps_client: Any = None,
    ) -> None:
        self.usage = usage or UsageTracker()
        if gmaps_client is not None:
            self._gmaps = gmaps_client
            return
        key = get_maps_api_key(api_key)
        if not key:
            raise MapsAuthError(
                "Google Maps API key not found. Set GOOGLE_MAPS_API_KEY (see .env.example); "
                "it needs the Places, Directions and Geocoding APIs enabled."
            )
        try:
            import googlemaps
        except ImportError as exc:  # pragma: no cover - dependency error
            raise ImportError("The `googlemaps` package is required: pip install -r requirements.txt") from exc
        try:
            self._gmaps = googlemaps.Client(key=key, timeout=timeout)
        except ValueError as exc:  # e.g. "Invalid API key provided."
            raise MapsAuthError(f"Could not create the Google Maps client: {exc}") from exc

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        self.usage.add_map_api_call()
        return getattr(self._gmaps, method)(*args, **kwargs)

    def places(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("places", *args, **kwargs)

    def place(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("place", *args, **kwargs)

    def directions(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("directions", *args, **kwargs)

    def geocode(self, *args: Any, **kwargs: Any) -> Any:
        return self._call("geocode", *args, **kwargs)
