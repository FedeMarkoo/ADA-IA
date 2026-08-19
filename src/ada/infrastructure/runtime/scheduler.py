"""Small durable scheduler for event-driven ADA workflows."""

import logging
import threading
import uuid

from ada.infrastructure.runtime.event_bus import EventBus

logger = logging.getLogger("ada.scheduler")


class Scheduler:
    def __init__(self, memory, handlers=None, interval=1.0, max_attempts=3):
        self.bus = EventBus(memory)
        self.handlers = handlers or {}
        self.interval = max(0.1, float(interval))
        self.max_attempts = max(1, int(max_attempts))
        self._stop = threading.Event()
        self.owner = uuid.uuid4().hex

    def schedule(self, topic, payload, priority=0, delay_seconds=0, dedupe_key=None):
        return self.bus.publish(topic, payload, priority, dedupe_key, delay_seconds)

    def cancel(self, event_id):
        return self.bus.cancel(event_id)

    def run_once(self):
        handled = 0
        for event in self.bus.consume():
            handler = self.handlers.get(event["topic"])
            if handler is None:
                self.bus.fail(event["id"], "no_handler")
                continue
            try:
                handler(event["payload"])
                self.bus.ack(event["id"])
            except Exception as exc:
                logger.exception("event_failed topic=%s id=%s", event["topic"], event["id"])
                if event["attempts"] < self.max_attempts:
                    self.bus.retry(event["id"], exc, delay_seconds=min(60, 2 ** event["attempts"]))
                else:
                    self.bus.fail(event["id"], exc)
            handled += 1
        return handled

    def run_forever(self):
        while not self._stop.is_set():
            self.run_once()
            self._stop.wait(self.interval)

    def stop(self):
        self._stop.set()
