"""Collection types: Vec, Mapa, Set, Fila for the Lumen standard library."""

from typing import Any, Iterable, Optional, Iterator, Generic, TypeVar
import collections as _collections

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


class Vec(list):
    """Lumen Vec — dynamic array with Lumen API methods."""

    def __new__(cls, items=None):
        if items is None:
            return super().__new__(cls, [])
        return super().__new__(cls, items)

    def push(self, item: Any) -> None:
        """Append item to the end."""
        self.append(item)

    def pop(self, index: int = -1) -> Any:
        """Remove and return item at index."""
        return super().pop(index)

    def unshift(self, item: Any) -> None:
        """Insert item at the beginning."""
        self.insert(0, item)

    def shift(self) -> Any:
        """Remove and return the first item."""
        return super().pop(0)

    def size(self) -> int:
        """Return the number of elements."""
        return len(self)

    def empty(self) -> bool:
        """Check if vec is empty."""
        return len(self) == 0

    def sort(self, reverse: bool = False) -> None:
        """Sort the vec in-place."""
        super().sort(reverse=reverse)

    def map(self, func):
        """Return a new Vec with func applied to each element."""
        return Vec([func(x) for x in self])

    def filter(self, func) -> 'Vec':
        """Return a new Vec with elements where func returns true."""
        return Vec([x for x in self if func(x)])

    def reduce(self, func, initial=None) -> Any:
        """Reduce the vec to a single value."""
        if initial is None:
            if not self:
                raise ValueError("reduce of empty sequence with no initial value")
            result = self[0]
            items = self[1:]
        else:
            result = initial
            items = self
        for item in items:
            result = func(result, item)
        return result

    def for_each(self, func) -> None:
        """Apply func to each element."""
        for item in self:
            func(item)

    def find(self, func):
        """Find first element where func returns true."""
        for item in self:
            if func(item):
                return item
        return None

    def contains(self, item: Any) -> bool:
        """Check if item is in vec."""
        return item in self

    def join(self, sep: str = "") -> str:
        """Join elements as string."""
        return sep.join(str(x) for x in self)

    def reversed(self) -> 'Vec':
        """Return a new reversed Vec."""
        return Vec(list(reversed(self)))

    def slice(self, start: int = 0, end: Optional[int] = None) -> 'Vec':
        """Return a slice of the vec."""
        return Vec(self[start:end])


class Mapa(dict):
    """Lumen Mapa — key-value map with Lumen API methods."""

    def __new__(cls, items=None):
        if items is None:
            return super().__new__(cls)
        if isinstance(items, dict):
            return super().__new__(cls, items)
        return super().__new__(cls, items)

    def set(self, key: Any, value: Any) -> None:
        """Set key-value pair."""
        self[key] = value

    def get(self, key: Any, default=None) -> Any:
        """Get value for key, or default."""
        return super().get(key, default)

    def remove(self, key: Any) -> Any:
        """Remove key and return its value."""
        return self.pop(key)

    def has(self, key: Any) -> bool:
        """Check if key exists."""
        return key in self

    def keys(self) -> list:
        """Return list of keys."""
        return list(super().keys())

    def values(self) -> list:
        """Return list of values."""
        return list(super().values())

    def entries(self) -> list:
        """Return list of (key, value) tuples."""
        return list(self.items())

    def size(self) -> int:
        """Return number of entries."""
        return len(self)

    def empty(self) -> bool:
        """Check if mapa is empty."""
        return len(self) == 0

    def for_each(self, func) -> None:
        """Apply func to each (key, value) pair."""
        for k, v in self.items():
            func(k, v)

    def map_values(self, func) -> 'Mapa':
        """Return new Mapa with func applied to each value."""
        return Mapa({k: func(v) for k, v in self.items()})

    def filter(self, func) -> 'Mapa':
        """Return new Mapa with entries where func returns true."""
        return Mapa({k: v for k, v in self.items() if func(k, v)})


class Set(set):
    """Lumen Set — unique element collection with Lumen API methods."""

    def __new__(cls, items=None):
        if items is None:
            return super().__new__(cls)
        return super().__new__(cls, items)

    def add(self, item: Any) -> None:
        """Add item to set."""
        super().add(item)

    def remove(self, item: Any) -> None:
        """Remove item from set."""
        self.discard(item)

    def has(self, item: Any) -> bool:
        """Check if item is in set."""
        return item in self

    def size(self) -> int:
        """Return number of elements."""
        return len(self)

    def empty(self) -> bool:
        """Check if set is empty."""
        return len(self) == 0

    def union(self, other: 'Set') -> 'Set':
        """Return union of two sets."""
        return Set(self | other)

    def intersection(self, other: 'Set') -> 'Set':
        """Return intersection of two sets."""
        return Set(self & other)

    def difference(self, other: 'Set') -> 'Set':
        """Return difference of two sets."""
        return Set(self - other)

    def is_subset(self, other: 'Set') -> bool:
        """Check if this is a subset of other."""
        return self <= other

    def is_superset(self, other: 'Set') -> bool:
        """Check if this is a superset of other."""
        return self >= other

    def for_each(self, func) -> None:
        """Apply func to each element."""
        for item in self:
            func(item)


class Fila:
    """Lumen Fila — queue data structure (FIFO)."""

    def __init__(self, items=None):
        self._data = _collections.deque(items or [])

    def enqueue(self, item: Any) -> None:
        """Add item to the back of the queue."""
        self._data.append(item)

    def dequeue(self) -> Any:
        """Remove and return item from the front."""
        if self.is_empty():
            raise IndexError("dequeue from empty Fila")
        return self._data.popleft()

    def peek(self) -> Any:
        """Return front item without removing."""
        if self.is_empty():
            raise IndexError("peek from empty Fila")
        return self._data[0]

    def size(self) -> int:
        """Return number of items."""
        return len(self._data)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._data) == 0

    def to_list(self) -> list:
        """Convert queue to list."""
        return list(self._data)

    def clear(self) -> None:
        """Clear the queue."""
        self._data.clear()

    def __len__(self):
        return self.size()

    def __repr__(self):
        return f"Fila({list(self._data)})"

    def __iter__(self):
        return iter(self._data)
