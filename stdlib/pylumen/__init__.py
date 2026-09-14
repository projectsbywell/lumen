"""Lumen Standard Library — Python implementation (espelho da API Lumen)."""

__version__ = "1.0.0"
__lang__ = "Lumen"

from .core import (
    LumenType, LumenString, LumenInt, LumenFloat, LumenBool, LumenNil,
    ltype_of, ltype_name, lconvert, lto_int, lto_float, lto_str, lto_bool,
    lis_nil, lis_type, lassert_type,
)
from .collections import Vec, Mapa, Set, Fila
from .strings import (
    lstrlen, lconcat, lindex, lcompare,
    lto_upper, lto_lower, lto_title,
    lstrip, ltrim, lreplace, lsplit, ljoin,
    lmatches, lfind, lcount,
    lformat, unicode_category, unicode_name, is_unicode_letter,
    regex_compile, regex_match, regex_search, regex_findall, regex_sub,
)
from .strings import lsub as _str_lsub
from .mathx import lsub as _num_lsub


def lsub(a, b, c=None):
    """Polimórfico: substring se `a` é str, subtração numérica caso contrário."""
    if isinstance(a, str):
        return _str_lsub(a, b) if c is None else _str_lsub(a, b, c)
    return _num_lsub(a, b)
from .io import read_file, write_file, read_lines, write_lines, read_stdin, print_stdout, print_err, stdout, stderr
from .mathx import (
    ladd, lmul, ldiv, lmod, lpow,
    lsub as lsub_num,
    lmat_add, lmat_mul, lmat_transpose, lmat_scalar_mul,
    lvec_dot, lvec_norm,
    lmean, lmedian, lstd, lvar, lsum, lmin, lmax,
    lsqrt, lfactorial, lgcd, llcm,
    lsin, lcos, ltan, lasin, lacos, latan, latan2,
    lpi, le, llng,
)
from .timex import (
    now, now_utc, from_timestamp, to_timestamp,
    format_date, parse_date,
    timedelta, date_add, date_diff,
    sleep,
    ldate, ltime, ldatetime,
    year, month, day, weekday, days_in_month, is_leap_year,
)
from .cryptox import (
    sha256, sha256_file, hmac_sha256, xor_cipher, xor_decrypt,
    generate_key, generate_nonce, xor_demo,
    lhash, lverify_hmac,
)
from .jsonx import (
    ldumps, lloads,
    lto_json, lfrom_json, lto_json_file, lfrom_json_file,
    lpretty, lis_json, lmerge, ldeep_merge,
)
from .yamlx import (
    lloads as yloads, ldumps as ydumps,
    lto_yaml, lfrom_yaml, lto_yaml_file, lfrom_yaml_file, lis_yaml,
)
from .tomlx import (
    lloads as tloads, ldumps as tdumps,
    lto_toml, lfrom_toml, lto_toml_file, lfrom_toml_file, lis_toml,
)
from .result import (
    Result, Ok, Err, Option, Some, NONE,
    LumenPanic, LumenError as StdLumenError, panic,
)
from .httpx import (
    get, post, put, delete,
    LumenResponse, HTTPClient,
)
from .sqlitex import (
    connect, disconnect,
    execute, fetchall, fetchone, fetchmany,
    executemany, commit, rollback,
    LumenCursor, LumenConnection,
)
from .testingx import (
    TestCase, AssertError,
    assert_eq, assert_ne, assert_true, assert_false, assert_none,
    assert_not_none, assert_almost_eq, assert_greater, assert_less,
    assert_raises, assert_in, assert_not_in,
    assert_is_instance, assert_is_none, assert_is_not_none,
    measure_time, measure_memory,
    Mock, mock, stub,
    TestSuite, TestResult,
)

__all__ = [
    "__version__", "__lang__",
    # core
    "LumenType", "LumenString", "LumenInt", "LumenFloat", "LumenBool", "LumenNil",
    "ltype_of", "ltype_name", "lconvert", "lto_int", "lto_float", "lto_str", "lto_bool",
    "lis_nil", "lis_type", "lassert_type",
    # collections
    "Vec", "Mapa", "Set", "Fila",
    # strings
    "lstrlen", "lsub", "lconcat", "lindex", "lcompare",
    "lto_upper", "lto_lower", "lto_title",
    "lstrip", "ltrim", "lreplace", "lsplit", "ljoin",
    "lmatches", "lfind", "lcount",
    "lformat", "unicode_category", "unicode_name", "is_unicode_letter",
    "regex_compile", "regex_match", "regex_search", "regex_findall", "regex_sub",
    # io
    "read_file", "write_file", "read_lines", "write_lines",
    "read_stdin", "print_stdout", "print_err", "stdout", "stderr",
    # mathx
    "ladd", "lsub_num", "lmul", "ldiv", "lmod", "lpow",
    "lmat_add", "lmat_mul", "lmat_transpose", "lmat_scalar_mul",
    "lvec_dot", "lvec_norm",
    "lmean", "lmedian", "lstd", "lvar", "lsum", "lmin", "lmax",
    "lsqrt", "lfactorial", "lgcd", "llcm",
    "lsin", "lcos", "ltan", "lasin", "lacos", "latan", "latan2",
    "lpi", "le", "llng",
    # timex
    "now", "now_utc", "from_timestamp", "to_timestamp",
    "format_date", "parse_date",
    "timedelta", "date_add", "date_diff",
    "sleep",
    "ldate", "ltime", "ldatetime",
    "year", "month", "day", "weekday", "days_in_month", "is_leap_year",
    # cryptox
    "sha256", "sha256_file", "hmac_sha256", "xor_cipher", "xor_decrypt",
    "generate_key", "generate_nonce", "xor_demo",
    "lhash", "lverify_hmac",
    # jsonx
    "ldumps", "lloads", "lto_json", "lfrom_json",
    "lto_json_file", "lfrom_json_file", "lpretty", "lis_json",
    "lmerge", "ldeep_merge",
    # yamlx
    "yloads", "ydumps",
    "lto_yaml", "lfrom_yaml", "lto_yaml_file", "lfrom_yaml_file", "lis_yaml",
    # tomlx
    "tloads", "tdumps",
    "lto_toml", "lfrom_toml", "lto_toml_file", "lfrom_toml_file", "lis_toml",
    # result (Result/Option/?/panic)
    "Result", "Ok", "Err", "Option", "Some", "NONE",
    "LumenPanic", "StdLumenError", "panic",
    # httpx
    "get", "post", "put", "delete",
    "LumenResponse", "HTTPClient",
    # sqlitex
    "connect", "disconnect",
    "execute", "fetchall", "fetchone", "fetchmany",
    "executemany", "commit", "rollback",
    "LumenCursor", "LumenConnection",
    # testingx
    "TestCase", "AssertError",
    "assert_eq", "assert_ne", "assert_true", "assert_false", "assert_none",
    "assert_not_none", "assert_almost_eq", "assert_greater", "assert_less",
    "assert_raises", "assert_in", "assert_not_in",
    "Mock", "mock", "stub",
    "assert_is_instance", "assert_is_none", "assert_is_not_none",
    "measure_time", "measure_memory",
    "TestSuite", "TestResult",
]
