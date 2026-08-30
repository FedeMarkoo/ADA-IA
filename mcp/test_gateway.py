import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class McpGatewayTest(unittest.TestCase):
    def test_gateway_exposes_both_mcp_endpoints(self):
        self.assertEqual({"/filesystem", "/web-search", "/weather"}, set(server.SERVERS))
        self.assertEqual(
            ["filesystem.list_files", "filesystem.read_file"],
            [tool["name"] for tool in server.SERVERS["/filesystem"]["tools"]],
        )
        self.assertEqual("web_search", server.SERVERS["/web-search"]["tools"][0]["name"])
        self.assertEqual("weather_current", server.SERVERS["/weather"]["tools"][0]["name"])

    def test_weather_contract_is_compact_and_routes_to_service(self):
        self.assertEqual({"type", "properties", "additionalProperties"}, set(server.weather.TOOL["inputSchema"]))
        with patch.object(server.weather, "current", return_value={"temperature_c": 21}):
            self.assertEqual(
                {"temperature_c": 21}, server.call_tool("/weather", "weather_current", {})
            )

    def test_weather_rounds_temperature_and_returns_short_forecast(self):
        with patch.object(
            server.weather,
            "_get_json",
            side_effect=[
                {"results": [{"latitude": -34.6, "longitude": -58.4, "name": "Buenos Aires", "country": "Argentina"}]},
                {
                    "current": {
                        "temperature_2m": 20.74,
                        "apparent_temperature": 19.96,
                        "weather_code": 1,
                        "precipitation": 0,
                        "wind_speed_10m": 11.26,
                        "time": "2026-08-30T08:00",
                    },
                    "daily": {
                        "time": ["2026-08-30", "2026-08-31"],
                        "weather_code": [0, 1],
                        "temperature_2m_min": [10.04, 11.12],
                        "temperature_2m_max": [21.66, 22.31],
                        "precipitation_probability_max": [5, 10],
                    },
                },
            ],
        ):
            result = server.weather.current({"location": "Buenos Aires"})

        self.assertEqual(20.7, result["temperature_c"])
        self.assertEqual(20.0, result["feels_like_c"])
        self.assertEqual(2, len(result["forecast"]))
        self.assertEqual(21.7, result["forecast"][0]["max_c"])
        self.assertEqual(5, result["forecast"][0]["rain_probability_pct"])

    def test_filesystem_read_file_is_routed_by_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            path.write_text("ok", encoding="utf-8")
            os.environ["ADA_FILESYSTEM_ALLOWED_ROOTS"] = tmp
            result = server.call_tool("/filesystem", "filesystem.read_file", {"path": str(path)})
            self.assertEqual("ok", result["content"])


if __name__ == "__main__":
    unittest.main()
