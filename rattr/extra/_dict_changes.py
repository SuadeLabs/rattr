from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from rattr.versioning.typing import Self


KT = TypeVar("KT")
VT = TypeVar("VT")

Item = TypeVar("Item")


def key_changes(targets: Mapping[KT, VT]) -> Iterable[Item]:
    return targets.keys()


def value_changes(targets: Mapping[KT, VT]) -> Iterable[Item]:
    return targets.values()


class DictChanges(Generic[KT, VT, Item]):
    """A context manager to track the changes to the keys in the given dict-like."""

    def __init__(
        self,
        target: Mapping[KT, VT],
        iter_items: Callable[[Mapping[KT, VT]], Iterable[Item]] = lambda t: t.keys(),
    ):
        self.target = target
        self.keys_fn = iter_items

    def __enter__(self) -> Self:
        self.antecedent = set(self.keys_fn(self.target))
        return self

    def __exit__(self, *_) -> None:
        self.consequent = set(self.keys_fn(self.target))

    @property
    def added(self) -> set[Item]:
        """Return the keys added to the dict-like in the context block."""
        return self.consequent - self.antecedent

    @property
    def removed(self) -> set[Item]:
        """Return the keys removed from the dict-like in the context block."""
        return self.antecedent - self.consequent
