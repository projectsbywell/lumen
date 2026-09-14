"""SQLite utilities for the Lumen standard library."""

import sqlite3
from typing import Optional, List, Tuple, Any, Union
from contextlib import contextmanager


class LumenCursor:
    """Lumen database cursor wrapper."""

    def __init__(self, cursor: sqlite3.Cursor):
        self._cursor = cursor
        self._closed = False

    def execute(self, sql: str, params: Tuple = ()) -> None:
        """Execute a single SQL statement."""
        self._cursor.execute(sql, params)

    def executemany(self, sql: str, params_list: List[Tuple]) -> None:
        """Execute SQL against all parameter tuples."""
        self._cursor.executemany(sql, params_list)

    def fetchall(self) -> List[Tuple]:
        """Fetch all rows."""
        return self._cursor.fetchall()

    def fetchone(self) -> Optional[Tuple]:
        """Fetch one row."""
        return self._cursor.fetchone()

    def fetchmany(self, size: int = 1) -> List[Tuple]:
        """Fetch many rows."""
        return self._cursor.fetchmany(size)

    def fetch_dicts(self) -> List[dict]:
        """Fetch all rows as list of dicts."""
        cols = [desc[0] for desc in self._cursor.description]
        return [dict(zip(cols, row)) for row in self._cursor.fetchall()]

    def rowcount(self) -> int:
        """Return number of affected rows."""
        return self._cursor.rowcount

    def lastrowid(self) -> Optional[int]:
        """Return last inserted row ID."""
        return self._cursor.lastrowid

    def close(self) -> None:
        """Close cursor (idempotent)."""
        if self._closed:
            return
        self._closed = True
        try:
            self._cursor.close()
        except sqlite3.ProgrammingError:
            pass


class LumenConnection:
    """Lumen database connection wrapper."""

    def __init__(self, db_path: str, timeout: int = 30):
        self._conn = sqlite3.connect(db_path, timeout=timeout)
        self._conn.row_factory = sqlite3.Row
        self._cursor = LumenCursor(self._conn.cursor())
        self._closed = False

    def cursor(self) -> LumenCursor:
        """Return cursor object."""
        return self._cursor

    def execute(self, sql: str, params: Tuple = ()) -> None:
        """Execute SQL."""
        self._cursor.execute(sql, params)

    def executemany(self, sql: str, params_list: List[Tuple]) -> None:
        """Execute many SQL."""
        self._cursor.executemany(sql, params_list)

    def fetchall(self, sql: str, params: Tuple = ()) -> List[Tuple]:
        """Execute query and fetch all."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchall()

    def fetchone(self, sql: str, params: Tuple = ()) -> Optional[Tuple]:
        """Execute query and fetch one."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchone()

    def fetchmany(self, sql: str, params: Tuple = (), size: int = 1) -> List[Tuple]:
        """Execute query and fetch many."""
        self._cursor.execute(sql, params)
        return self._cursor.fetchmany(size)

    def commit(self) -> None:
        """Commit transaction."""
        self._conn.commit()

    def rollback(self) -> None:
        """Rollback transaction."""
        self._conn.rollback()

    def close(self) -> None:
        """Close connection (idempotent, pool-safe)."""
        if self._closed:
            return
        self._closed = True
        self._cursor.close()
        try:
            self._conn.close()
        except sqlite3.ProgrammingError:
            pass

    @property
    def closed(self) -> bool:
        return self._closed

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def in_transaction(self) -> bool:
        """Check if in transaction."""
        return self._conn.in_transaction


# Module-level connection pool
_connections: dict = {}


def connect(db_path: str = ":memory:", timeout: int = 30) -> LumenConnection:
    """Create a database connection (reuses pool; replaces closed handles)."""
    key = db_path
    old = _connections.get(key)
    if old is None or old.closed:
        if old is not None:
            del _connections[key]
        _connections[key] = LumenConnection(db_path, timeout)
    return _connections[key]


def disconnect(db_path: str = ":memory:") -> None:
    """Close and remove a database connection."""
    key = db_path
    if key in _connections:
        _connections[key].close()
        del _connections[key]


def execute(db_path: str, sql: str, params: Tuple = ()) -> List[Tuple]:
    """Execute SQL (uma vez) e retorna linhas se for SELECT."""
    conn = connect(db_path)
    conn.execute(sql, params)
    conn.commit()
    if sql.strip().upper().startswith("SELECT"):
        return conn.fetchall(sql, params)
    return []


def executemany(db_path: str, sql: str, params_list: List[Tuple]) -> None:
    """Execute SQL against all parameter tuples."""
    conn = connect(db_path)
    conn.executemany(sql, params_list)
    conn.commit()
    disconnect(db_path)


def fetchall(db_path: str, sql: str, params: Tuple = ()) -> List[Tuple]:
    """Execute query and return all rows."""
    conn = connect(db_path)
    return conn.fetchall(sql, params)


def fetchone(db_path: str, sql: str, params: Tuple = ()) -> Optional[Tuple]:
    """Execute query and return one row."""
    conn = connect(db_path)
    return conn.fetchone(sql, params)


def fetchmany(db_path: str, sql: str, params: Tuple = (), size: int = 1) -> List[Tuple]:
    """Execute query and return many rows."""
    conn = connect(db_path)
    return conn.fetchmany(sql, params, size)


def commit(db_path: str) -> None:
    """Commit transaction for a connection."""
    conn = connect(db_path)
    conn.commit()
    disconnect(db_path)


def rollback(db_path: str) -> None:
    """Rollback transaction for a connection."""
    conn = connect(db_path)
    conn.rollback()
    disconnect(db_path)


@contextmanager
def transaction(db_path: str = ":memory:"):
    """Context manager for database transactions."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        disconnect(db_path)


def create_table(conn: LumenConnection, table_sql: str) -> None:
    """Create a table from SQL."""
    conn.execute(table_sql)
    conn.commit()
