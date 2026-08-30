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
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 3,
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    current_data = data["current"]
    probability = daily.get("precipitation_probability_max", [None])[0]
    forecast = [
        {
            "date": date,
            "min_c": round(minimum, 1),
            "max_c": round(maximum, 1),
            "rain_probability_pct": rain,
        }
        for date, minimum, maximum, rain in zip(
            daily.get("time", []),
            daily.get("temperature_2m_min", []),
            daily.get("temperature_2m_max", []),
            daily.get("precipitation_probability_max", []),
        )
    ]
    return {
        "location": place or "unknown",
        "temperature_c": round(current_data["temperature_2m"], 1),
        "feels_like_c": round(current_data["apparent_temperature"], 1),
        "weather_code": current_data.get("weather_code"),
        "precipitation_mm": current_data.get("precipitation"),
        "rain_probability_pct": probability,
        "wind_kmh": round(current_data["wind_speed_10m"], 1),
        "observed_at": current_data.get("time"),
        "forecast": forecast,
    }
