"""Compact weather MCP backed by Open-Meteo and IP geolocation."""

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TOOL = {
    "name": "weather_current",
    "description": "Current weather. Call for weather, temperature or rain; omit location to use approximate location.",
    "inputSchema": {
        "type": "object",
        "properties": {"location": {"type": "string", "description": "City or place; optional."}},
        "additionalProperties": False,
    },
}


def _get_json(url, params=None):
    target = url if not params else f"{url}?{urlencode(params)}"
    request = Request(target, headers={"User-Agent": "ada-weather-mcp/1.0"})
    with urlopen(request, timeout=8) as response:
        return json.load(response)


def _coordinates(location):
    if location:
        data = _get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": location, "count": 1, "language": "es", "format": "json"},
        )
        results = data.get("results", [])
        if not results:
            raise ValueError("location not found")
        place = results[0]
        return place["latitude"], place["longitude"], ", ".join(
            value for value in (place.get("name"), place.get("country")) if value
        )
    place = _get_json("https://ipapi.co/json/")
    return place["latitude"], place["longitude"], ", ".join(
        value for value in (place.get("city"), place.get("country_name")) if value
    )


def current(arguments):
    latitude, longitude, place = _coordinates((arguments or {}).get("location", "").strip())
    data = _get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,weather_code,precipitation,wind_speed_10m",
            "hourly": "precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto",
        },
    )
    current_data = data["current"]
    probability = data.get("hourly", {}).get("precipitation_probability", [None])[0]
    return {
        "location": place or "unknown",
        "temperature_c": current_data.get("temperature_2m"),
        "feels_like_c": current_data.get("apparent_temperature"),
        "weather_code": current_data.get("weather_code"),
        "precipitation_mm": current_data.get("precipitation"),
        "rain_probability_pct": probability,
        "wind_kmh": current_data.get("wind_speed_10m"),
        "observed_at": current_data.get("time"),
    }
