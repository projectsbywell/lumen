"""Testing utilities for the Lumen standard library."""

import time
import tracemalloc
import sys
import inspect
from typing import Any, Callable, List, Optional, Tuple, Type
from collections import defaultdict


class AssertError(Exception):
    """Raised when an assertion fails."""
    pass


class TestCase:
    """Base test case class."""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._tests = []
        self._results = []
        self.passed = 0
        self.failed = 0
        self.errors = 0

    def setup(self) -> None:
        """Setup method called before each test."""
        pass

    def teardown(self) -> None:
        """Teardown method called after each test."""
        pass

    def assert_eq(self, a: Any, b: Any, msg: str = "") -> bool:
        """Assert equality."""
        if a != b:
            raise AssertError(msg or f"Expected {a!r} == {b!r}")
        return True

    def assert_ne(self, a: Any, b: Any, msg: str = "") -> bool:
        """Assert inequality."""
        if a == b:
            raise AssertError(msg or f"Expected {a!r} != {b!r}")
        return True

    def assert_true(self, condition: bool, msg: str = "") -> bool:
        """Assert condition is true."""
        if not condition:
            raise AssertError(msg or f"Expected True, got {condition}")
        return True

    def assert_false(self, condition: bool, msg: str = "") -> bool:
        """Assert condition is false."""
        if condition:
            raise AssertError(msg or f"Expected False, got {condition}")
        return True

    def assert_none(self, value: Any, msg: str = "") -> bool:
        """Assert value is None."""
        if value is not None:
            raise AssertError(msg or f"Expected None, got {value!r}")
        return True

    def assert_not_none(self, value: Any, msg: str = "") -> bool:
        """Assert value is not None."""
        if value is None:
            raise AssertError(msg or f"Expected not None")
        return True

    def assert_in(self, member: Any, container: Any, msg: str = "") -> bool:
        """Assert member is in container."""
        if member not in container:
            raise AssertError(msg or f"{member!r} not in {container!r}")
        return True

    def assert_not_in(self, member: Any, container: Any, msg: str = "") -> bool:
        """Assert member is not in container."""
        if member in container:
            raise AssertError(msg or f"{member!r} in {container!r}")
        return True

    def assert_is_instance(self, obj: Any, cls: Type, msg: str = "") -> bool:
        """Assert object is instance of class."""
        if not isinstance(obj, cls):
            raise AssertError(msg or f"Expected {obj!r} to be instance of {cls.__name__}")
        return True

    def assert_is_none(self, value: Any, msg: str = "") -> bool:
        """Assert value is None."""
        if value is not None:
            raise AssertError(msg or f"Expected None, got {value!r}")
        return True

    def assert_is_not_none(self, value: Any, msg: str = "") -> bool:
        """Assert value is not None."""
        if value is None:
            raise AssertError(msg or f"Expected not None")
        return True

    def assert_raises(self, exc_type: Type[Exception], func: Callable, *args, **kwargs) -> bool:
        """Assert that func raises exc_type."""
        try:
            func(*args, **kwargs)
            raise AssertError(f"Expected {exc_type.__name__} to be raised")
        except exc_type:
            return True
        except Exception as e:
            raise AssertError(f"Expected {exc_type.__name__}, got {type(e).__name__}: {e}")

    def assert_almost_eq(self, a: float, b: float, places: int = 6, msg: str = "") -> bool:
        """Assert floats are approximately equal (compara arredondados)."""
        if round(a, places) != round(b, places):
            raise AssertError(msg or f"Expected {a!r} ≈ {b!r}")
        return True

    def assert_greater(self, a: float, b: float, msg: str = "") -> bool:
        """Assert a > b."""
        if not a > b:
            raise AssertError(msg or f"Expected {a!r} > {b!r}")
        return True

    def assert_less(self, a: float, b: float, msg: str = "") -> bool:
        """Assert a < b."""
        if not a < b:
            raise AssertError(msg or f"Expected {a!r} < {b!r}")
        return True

    def run(self) -> dict:
        """Run all test methods."""
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self._results = []

        methods = sorted(
            [m for m in dir(self) if m.startswith("test_") and callable(getattr(self, m))],
            key=str.lower
        )

        for method_name in methods:
            method = getattr(self, method_name)
            self.setup()
            try:
                method()
                self.passed += 1
                self._results.append({"name": method_name, "status": "PASS"})
            except AssertError as e:
                self.failed += 1
                self._results.append({"name": method_name, "status": "FAIL", "error": str(e)})
            except Exception as e:
                self.errors += 1
                self._results.append({"name": method_name, "status": "ERROR", "error": str(e)})
            finally:
                self.teardown()

        return self.summary()

    def summary(self) -> dict:
        """Return test summary."""
        total = self.passed + self.failed + self.errors
        return {
            "name": self.name,
            "total": total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "success": self.failed == 0 and self.errors == 0,
            "results": self._results,
        }


def assert_eq(a: Any, b: Any, msg: str = "") -> bool:
    """Module-level assert_eq."""
    return TestCase().assert_eq(a, b, msg)


def assert_ne(a: Any, b: Any, msg: str = "") -> bool:
    """Module-level assert_ne."""
    return TestCase().assert_ne(a, b, msg)


def assert_true(condition: bool, msg: str = "") -> bool:
    """Module-level assert_true."""
    return TestCase().assert_true(condition, msg)


def assert_false(condition: bool, msg: str = "") -> bool:
    """Module-level assert_false."""
    return TestCase().assert_false(condition, msg)


def assert_none(value: Any, msg: str = "") -> bool:
    """Module-level assert_none."""
    return TestCase().assert_none(value, msg)


def assert_not_none(value: Any, msg: str = "") -> bool:
    """Module-level assert_not_none (alias of assert_is_not_none)."""
    return TestCase().assert_not_none(value, msg)


def assert_almost_eq(a: float, b: float, places: int = 6, msg: str = "") -> bool:
    """Module-level assert_almost_eq."""
    return TestCase().assert_almost_eq(a, b, places, msg)


def assert_greater(a: float, b: float, msg: str = "") -> bool:
    """Module-level assert_greater."""
    return TestCase().assert_greater(a, b, msg)


def assert_less(a: float, b: float, msg: str = "") -> bool:
    """Module-level assert_less."""
    return TestCase().assert_less(a, b, msg)


def assert_raises(exc_type: Type[Exception], func: Callable, *args, **kwargs) -> bool:
    """Module-level assert_raises."""
    return TestCase().assert_raises(exc_type, func, *args, **kwargs)


def assert_in(member: Any, container: Any, msg: str = "") -> bool:
    """Module-level assert_in."""
    return TestCase().assert_in(member, container, msg)


def assert_not_in(member: Any, container: Any, msg: str = "") -> bool:
    """Module-level assert_not_in."""
    return TestCase().assert_not_in(member, container, msg)


def assert_is_instance(obj: Any, cls: Type, msg: str = "") -> bool:
    """Module-level assert_is_instance."""
    return TestCase().assert_is_instance(obj, cls, msg)


def assert_is_none(value: Any, msg: str = "") -> bool:
    """Module-level assert_is_none."""
    return TestCase().assert_is_none(value, msg)


def assert_is_not_none(value: Any, msg: str = "") -> bool:
    """Module-level assert_is_not_none."""
    return TestCase().assert_is_not_none(value, msg)


def measure_time(func: Callable, *args, **kwargs) -> Tuple[Any, float]:
    """Measure execution time of a function."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


def measure_memory(func: Callable, *args, **kwargs) -> Tuple[Any, int]:
    """Measure peak memory usage of a function."""
    tracemalloc.start()
    result = func(*args, **kwargs)
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak


class TestSuite:
    """Collection of test cases."""

    def __init__(self, name: str = "Suite"):
        self.name = name
        self._cases: List[TestCase] = []

    def add(self, test_case: TestCase) -> None:
        """Add a test case."""
        self._cases.append(test_case)

    def add_module(self, module) -> None:
        """Add all TestCase subclasses from a module."""
        for name in dir(module):
            obj = getattr(module, name)
            if inspect.isclass(obj) and issubclass(obj, TestCase) and obj is not TestCase:
                self.add(obj())

    def run(self) -> dict:
        """Run all test cases."""
        total_passed = 0
        total_failed = 0
        total_errors = 0
        all_results = []

        for case in self._cases:
            summary = case.run()
            total_passed += summary["passed"]
            total_failed += summary["failed"]
            total_errors += summary["errors"]
            all_results.append(summary)

        total = total_passed + total_failed + total_errors
        return {
            "name": self.name,
            "total": total,
            "passed": total_passed,
            "failed": total_failed,
            "errors": total_errors,
            "success": total_failed == 0 and total_errors == 0,
            "cases": all_results,
        }


class TestResult:
    """Container for test results."""

    def __init__(self):
        self.results: List[dict] = []
        self.start_time: float = 0
        self.end_time: float = 0

    @property
    def elapsed(self) -> float:
        return self.end_time - self.start_time


# ---------------------------------------------------------------------------
# Mocks e stubs (v0.2)
# ---------------------------------------------------------------------------
class Mock:
    """Mock mínimo: registra chamadas e devolve retornos programados."""

    def __init__(self, **retornos):
        self._retornos = dict(retornos)
        self.chamadas: list = []

    def quando(self, metodo: str, retorno=None, efeito=None) -> "Mock":
        """Programa retorno/efeito de um método."""
        self._retornos[metodo] = (retorno, efeito)
        return self

    def __getattr__(self, nome: str):
        if nome.startswith("_"):
            raise AttributeError(nome)

        def _chamada(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            prog = self._retornos.get(nome)
            if prog is None:
                return None
            ret, efeito = prog if isinstance(prog, tuple) else (prog, None)
            if efeito is not None:
                return efeito(*args, **kwargs)
            return ret() if callable(ret) and not isinstance(ret, type) else ret

        return _chamada

    def foi_chamado(self, metodo: str | None = None) -> bool:
        """True se houve ao menos uma chamada (opcionalmente do método)."""
        if metodo is None:
            return bool(self.chamadas)
        return any(c[0] == metodo for c in self.chamadas)

    def vezes_chamado(self, metodo: str) -> int:
        """Quantas vezes o método foi chamado."""
        return sum(1 for c in self.chamadas if c[0] == metodo)

    def reset(self) -> None:
        """Limpa o histórico de chamadas."""
        self.chamadas.clear()


def mock(**retornos) -> Mock:
    """Cria um Mock com retornos programados."""
    return Mock(**retornos)


def stub(obj: Any, nome: str, func: Callable) -> Callable:
    """Substitui obj.nome por func; devolve restaurador."""
    original = getattr(obj, nome)
    setattr(obj, nome, func)

    def restaurar() -> None:
        setattr(obj, nome, original)

    return restaurar
