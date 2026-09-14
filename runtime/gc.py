"""
Lumen Runtime — Garbage Collector generacional simplificado.

Geração jovem (nursery) + geração velha (old).
Mark-and-compact via simulação de grafo de objetos.

Estratégia:
    1. Objetos alocados vão para a nursery.
    2. Quando a nursery atinge o limiar, dispara coleta.
    3. Objetos vivos da nursery são promovidos para old.
    4. Coletas completas (old) happen raramente (limiar maior).
    5. Mark-and-compact: marca vivos a partir de roots, compacta.

Roots automáticos (v0.3):
    - Frames registrados via ``registrar_frame``/``remover_frame``.
    - Globals definidos via ``definir_global``/``remover_global``.
    - ``marcar_root``/``desmarcar_root`` continuam existindo como override
      manual e são somados aos roots automáticos na coleta.
"""

from __future__ import annotations

import sys
import weakref
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Objeto
# ---------------------------------------------------------------------------
class Objeto:
    """Representa um objeto alocado no heap Lumen."""

    __slots__ = ("tipo", "valor", "attrs", "mark", "gen", "id", "_refs")

    def __init__(self, tipo: str, valor: Any = None, gen: int = 0):
        self.tipo: str = tipo
        self.valor: Any = valor
        self.attrs: Dict[str, Any] = {}
        self.mark: bool = False
        self.gen: int = gen          # 0 = nursery, 1 = old
        self.id: int = 0             # atribuído pelo Heap
        self._refs: List["Objeto"] = []

    def __repr__(self) -> str:
        v = repr(self.valor) if self.valor is not None else "{}"
        return f"Objeto({self.tipo}, gen={self.gen}, id={self.id}, {v})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Objeto):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def referencar(self, outro: "Objeto") -> None:
        """Adiciona referência a outro objeto (para o grafo de reachability)."""
        if outro not in self._refs:
            self._refs.append(outro)

    def refs(self) -> List["Objeto"]:
        """Retorna referências diretas."""
        return list(self._refs)


# ---------------------------------------------------------------------------
# Heap
# ---------------------------------------------------------------------------
NURSERY_MAX = 64        # Limiar para promoção
OLD_MAX     = 512       # Limiar para coleta completa


@dataclass
class GCStats:
    """Estatísticas do GC."""
    total_alocacoes: int = 0
    total_coletas: int = 0
    nursery_coletas: int = 0
    old_coletas: int = 0
    objetos_promovidos: int = 0
    objetos_liberados: int = 0
    nursery_atual: int = 0
    old_atual: int = 0


class Heap:
    """
    Heap generacional Lumen.

    Gerencia dois espaços: nursery (jovem) e old (velho).
    Coleta mark-and-compact com promoção.
    """

    def __init__(self, nursery_max: int = NURSERY_MAX, old_max: int = OLD_MAX):
        self.nursery: List[Objeto] = []
        self.old: List[Objeto] = []
        self._all: Dict[int, Objeto] = {}
        self._next_id: int = 1
        self._nursery_max = nursery_max
        self._old_max = old_max
        self.stats = GCStats()
        # Roots externas (variáveis globais, frame locals, etc.)
        self._roots: Set[int] = set()
        # Roots automáticos: frames rastreados (id -> mapa nome->Objeto) e globals.
        self._frames: Dict[Any, Dict[Any, Optional[Objeto]]] = {}
        self._globals: Dict[Any, Optional[Objeto]] = {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def alocar(self, tipo: str, valor: Any = None) -> Objeto:
        """
        Aloca um novo objeto no heap.

        Parameters
        ----------
        tipo : str
            Tipo do objeto (ex: "int", "str", "vec", "mapa").
        valor : any
            Valor inicial.

        Returns
        -------
        Objeto
            Objeto alocado.
        """
        # coleta antes de alocar se nursery cheia
        if len(self.nursery) >= self._nursery_max:
            self.coletar()

        obj = Objeto(tipo, valor, gen=0)
        obj.id = self._next_id
        self._next_id += 1
        self.nursery.append(obj)
        self._all[obj.id] = obj
        self.stats.total_alocacoes += 1
        self.stats.nursery_atual = len(self.nursery)
        return obj

    def marcar_root(self, obj: Objeto) -> None:
        """Registra um objeto como root para o GC (override manual)."""
        self._roots.add(obj.id)

    def desmarcar_root(self, obj: Objeto) -> None:
        """Remove um objeto das roots manuais."""
        self._roots.discard(obj.id)

    def registrar_frame(self, frame_id: Any, mapa: Dict[Any, Optional[Objeto]]) -> None:
        """
        Registra um frame como root automático.

        ``mapa`` mapeia nome -> Objeto (ex.: as locals de um frame da VM).
        O heap mantém a referência ao próprio dict: mutações posteriores
        (novos STOREs, overwrites) são refletidas sem re-registrar.

        ``frame_id`` deve ser único entre frames vivos (ex.: ``id(frame)``
        ou um contador da VM). Registrar um id já existente substitui o mapa.
        """
        self._frames[frame_id] = mapa

    def remover_frame(self, frame_id: Any) -> None:
        """
        Remove um frame das roots automáticas.

        Chamado quando o frame morre (RET/HALT): os objetos que só eram
        alcançáveis por ele tornam-se coletáveis.
        """
        self._frames.pop(frame_id, None)

    def definir_global(self, nome: Any, obj: Optional[Objeto]) -> None:
        """Define uma global como root automático (nome -> Objeto)."""
        self._globals[nome] = obj

    def remover_global(self, nome: Any) -> None:
        """Remove uma global das roots automáticas."""
        self._globals.pop(nome, None)

    def coletar(self) -> GCStats:
        """
        Executa coleta de lixo.

        Returns
        -------
        GCStats
            Estatísticas atualizadas.
        """
        self.stats.total_coletas += 1

        # Fase 1: Mark — marca todos a partir de roots
        vivos: Set[int] = set()
        self._mark(vivos)

        # Fase 2: Sweep nursery — remove mortos, promove vivos
        nursery_vivos: List[Objeto] = []
        for obj in self.nursery:
            if obj.id in vivos:
                # promove para old generation
                obj.gen = 1
                self.old.append(obj)
                nursery_vivos.append(obj)
                self.stats.objetos_promovidos += 1
            else:
                self._all.pop(obj.id, None)
                self.stats.objetos_liberados += 1

        liberados_nursery = len(self.nursery) - len(nursery_vivos)
        self.nursery.clear()
        self.stats.nursery_atual = 0

        # Fase 3: Se old também está grande, coleta completa
        if len(self.old) >= self._old_max:
            self._coleta_completa(vivos)

        self.stats.nursery_coletas += 1
        self.stats.old_atual = len(self.old)
        return self.stats

    def stats_resumo(self) -> dict:
        """Retorna resumo das estatísticas como dict."""
        return {
            "total_alocacoes": self.stats.total_alocacoes,
            "total_coletas": self.stats.total_coletas,
            "nursery_coletas": self.stats.nursery_coletas,
            "old_coletas": self.stats.old_coletas,
            "objetos_promovidos": self.stats.objetos_promovidos,
            "objetos_liberados": self.stats.objetos_liberados,
            "nursery_atual": len(self.nursery),
            "old_atual": len(self.old),
        }

    def tamanho_total(self) -> int:
        """Retorna número total de objetos vivos."""
        return len(self.nursery) + len(self.old)

    # ------------------------------------------------------------------
    # Mark & Compact (interno)
    # ------------------------------------------------------------------
    def _sementes(self) -> List[int]:
        """
        Coleta todos os ids de raízes: manuais + frames + globals.

        Objetos ``None`` e ids já liberados são ignorados.
        """
        sementes: Set[int] = set(self._roots)
        for mapa in self._frames.values():
            for obj in mapa.values():
                if obj is not None:
                    sementes.add(obj.id)
        for obj in self._globals.values():
            if obj is not None:
                sementes.add(obj.id)
        return list(sementes)

    def _mark(self, vivos: Set[int]) -> None:
        """Mark phase: DFS a partir de roots (manuais + frames + globals)."""
        stack: List[int] = self._sementes()

        while stack:
            oid = stack.pop()
            if oid in vivos:
                continue
            obj = self._all.get(oid)
            if obj is None:
                continue
            vivos.add(oid)
            for ref in obj._refs:
                if ref.id not in vivos:
                    stack.append(ref.id)

    def _coleta_completa(self, vivos_nursery: Set[int]) -> None:
        """Coleta completa do old generation (mark-and-compact)."""
        # re-mmarca incluindo roots
        todos_vivos: Set[int] = set()
        self._mark(todos_vivos)

        old_vivos: List[Objeto] = []
        for obj in self.old:
            if obj.id in todos_vivos:
                old_vivos.append(obj)
            else:
                self._all.pop(obj.id, None)
                self.stats.objetos_liberados += 1

        liberados_old = len(self.old) - len(old_vivos)
        self.old = old_vivos
        self.stats.old_coletas += 1
        self.stats.old_atual = len(self.old)

    # ------------------------------------------------------------------
    # Depuração
    # ------------------------------------------------------------------
    def dump(self) -> str:
        """Dump do estado do heap para depuração."""
        lines = [f"=== HEAP DUMP ==="]
        lines.append(f"Nursery ({len(self.nursery)}):")
        for o in self.nursery:
            refs = [r.id for r in o._refs]
            lines.append(f"  [{o.id}] {o.tipo} = {o.valor!r}  refs={refs}")
        lines.append(f"Old ({len(self.old)}):")
        for o in self.old:
            refs = [r.id for r in o._refs]
            lines.append(f"  [{o.id}] {o.tipo} = {o.valor!r}  refs={refs}")
        lines.append(f"Stats: {self.stats_resumo()}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers de wrapping (P5.1)
# ---------------------------------------------------------------------------

def envolver(heap: "Heap", tipo: str, valor: Any) -> Objeto:
    """
    Aloca um Objeto no *heap* para um valor primitivo.

    Conveniência sobre ``heap.alocar`` que mantém a API existente.
    """
    return heap.alocar(tipo, valor)


def desembrulhar(obj: Any) -> Any:
    """
    Desembrulha um valor que pode ser ``Objeto`` ou Python puro.

    - Se *obj* é ``Objeto`` com tipo primitivo (``int``, ``float``,
      ``bool``, ``str``, ``none``), retorna ``obj.valor``.
    - Se *obj* já é valor Python puro, retorna o próprio.
    - Qualquer falha retorna o valor original (defensivo).
    """
    try:
        if isinstance(obj, Objeto) and obj.tipo in (
            "int", "float", "bool", "str", "none",
        ):
            return obj.valor
    except Exception:
        pass
    return obj


# ---------------------------------------------------------------------------
# Teste de estresse (executa direto)
# ---------------------------------------------------------------------------
def _teste_estresse():
    """Teste de estresse do GC: aloca e libera muitos objetos."""
    print("=== Teste de estresse GC ===")
    h = Heap(nursery_max=32, old_max=128)

    # Fase 1: aloca muitos objetos sem referências (devem ser coletados)
    print("Fase 1: Alocação sem referências...")
    for i in range(200):
        obj = h.alocar("int", i)
    h.coletar()  # flush último batch
    print(f"  Após 200 alocações: nursery={len(h.nursery)}, old={len(h.old)}")
    print(f"  Stats: {h.stats_resumo()}")

    # Fase 2: cria grafo de referências (vivos devem sobreviver)
    print("Fase 2: Grafo de referências...")
    raiz = h.alocar("node", "raiz")
    h.marcar_root(raiz)
    filhos = []
    for i in range(50):
        filho = h.alocar("node", f"filho_{i}")
        raiz.referencar(filho)
        filhos.append(filho)

    # mantém referência a filhos impares
    vivos = [f for i, f in enumerate(filhos) if i % 2 == 0]
    for v in vivos:
        h.marcar_root(v)

    # coleta deve manter raiz + filhos pares (referenciados)
    h.coletar()
    print(f"  Após coleta com grafo: nursery={len(h.nursery)}, old={len(h.old)}")
    print(f"  Stats: {h.stats_resumo()}")

    # Fase 3: stress test
    print("Fase 3: Stress test (1000 ciclos)...")
    for ciclo in range(1000):
        obj = h.alocar("tmp", ciclo)
        if ciclo % 3 == 0:
            h.marcar_root(obj)
        if ciclo % 5 == 0 and h.nursery:
            h.desmarcar_root(h.nursery[-1])

    print(f"  Após 1000 ciclos: nursery={len(h.nursery)}, old={len(h.old)}")
    print(f"  Stats: {h.stats_resumo()}")
    print(f"  Total vivo: {h.tamanho_total()}")
    print("=== OK ===\n")


if __name__ == "__main__":
    _teste_estresse()
