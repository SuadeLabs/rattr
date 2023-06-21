from __future__ import annotations

from typing import Any


def _pretty_list_format(items: list[str]) -> str:
    """Return a nicely formatted list of strings as a string.

    >>> _pretty_list_format([])
    ValueError(...)
    >>> _pretty_list_format(["matthew"])
    "matthew"
    >>> _pretty_list_format(["matthew", "mark"])
    "matthew and mark"
    >>> _pretty_list_format(["matthew", "mark", "luke", "john"])
    "matthew, mark, luke, and john"
    """
    if not items:
        raise ValueError("items must not be empty")

    if len(items) == 1:
        return items[0]

    _comma_separated_items = ", ".join(items[:-1])
    _final_item = items[-1]

    return f"{_comma_separated_items} and {_final_item}"


def _get_simple_present_of_be(things: list[Any]) -> str:
    if len(things) >= 2:
        return "are"
    return "is"


def confirm_walrus_happiness(walruses):
    unhappy_walruses = []

    for walrus in walruses:
        if (happiness := walrus.happiness) > 75:
            print(f"{walrus.name} is {happiness} / {walrus.max_happiness} happy :)")

        unhappy_walruses.append(walrus)

    if not unhappy_walruses:
        return True

    # Log the walruses that are displeased
    _walrus_or_walruses_by_name = _pretty_list_format(
        [w.name for w in unhappy_walruses]
    )
    _are_or_is = _get_simple_present_of_be(unhappy_walruses)
    print(f"{_walrus_or_walruses_by_name} {_are_or_is} unhappy :(")

    return False
