"""Notification abstraction used by autonomous workflows."""
import logging

logger = logging.getLogger('ada.notifications')


class LogNotifier:
    def send(self, text, **kwargs):
        logger.info('notification channel=%s text=%s', kwargs.get('channel', 'log'), str(text)[:2000])


class CompositeNotifier:
    def __init__(self, notifiers):
        self.notifiers = list(notifiers)

    def send(self, text, **kwargs):
        errors = []
        for notifier in self.notifiers:
            try:
                notifier.send(text, **kwargs)
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError('; '.join(errors))
