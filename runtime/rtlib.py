"""
Lumen Runtime — Biblioteca de runtime.

Alocação, strings unicode, coleções (Vec, Mapa), operações numéricas.
Tudo integrado ao heap generacional do GC.
"""

from __future__ import annotations

import math
import unicodedata
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .gc import Heap, Objeto


# ---------------------------------------------------------------------------
# Vec — vetor dinâmico
# ---------------------------------------------------------------------------
class Vec:
    """Vetor dinâmico Lumen, armazenado como objeto no heap."""

    def __init__(self, heap: Heap, itens: Optional[List[Any]] = None):
        self._heap = heap
        self._obj = heap.alocar("vec", itens or [])
        self._heap.marcar_root(self._obj)

    @property
    def obj(self) -> Objeto:
        return self._obj

    @property
    def valores(self) -> List[Any]:
        return list(self._obj.valor)

    def __len__(self) -> int:
        return len(self._obj.valor)

    def __getitem__(self, idx: int) -> Any:
        if idx < 0 or idx >= len(self._obj.valor):
            raise LumenIndexError(idx, len(self._obj.valor))
        return self._obj.valor[idx]

    def __setitem__(self, idx: int, valor: Any) -> None:
        if idx < 0 or idx >= len(self._obj.valor):
            raise LumenIndexError(idx, len(self._obj.valor))
        self._obj.valor[idx] = valor

    def push(self, valor: Any) -> None:
        """Insere no final."""
        self._obj.valor.append(valor)

    def pop(self) -> Any:
        """Remove e retorna o último."""
        if not self._obj.valor:
            raise LumenError("Vec vazio — pop impossível")
        return self._obj.valor.pop()

    def insert(self, idx: int, valor: Any) -> None:
        """Insere na posição idx."""
        if idx < 0 or idx > len(self._obj.valor):
            raise LumenIndexError(idx, len(self._obj.valor))
        self._obj.valor.insert(idx, valor)

    def remove(self, idx: int) -> Any:
        """Remove e retorna o item na posição idx."""
        if idx < 0 or idx >= len(self._obj.valor):
            raise LumenIndexError(idx, len(self._obj.valor))
        return self._obj.valor.pop(idx)

    def concat(self, outro: "Vec") -> "Vec":
        """Retorna novo Vec com concatenação."""
        resultado = Vec(self._heap, self.valores + outro.valores)
        return resultado

    def slice(self, start: int, end: Optional[int] = None) -> "Vec":
        """Retorna novo Vec com fatia."""
        return Vec(self._heap, self._obj.valor[start:end])

    def index_of(self, valor: Any) -> int:
        """Retorna índice do valor ou -1."""
        try:
            return self._obj.valor.index(valor)
        except ValueError:
            return -1

    def contiene(self, valor: Any) -> bool:
        """Verifica se contém o valor."""
        return valor in self._obj.valor

    def iterar(self) -> Iterator[Any]:
        """Itera sobre os valores."""
        return iter(self._obj.valor)

    def __repr__(self) -> str:
        return f"Vec({self._obj.valor})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Vec):
            return self._obj.valor == other._obj.valor
        return NotImplemented

    def __str__(self) -> str:
        return f"[{', '.join(_lumen_repr(v) for v in self._obj.valor)}]"


# ---------------------------------------------------------------------------
# Mapa — dicionário
# ---------------------------------------------------------------------------
class Mapa:
    """Mapa (dicionário) Lumen, armazenado no heap."""

    def __init__(self, heap: Heap, dados: Optional[Dict[str, Any]] = None):
        self._heap = heap
        self._obj = heap.alocar("mapa", dados or {})
        self._heap.marcar_root(self._obj)

    @property
    def obj(self) -> Objeto:
        return self._obj

    @property
    def dados(self) -> Dict[str, Any]:
        return dict(self._obj.valor)

    def __len__(self) -> int:
        return len(self._obj.valor)

    def __getitem__(self, chave: str) -> Any:
        if chave not in self._obj.valor:
            raise LumenKeyError(chave)
        return self._obj.valor[chave]

    def __setitem__(self, chave: str, valor: Any) -> None:
        self._obj.valor[chave] = valor

    def __delitem__(self, chave: str) -> None:
        if chave not in self._obj.valor:
            raise LumenKeyError(chave)
        del self._obj.valor[chave]

    def __contains__(self, chave: str) -> bool:
        return chave in self._obj.valor

    def get(self, chave: str, padrao: Any = None) -> Any:
        """Obtém valor com valor padrão."""
        return self._obj.valor.get(chave, padrao)

    def chaves(self) -> List[str]:
        return list(self._obj.valor.keys())

    def valores_list(self) -> List[Any]:
        return list(self._obj.valor.values())

    def itens(self) -> List[Tuple[str, Any]]:
        return list(self._obj.valor.items())

    def merge(self, outro: "Mapa") -> "Mapa":
        """Retorna novo Mapa com merge."""
        dados = {**self._obj.valor, **outro._obj.valor}
        return Mapa(self._heap, dados)

    def __repr__(self) -> str:
        return f"Mapa({self._obj.valor})"

    def __str__(self) -> str:
        pares = ", ".join(f"{k}: {_lumen_repr(v)}" for k, v in self._obj.valor.items())
        return f"{{{pares}}}"


# ---------------------------------------------------------------------------
# LumenString — string unicode rica
# ---------------------------------------------------------------------------
class LumenString:
    """String unicode Lumen com operações丰富idas."""

    def __init__(self, heap: Heap, valor: str = ""):
        self._heap = heap
        self._obj = heap.alocar("str", valor)
        self._heap.marcar_root(self._obj)

    @property
    def valor(self) -> str:
        return self._obj.valor

    def __len__(self) -> int:
        return len(self._obj.valor)

    def __getitem__(self, idx: int) -> str:
        if idx < 0 or idx >= len(self._obj.valor):
            raise LumenIndexError(idx, len(self._obj.valor))
        return self._obj.valor[idx]

    def concatenar(self, outro: str | "LumenString") -> "LumenString":
        if isinstance(outro, LumenString):
            outro = outro.valor
        return LumenString(self._heap, self._obj.valor + outro)

    def sub(self, start: int, end: Optional[int] = None) -> "LumenString":
        return LumenString(self._heap, self._obj.valor[start:end])

    def maiuscula(self) -> "LumenString":
        return LumenString(self._heap, self._obj.valor.upper())

    def minuscula(self) -> "LumenString":
        return LumenString(self._heap, self._obj.valor.lower())

    def strip(self) -> "LumenString":
        return LumenString(self._heap, self._obj.valor.strip())

    def contém(self, sub: str) -> bool:
        return sub in self._obj.valor

    def encontrar(self, sub: str) -> int:
        """Retorna índice da primeira ocorrência ou -1."""
        idx = self._obj.valor.find(sub)
        return idx

    def substituir(self, antigo: str, novo: str) -> "LumenString":
        return LumenString(self._heap, self._obj.valor.replace(antigo, novo))

    def dividir(self, sep: str) -> List[str]:
        return self._obj.valor.split(sep)

    def caracteres(self) -> List[str]:
        return list(self._obj.valor)

    def bytes_utf8(self) -> List[int]:
        return list(self._obj.valor.encode("utf-8"))

    def tamanho_codepoints(self) -> int:
        """Número de codepoints Unicode."""
        return len(self._obj.valor)

    def categoria_unicode(self) -> List[str]:
        """Retorna categorias Unicode de cada caractere."""
        return [unicodedata.category(c) for c in self._obj.valor]

    def eh_ascii(self) -> bool:
        return all(ord(c) < 128 for c in self._obj.valor)

    def __repr__(self) -> str:
        return f"LumenString({self._obj.valor!r})"

    def __str__(self) -> str:
        return self._obj.valor

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LumenString):
            return self._obj.valor == other._obj.valor
        if isinstance(other, str):
            return self._obj.valor == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._obj.valor)


# ---------------------------------------------------------------------------
# Operações numéricas
# ---------------------------------------------------------------------------
class NumOps:
    """Operações numéricas do runtime Lumen."""

    @staticmethod
    def add(a: Any, b: Any) -> Any:
        return a + b

    @staticmethod
    def sub(a: Any, b: Any) -> Any:
        return a - b

    @staticmethod
    def mul(a: Any, b: Any) -> Any:
        return a * b

    @staticmethod
    def div(a: Any, b: Any) -> float:
        if b == 0:
            raise LumenError("Divisão por zero")
        if isinstance(a, int) and isinstance(b, int) and a % b == 0:
            return a // b
        return a / b

    @staticmethod
    def mod(a: int, b: int) -> int:
        if b == 0:
            raise LumenError("Módulo por zero")
        return a % b

    @staticmethod
    def pow(a: Any, b: Any) -> Any:
        return a ** b

    @staticmethod
    def abs(a: Any) -> Any:
        return abs(a)

    @staticmethod
    def min_val(a: Any, b: Any) -> Any:
        return a if a < b else b

    @staticmethod
    def max_val(a: Any, b: Any) -> Any:
        return a if a > b else b

    @staticmethod
    def sqrt(a: float) -> float:
        if a < 0:
            raise LumenError("Raiz quadrada de número negativo")
        return math.sqrt(a)

    @staticmethod
    def log(a: float, base: float = math.e) -> float:
        if a <= 0:
            raise LumenError("Logaritmo de número não-positivo")
        return math.log(a, base)

    @staticmethod
    def eh_par(n: int) -> bool:
        return n % 2 == 0

    @staticmethod
    def eh_impar(n: int) -> bool:
        return n % 2 != 0

    @staticmethod
    def eh_primo(n: int) -> bool:
        if n < 2:
            return False
        if n < 4:
            return True
        if n % 2 == 0 or n % 3 == 0:
            return False
        i = 5
        while i * i <= n:
            if n % i == 0 or n % (i + 2) == 0:
                return False
            i += 6
        return True

    @staticmethod
    def fibonacci(n: int) -> List[int]:
        """Retorna sequência Fibonacci de tamanho n."""
        if n <= 0:
            return []
        if n == 1:
            return [0]
        seq = [0, 1]
        while len(seq) < n:
            seq.append(seq[-1] + seq[-2])
        return seq


# ---------------------------------------------------------------------------
# Exceções Lumen
# ---------------------------------------------------------------------------
class LumenError(Exception):
    """Exceção base do runtime Lumen."""
    pass


class LumenIndexError(LumenError):
    """Índice fora dos limites."""
    def __init__(self, idx: int, tamanho: int):
        super().__init__(f"Índice {idx} fora dos limites (tamanho={tamanho})")
        self.idx = idx
        self.tamanho = tamanho


class LumenKeyError(LumenError):
    """Chave não encontrada no Mapa."""
    def __init__(self, chave: str):
        super().__init__(f"Chave não encontrada: '{chave}'")
        self.chave = chave


class LumenPanic(LumenError):
    """Panic do runtime Lumen (erro irrecuperável, como `panic(msg)`)."""
    pass


def panic(msg: Any) -> None:
    """Levanta LumenPanic com a mensagem dada."""
    raise LumenPanic(str(msg))


class Option:
    """Option<T> — Some(valor) ou NONE (ausência)."""

    __slots__ = ("_valor", "_some")

    def __init__(self, valor: Any = None, some: bool = False):
        self._valor = valor
        self._some = some

    def is_some(self) -> bool:
        return self._some

    def is_none(self) -> bool:
        return not self._some

    def unwrap(self) -> Any:
        if not self._some:
            raise LumenPanic("unwrap em None")
        return self._valor

    def unwrap_or(self, padrao: Any) -> Any:
        return self._valor if self._some else padrao

    def expect(self, msg: str) -> Any:
        if not self._some:
            raise LumenPanic(msg)
        return self._valor

    def map(self, fn: Callable[[Any], Any]) -> "Option":
        if not self._some:
            return NONE
        return Some(fn(self._valor))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Option):
            if self._some != other._some:
                return False
            return (not self._some) or (self._valor == other._valor)
        return NotImplemented

    def __repr__(self) -> str:
        return f"Some({self._valor!r})" if self._some else "None"


class Some(Option):
    """Variante presente de Option."""
    def __init__(self, valor: Any):
        super().__init__(valor, True)


class _None(Option):
    """Variante ausente de Option (singleton NONE)."""
    _inst: Optional["_None"] = None

    def __new__(cls) -> "_None":
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __init__(self) -> None:
        super().__init__(None, False)


NONE = _None()


class Result:
    """Result<T, E> — Ok(valor) ou Err(erro). Operador `?` = método q()."""

    __slots__ = ("_valor", "_ok")

    def __init__(self, valor: Any = None, ok: bool = True):
        self._valor = valor
        self._ok = ok

    def is_ok(self) -> bool:
        return self._ok

    def is_err(self) -> bool:
        return not self._ok

    def unwrap(self) -> Any:
        if not self._ok:
            raise LumenPanic(f"unwrap em Err: {self._valor}")
        return self._valor

    def unwrap_err(self) -> Any:
        if self._ok:
            raise LumenPanic(f"unwrap_err em Ok: {self._valor}")
        return self._valor

    def unwrap_or(self, padrao: Any) -> Any:
        return self._valor if self._ok else padrao

    def expect(self, msg: str) -> Any:
        if not self._ok:
            raise LumenPanic(f"{msg}: {self._valor}")
        return self._valor

    def map(self, fn: Callable[[Any], Any]) -> "Result":
        if not self._ok:
            return self
        try:
            return Ok(fn(self._valor))
        except Exception as e:  # noqa: BLE001
            return Err(str(e))

    def q(self) -> Any:
        """Equivalente ao operador `?`: desembrulha Ok ou propaga Err."""
        if not self._ok:
            raise LumenError(f"Err não tratado: {self._valor}")
        return self._valor

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Result):
            return self._ok == other._ok and self._valor == other._valor
        return NotImplemented

    def __repr__(self) -> str:
        tag = "Ok" if self._ok else "Err"
        return f"{tag}({self._valor!r})"


class Ok(Result):
    """Variante de sucesso de Result."""
    def __init__(self, valor: Any):
        super().__init__(valor, True)


class Err(Result):
    """Variante de erro de Result."""
    def __init__(self, erro: Any):
        super().__init__(erro, False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lumen_repr(valor: Any) -> str:
    """Representação Lumen de um valor."""
    if valor is None:
        return "nil"
    if valor is True:
        return "true"
    if valor is False:
        return "false"
    if isinstance(valor, str):
        return f'"{valor}"'
    if isinstance(valor, Vec):
        return str(valor)
    if isinstance(valor, Mapa):
        return str(valor)
    if isinstance(valor, LumenString):
        return f'"{valor.valor}"'
    if isinstance(valor, list):
        return f"[{', '.join(_lumen_repr(v) for v in valor)}]"
    if isinstance(valor, dict):
        pares = ", ".join(f"{k}: {_lumen_repr(v)}" for k, v in valor.items())
        return f"{{{pares}}}"
    return str(valor)


def criar_runtime(heap: Optional[Heap] = None) -> dict:
    """
    Cria o namespace do runtime Lumen completo.

    Returns
    -------
    dict
        Dicionário com todas as funções e classes do runtime.
    """
    if heap is None:
        heap = Heap()

    num = NumOps()

    def vec(*args):
        """Cria um Vec a partir dos argumentos."""
        return Vec(heap, list(args))

    def mapa(**kwargs):
        """Cria um Mapa a partir de keyword args."""
        return Mapa(heap, kwargs)

    def str_lumen(valor: Any) -> LumenString:
        """Converte valor para LumenString."""
        return LumenString(heap, str(valor) if valor is not None else "")

    def int_lumen(valor: Any) -> int:
        """Converte para int."""
        if isinstance(valor, float):
            return int(valor)
        if isinstance(valor, str):
            return int(valor)
        if isinstance(valor, bool):
            return 1 if valor else 0
        return int(valor)

    def float_lumen(valor: Any) -> float:
        """Converte para float."""
        return float(valor)

    def len_lumen(valor: Any) -> int:
        """Retorna tamanho."""
        if isinstance(valor, (Vec, LumenString)):
            return len(valor)
        if isinstance(valor, (list, str, dict)):
            return len(valor)
        raise LumenError(f"len() não suportado para {type(valor).__name__}")

    return {
        # Coleções
        "Vec": vec,
        "Mapa": mapa,
        "Str": str_lumen,
        "Int": int_lumen,
        "Float": float_lumen,
        "len": len_lumen,

        # Num
        "soma": num.add,
        "subtrai": num.sub,
        "multiplica": num.mul,
        "dividir": num.div,
        "modulo": num.mod,
        "potencia": num.pow,
        "absoluto": num.abs,
        "minimo": num.min_val,
        "maximo": num.max_val,
        "raiz": num.sqrt,
        "logaritmo": num.log,
        "eh_par": num.eh_par,
        "eh_impar": num.eh_impar,
        "eh_primo": num.eh_primo,
        "fibonacci": num.fibonacci,

        # Heap
        "heap": heap,

        # Exceções
        "LumenError": LumenError,
        "LumenIndexError": LumenIndexError,
        "LumenKeyError": LumenKeyError,
        "LumenPanic": LumenPanic,
        "panic": panic,

        # Result / Option (exceções + operador ?)
        "Option": Option,
        "Some": Some,
        "None": NONE,
        "NONE": NONE,
        "Result": Result,
        "Ok": Ok,
        "Err": Err,
    }
