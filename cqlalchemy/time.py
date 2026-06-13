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

"""Generic Duration Helper Methods"""

__all__ = [
    "hours",
    "days",
    "weeks",
]


def hours(number: int) -> int:
    """Returns duration of @number hours in seconds"""
    if not isinstance(number, int):
        raise ValueError("You must provide a valid `int` as parameter")
    return number * minutes(60)


def minutes(number: int) -> int:
    if not isinstance(number, int):
        raise ValueError("You must provide a valid `int` as parameter")
    return number * 60


def days(number: int) -> int:
    """Returns duration of @number days in seconds"""
    if not isinstance(number, int):
        raise ValueError("You must provide a valid `int` as parameter")
    return number * hours(24)


def weeks(number: int) -> int:
    """Returns duration of @number weeks in seconds"""
    if not isinstance(number, int):
        raise ValueError("You must provide a valid `int` as parameter")
    return number * days(7)
