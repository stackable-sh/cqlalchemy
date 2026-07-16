# Copyright 2026 Iroiso Ikpokonte
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Allows decoupled communication across different parts of the codebase."""

from enum import Enum
from blinker import signal, ANY

__all__ = ["Event", "subscribe", "propagate",]

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
        "UOW_START",
        "UOW_END",
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
