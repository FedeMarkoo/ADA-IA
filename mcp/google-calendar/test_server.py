import json

from server import upcoming_events


def test_calendar_tool_returns_compact_event_shape(monkeypatch):
    monkeypatch.setattr(
        "server._access_token", lambda: "test-token"
    )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps(
                {
                    "items": [
                        {
                            "summary": "Reunión",
                            "start": {"dateTime": "2026-08-31T10:00:00-03:00"},
                            "end": {"dateTime": "2026-08-31T11:00:00-03:00"},
                            "location": "Oficina",
                            "description": "dato que no debe viajar",
                        }
                    ]
                }
            ).encode()

    monkeypatch.setattr("server.urllib.request.urlopen", lambda *_args, **_kwargs: Response())
    result = upcoming_events({"days": 7, "max_results": 10})

    assert result == {
        "status": "ok",
        "calendar": "primary",
        "days": 7,
        "events": [
            {
                "title": "Reunión",
                "start": "2026-08-31T10:00:00-03:00",
                "end": "2026-08-31T11:00:00-03:00",
                "location": "Oficina",
            }
        ],
    }
