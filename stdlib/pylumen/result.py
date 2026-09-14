"""Result/Option/panic for the Lumen standard library.

Mirrors the runtime semantics (runtime/rtlib.py) without importing it:
- ``Result`` is ``Ok(value)`` or ``Err(error)``; ``q()`` is the ``?`` operator.
- ``Option`` is ``Some(value)`` or ``NONE`` (absence).
- ``panic(msg)`` raises ``LumenPanic`` (unrecoverable error).
"""

from typing import Any, Callable, Optional


class LumenError(Exception):
    """Base Lumen exception (stdlib mirror)."""


class LumenPanic(LumenError):
    """Unrecoverable Lumen error, raised by ``panic``."""


def panic(msg: Any) -> None:
    """Raise LumenPanic with the given message."""
    raise LumenPanic(str(msg))


class Option:
    """Option[T] — Some(value) or NONE."""

    __slots__ = ("_value", "_some")

    def __init__(self, value: Any = None, some: bool = False):
        self._value = value
        self._some = some

    def is_some(self) -> bool:
        return self._some

    def is_none(self) -> bool:
        return not self._some

    def unwrap(self) -> Any:
        if not self._some:
            raise LumenPanic("unwrap on None")
        return self._value

    def unwrap_or(self, default: Any) -> Any:
        return self._value if self._some else default

    def expect(self, msg: str) -> Any:
        if not self._some:
            raise LumenPanic(msg)
        return self._value

    def map(self, fn: Callable[[Any], Any]) -> "Option":
        if not self._some:
            return NONE
        return Some(fn(self._value))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Option):
            if self._some != other._some:
                return False
            return (not self._some) or (self._value == other._value)
        return NotImplemented

    def __repr__(self) -> str:
        return f"Some({self._value!r})" if self._some else "None"


class Some(Option):
    """Present variant of Option."""

    def __init__(self, value: Any):
        super().__init__(value, True)


class _None(Option):
    """Absent variant of Option (NONE singleton)."""

    _inst: Optional["_None"] = None

    def __new__(cls) -> "_None":
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __init__(self) -> None:
        super().__init__(None, False)


NONE = _None()


class Result:
    """Result[T, E] — Ok(value) or Err(error). ``q()`` is the ``?`` operator."""

    __slots__ = ("_value", "_ok")

    def __init__(self, value: Any = None, ok: bool = True):
        self._value = value
        self._ok = ok

    def is_ok(self) -> bool:
        return self._ok

    def is_err(self) -> bool:
        return not self._ok

    def unwrap(self) -> Any:
        if not self._ok:
            raise LumenPanic(f"unwrap on Err: {self._value}")
        return self._value

    def unwrap_err(self) -> Any:
        if self._ok:
            raise LumenPanic(f"unwrap_err on Ok: {self._value}")
        return self._value

    def unwrap_or(self, default: Any) -> Any:
        return self._value if self._ok else default

    def expect(self, msg: str) -> Any:
        if not self._ok:
            raise LumenPanic(f"{msg}: {self._value}")
        return self._value

    def map(self, fn: Callable[[Any], Any]) -> "Result":
        if not self._ok:
            return self
        try:
            return Ok(fn(self._value))
        except Exception as e:  # noqa: BLE001
            return Err(str(e))

    def q(self) -> Any:
        """``?`` operator: unwrap Ok or propagate Err as LumenError."""
        if not self._ok:
            raise LumenError(f"unhandled Err: {self._value}")
        return self._value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Result):
            return self._ok == other._ok and self._value == other._value
        return NotImplemented

    def __repr__(self) -> str:
        tag = "Ok" if self._ok else "Err"
        return f"{tag}({self._value!r})"


class Ok(Result):
    """Success variant of Result."""

    def __init__(self, value: Any):
        super().__init__(value, True)


class Err(Result):
    """Error variant of Result."""

    def __init__(self, error: Any):
        super().__init__(error, False)
