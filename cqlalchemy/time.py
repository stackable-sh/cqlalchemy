"""Generic Duration Helper Methods"""

__all__ = ["hours", "days", "weeks",]


def hours(number: int) -> int:
    """Returns duration of @number hours in seconds"""
    if not isinstance(number, int):
        raise ValueError("You must provide a valid `int` as parameter")
    return number * minutes(60)

def minutes(number:int) -> int:
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
