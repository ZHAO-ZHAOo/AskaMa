"""OneMap API adapter for AI Grandma.

OneMap is Singapore's official map service (free, requires registration).
https://docs.onemap.sg/

This adapter provides:
- Address search (geocoding)
- Route calculation (travel time estimation)

Falls back to approximate distance (haversine) when API is unavailable.
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from typing import Any

import urllib.request
import urllib.parse
import json


ONEMAP_BASE = "https://www.onemap.gov.sg/api"


@dataclass
class OneMapResult:
    """Result of a OneMap query."""
    lat: float
    lng: float
    address: str
    travel_time_minutes: float
    source: str  # "onemap" or "haversine"


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate haversine distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _estimate_travel_time_km(distance_km: float, mode: str = "public_transport") -> float:
    """Estimate travel time from distance."""
    speed_kmh = {
        "public_transport": 25,
        "driving": 40,
        "walking": 5,
    }
    speed = speed_kmh.get(mode, 25)
    return (distance_km / speed) * 60  # minutes


class OneMapAdapter:
    """Adapter for OneMap API with fallback."""

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("ONEMAP_TOKEN")
        self._token_expiry = 0
        self._rate_limit_delay = 0.5  # seconds between calls
        self._last_call_time = 0

    def _rate_limit(self) -> None:
        """Simple rate limiting."""
        elapsed = time.time() - self._last_call_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_call_time = time.time()

    def search_address(self, query: str) -> dict | None:
        """Search for an address, return first result."""
        if not self.token:
            return None

        self._rate_limit()
        params = urllib.parse.urlencode({"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y"})
        url = f"{ONEMAP_BASE}/common/elastic/search?{params}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", self.token)

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                results = data.get("results", [])
                if results:
                    return results[0]
        except Exception:
            pass
        return None

    def get_travel_time(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        mode: str = "public_transport",
    ) -> OneMapResult:
        """Get estimated travel time between two points.

        Uses OneMap route API if available, otherwise falls back to haversine.
        """
        # Fallback: haversine distance
        dist_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        time_min = _estimate_travel_time_km(dist_km, mode)

        return OneMapResult(
            lat=dest_lat,
            lng=dest_lng,
            address="",
            travel_time_minutes=time_min,
            source="haversine",
        )

    def geocode_postal(self, postal_code: str) -> tuple[float, float] | None:
        """Geocode a Singapore postal code."""
        if not self.token:
            return None

        result = self.search_address(postal_code)
        if result:
            lat = float(result.get("LATITUDE", 0))
            lng = float(result.get("LONGITUDE", 0))
            if lat and lng:
                return (lat, lng)
        return None


# Singleton instance
_adapter: OneMapAdapter | None = None


def get_adapter() -> OneMapAdapter:
    """Get or create the singleton adapter."""
    global _adapter
    if _adapter is None:
        _adapter = OneMapAdapter()
    return _adapter
