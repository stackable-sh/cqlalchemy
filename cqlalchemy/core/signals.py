
"""
Signals:
Allows decoupled communication across different parts of the codebase. 
"""
from blinker import signal, ANY

BEFORE_COMMIT = "BEFORE_COMMIT"
AFTER_COMMIT = "AFTER_COMMIT"

events = [BEFORE_COMMIT, AFTER_COMMIT,]


def callable(function):
    """Creates a callable that can handle events from the Signal library"""
    processor = lambda sender, **keywords : function()
    return processor

def subscribe(event, subscriber, sender=None):
    """Subscribes a handler to a specific callback"""
    if event not in events:
        raise ValueError("You can only only subscribe to valid events from this module")
    pipe = signal(event)
    channel = ANY if sender is None else sender
    pipe.connect(subscriber, sender=channel, weak=False)

def propagate(event, sender, **message):
    """Propagates @message to all the subscribers of @event"""
    if event not in events:
        raise ValueError("You can only only subscribe to valid events from this module")
    pipe = signal(event)
    return pipe.send(sender)