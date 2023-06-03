
"""
Signals:
Allows decoupled communication across different parts of the codebase. 
"""
from blinker import signal, ANY

SIGNAL_MODEL_CREATED = "STACK_MODEL_CREATED"
SIGNAL_MODEL_SAVED = "STACK_MODEL_SAVED"
SIGNAL_MODEL_UPDATED = "STACK_MODEL_UPDATED"
SIGNAL_MODEL_READ = "STACK_MODEL_READ"
SIGNAL_MODEL_DELETED = "STACK_MODEL_DELETE"

events = [
    SIGNAL_MODEL_CREATED, SIGNAL_MODEL_READ, 
    SIGNAL_MODEL_UPDATED, SIGNAL_MODEL_DELETED, SIGNAL_MODEL_SAVED
]


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
    pipe.connect(subscriber, sender=channel)


def propagate(event, sender, **message):
    """Propagates @message to all the subscribers of @event"""
    if event not in events:
        raise ValueError("You can only only subscribe to valid events from this module")
    pipe = signal(event)
    pipe.send(sender=sender, **message)