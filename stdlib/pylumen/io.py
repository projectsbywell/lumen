"""I/O utilities for the Lumen standard library."""

import sys
import os
from typing import List, Optional, IO
from io import StringIO, BytesIO


class LumenIO:
    """Lumen I/O wrapper."""

    def __init__(self, stream=None):
        self._stream = stream

    def write(self, data: str) -> int:
        """Write data to stream."""
        if self._stream is None:
            self._stream = sys.stdout
        return self._stream.write(data)

    def writeline(self, data: str = "") -> int:
        """Write data with newline."""
        return self.write(data + "\n")

    def flush(self) -> None:
        """Flush the stream."""
        if self._stream is not None:
            self._stream.flush()


class LumenFile:
    """Lumen file handle wrapper."""

    def __init__(self, filepath: str, mode: str = "r"):
        self._filepath = filepath
        self._mode = mode
        self._file = open(filepath, mode)

    def read(self, size: int = -1) -> str:
        """Read from file."""
        return self._file.read(size) if size > 0 else self._file.read()

    def readline(self) -> str:
        """Read a single line."""
        return self._file.readline()

    def readlines(self) -> List[str]:
        """Read all lines."""
        return self._file.readlines()

    def write(self, data: str) -> int:
        """Write to file."""
        return self._file.write(data)

    def writelines(self, lines: List[str]) -> int:
        """Write multiple lines."""
        return self._file.writelines(lines)

    def close(self) -> None:
        """Close the file."""
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __iter__(self):
        return iter(self._file)


def read_file(filepath: str) -> str:
    """Read entire file as string."""
    with open(filepath, "r") as f:
        return f.read()


def write_file(filepath: str, data: str) -> int:
    """Write string to file. Returns number of characters written."""
    with open(filepath, "w") as f:
        return f.write(data)


def read_lines(filepath: str) -> List[str]:
    """Read file and return list of lines."""
    with open(filepath, "r") as f:
        return f.readlines()


def write_lines(filepath: str, lines: List[str]) -> int:
    """Write list of lines to file."""
    with open(filepath, "w") as f:
        return f.writelines(lines)


def read_stdin() -> str:
    """Read from stdin."""
    return sys.stdin.read()


def print_stdout(data: str) -> None:
    """Print to stdout."""
    print(data, end="")


def print_err(data: str) -> None:
    """Print to stderr."""
    print(data, file=sys.stderr, end="")


# Module-level stream objects
class _LumenStream:
    """Stream-like object for stdout/stderr."""
    def __init__(self, stream):
        self._stream = stream

    def write(self, data: str) -> int:
        return self._stream.write(data)

    def flush(self):
        return self._stream.flush()

    def writeline(self, data: str = ""):
        return self.write(data + "\n")


stdout = _LumenStream(sys.stdout)
stderr = _LumenStream(sys.stderr)
