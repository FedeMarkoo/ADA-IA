"""Durable local event bus backed by ADA's SQLite memory store."""

import json


class EventBus:
    def __init__(self, memory):
        self.memory = memory

    def publish(self, topic, payload, priority=0, dedupe_key=None, delay_seconds=0):
        return self.memory.publish_event(topic, payload, priority, dedupe_key, delay_seconds)

    def consume(self, limit=10):
        for event in self.memory.claim_events(limit):
            try:
                event["payload"] = json.loads(event["payload"])
            except (TypeError, ValueError):
                event["payload"] = {}
            yield event

    def ack(self, event_id):
        self.memory.finish_event(event_id, success=True)

    def retry(self, event_id, error, delay_seconds=5):
        self.memory.finish_event(event_id, success=False, error=error, retry_seconds=delay_seconds)

    def fail(self, event_id, error):
        self.memory.finish_event(event_id, success=False, error=error)

    def cancel(self, event_id):
        return self.memory.cancel_event(event_id)
