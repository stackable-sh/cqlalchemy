"""Allows decoupled communication across different parts of the codebase."""
from blinker import signal, ANY
from enum import Enum


Event = Enum(
    "Event",
    [
        "BEFORE_SAVE",
        "AFTER_SAVE",
        "BEFORE_BATCH",
        "AFTER_BATCH",
        "BEFORE_EXECUTE",
        "AFTER_EXECUTE",
        "BEFORE_TRANSACTION",
        "AFTER_TRANSACTION",
        "BEFORE_REMOVE",
        "AFTER_REMOVE",
    ],
)


def callable(function):
    """Creates a callable that can handle events from the Signal library"""
    processor = lambda sender, **keywords: function()
    return processor


def subscribe(event: Event, subscriber, sender=None):
    """Subscribes a handler to a specific callback"""
    if not isinstance(event, Event):
        raise ValueError("You can only only subscribe to valid events from this module")
    pipe = signal(event.name)
    channel = ANY if sender is None else sender
    pipe.connect(subscriber, sender=channel, weak=False)


def propagate(event: Event, sender, **message):
    """Propagates @message to all the subscribers of @event"""
    if not isinstance(event, Event):
        raise ValueError("You can only only subscribe to valid events from this module")
    pipe = signal(event.name)
    return pipe.send(sender, **message)
