"""Math and linear algebra utilities for the Lumen standard library."""

import math
from typing import List, Tuple, Union

Number = Union[int, float]
Matrix = List[List[Number]]
Vector = List[Number]


# --- Basic arithmetic ---

def ladd(a: Number, b: Number) -> Number:
    """Add two numbers."""
    return a + b


def lsub(a: Number, b: Number) -> Number:
    """Subtract b from a."""
    return a - b


def lmul(a: Number, b: Number) -> Number:
    """Multiply two numbers."""
    return a * b


def ldiv(a: Number, b: Number) -> float:
    """Divide a by b."""
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def lmod(a: Number, b: Number) -> Number:
    """Modulo operation."""
    if b == 0:
        raise ZeroDivisionError("modulo by zero")
    return a % b


def lpow(a: Number, b: Number) -> Number:
    """Raise a to power b."""
    return a ** b


# --- Linear algebra ---

def lmat_add(a: Matrix, b: Matrix) -> Matrix:
    """Add two matrices."""
    if len(a) != len(b) or len(a[0]) != len(b[0]):
        raise ValueError("matrix dimensions must match")
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


def lmat_mul(a: Matrix, b: Matrix) -> Matrix:
    """Multiply two matrices."""
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])
    if cols_a != rows_b:
        raise ValueError(f"cannot multiply {rows_a}x{cols_a} by {rows_b}x{cols_b}")
    result = [[sum(a[i][k] * b[k][j] for k in range(cols_a)) for j in range(cols_b)] for i in range(rows_a)]
    return result


def lmat_transpose(m: Matrix) -> Matrix:
    """Transpose a matrix."""
    if not m:
        return []
    return [[m[i][j] for i in range(len(m))] for j in range(len(m[0]))]


def lmat_scalar_mul(m: Matrix, scalar: Number) -> Matrix:
    """Multiply matrix by scalar."""
    return [[cell * scalar for cell in row] for row in m]


def lvec_dot(a: Vector, b: Vector) -> Number:
    """Dot product of two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have same length")
    return sum(x * y for x, y in zip(a, b))


def lvec_norm(v: Vector) -> float:
    """Euclidean norm of vector."""
    return math.sqrt(sum(x * x for x in v))


# --- Statistics ---

def lmean(data: Vector) -> float:
    """Arithmetic mean."""
    if not data:
        raise ValueError("cannot compute mean of empty data")
    return sum(data) / len(data)


def lmedian(data: Vector) -> float:
    """Median value."""
    if not data:
        raise ValueError("cannot compute median of empty data")
    s = sorted(data)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2
    return float(s[mid])


def lvar(data: Vector) -> float:
    """Population variance."""
    if not data:
        raise ValueError("cannot compute variance of empty data")
    m = lmean(data)
    return sum((x - m) ** 2 for x in data) / len(data)


def lstd(data: Vector) -> float:
    """Population standard deviation."""
    return math.sqrt(lvar(data))


def lsum(data: Vector) -> Number:
    """Sum of all elements."""
    return sum(data)


def lmin(data: Vector) -> Number:
    """Minimum value."""
    if not data:
        raise ValueError("cannot compute min of empty data")
    return min(data)


def lmax(data: Vector) -> Number:
    """Maximum value."""
    if not data:
        raise ValueError("cannot compute max of empty data")
    return max(data)


# --- Math functions ---

def lsqrt(x: Number) -> float:
    """Square root."""
    if x < 0:
        raise ValueError("cannot compute sqrt of negative number")
    return math.sqrt(x)


def lfactorial(n: int) -> int:
    """Factorial of n."""
    if n < 0:
        raise ValueError("factorial not defined for negative numbers")
    return math.factorial(n)


def lgcd(a: int, b: int) -> int:
    """Greatest common divisor."""
    return math.gcd(a, b)


def llcm(a: int, b: int) -> int:
    """Least common multiple."""
    return abs(a * b) // math.gcd(a, b) if a and b else 0


def lsin(x: Number) -> float:
    """Sine."""
    return math.sin(x)


def lcos(x: Number) -> float:
    """Cosine."""
    return math.cos(x)


def ltan(x: Number) -> float:
    """Tangent."""
    return math.tan(x)


def lasin(x: Number) -> float:
    """Arcsine."""
    return math.asin(x)


def lacos(x: Number) -> float:
    """Arccosine."""
    return math.acos(x)


def latan(x: Number) -> float:
    """Arctangent."""
    return math.atan(x)


def latan2(y: Number, x: Number) -> float:
    """Arctangent of y/x."""
    return math.atan2(y, x)


# Constants
lpi = math.pi
le = math.e
llng = math.log(2)  # ln(2)
