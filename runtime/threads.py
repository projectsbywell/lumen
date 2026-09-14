"""
Lumen Runtime — Coroutines/Threads cooperativas.

Tarefa: unidade de execução cooperativa.
Escalonador: round-robin, spawn/step/run.
Channel: canal simples para comunicação entre tarefas.
Future: promessa de valor futuro com poll() e waker.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional
from collections import deque


# ---------------------------------------------------------------------------
# Estado da tarefa
# ---------------------------------------------------------------------------
class EstadoTarefa(enum.Enum):
    PRONTA   = "pronta"
    RODANDO  = "rodando"
    BLOQ     = "bloqueada"
    ENCERR  = "encerrada"


# ---------------------------------------------------------------------------
# Estado da future
# ---------------------------------------------------------------------------
class EstadoFuture(enum.Enum):
    """Estados possíveis de uma Future."""
    PENDENTE = "pendente"
    PRONTO   = "pronto"


# ---------------------------------------------------------------------------
# Future
# ---------------------------------------------------------------------------
class Future:
    """
    Promessa de valor futuro.

    poll() retorna EstadoFuture.PENDENTE ou EstadoFuture.PRONTO.
    set_result(valor) resolve a future e acorda quem aguarda via waker.
    """

    def __init__(self):
        self._estado: EstadoFuture = EstadoFuture.PENDENTE
        self._valor: Any = None
        self._waker: Optional[Callable[['Future'], None]] = None

    def poll(self) -> EstadoFuture:
        """Verifica o estado da future."""
        return self._estado

    @property
    def valor(self) -> Any:
        """Retorna o valor resolvido (None se ainda pendente)."""
        return self._valor

    @property
    def pronto(self) -> bool:
        """True se a future já foi resolvida."""
        return self._estado == EstadoFuture.PRONTO

    def set_result(self, valor: Any) -> None:
        """Resolve a future com um valor e acorda quem aguarda."""
        self._valor = valor
        self._estado = EstadoFuture.PRONTO
        if self._waker:
            self._waker(self)

    def __repr__(self) -> str:
        return f"Future(estado={self._estado.value}, valor={self._valor})"


# ---------------------------------------------------------------------------
# Funções auxiliares de await
# ---------------------------------------------------------------------------
def bloquear(future: Future):
    """
    Dentro de um generator (tarefa), yield este retorno para aguardar uma Future.

    Uso::

        resultado = yield bloquear(minha_future)
    """
    return ("await_future", future)


def block_on(future: Future, scheduler: 'Escalonador' = None) -> Any:
    """
    Roda o escalonador até a future ficar pronta.

    Se *scheduler* não fornecido, cria um novo.
    Retorna o valor resolvido da future.
    """
    if scheduler is None:
        scheduler = Escalonador()

    while future.poll() == EstadoFuture.PENDENTE:
        if not scheduler._fila:
            raise RuntimeError(
                "Deadlock: escalonador sem tarefas e future ainda pendente"
            )
        scheduler.step()

    return future.valor


# ---------------------------------------------------------------------------
# Tarefa
# ---------------------------------------------------------------------------
class Tarefa:
    """
    Tarefa cooperativa (coroutine).

    Uma tarefa é um gerador Python que yielda valores de controle::

        ("yield", valor)           → yield normal (cede execução)
        ("await_future", future)   → aguarda uma future
        ("await_channel", ch, t)   → aguarda dado do canal (t=None bloqueante)
        ("recv_immediate", ch)     → recepção não-bloqueante
        ("halt",)                  → encerra
    """

    def __init__(self, id_: int, gen: Callable[..., Any], args: tuple = ()):
        self.id: int = id_
        self.nome: str = f"tarefa_{id_}"
        self.estado: EstadoTarefa = EstadoTarefa.PRONTA
        self._gen_fn = gen
        self._args = args
        self._coro: Any = None
        self.resultado: Any = None
        self.erro: Optional[Exception] = None
        self._valor_retorno: Any = None  # valor a enviar na próxima step (re-awaken)
        self._init_coro()

    def _init_coro(self) -> None:
        """Inicializa o gerador."""
        try:
            self._coro = self._gen_fn(*self._args)
        except TypeError:
            self._coro = self._gen_fn()

    def step(self, valor: Any = None) -> Any:
        """
        Executa um passo da coroutine.

        Parameters
        ----------
        valor : Any, opcional
            Valor a enviar via .send(). Se None, usa _valor_retorno
            (definido pelo scheduler ao re-acordar tarefa estacionada).

        Returns
        -------
        tuple
            (tipo, payload) com o yield atual.
        """
        if self.estado == EstadoTarefa.ENCERR:
            return ("halt", None)

        self.estado = EstadoTarefa.RODANDO

        # Prioriza valor explícito; caso contrário usa _valor_retorno
        val_envio = valor if valor is not None else self._valor_retorno
        self._valor_retorno = None

        try:
            if val_envio is not None:
                resultado = self._coro.send(val_envio)
            else:
                resultado = next(self._coro)
            self.estado = EstadoTarefa.PRONTA
            return resultado
        except StopIteration as e:
            self.estado = EstadoTarefa.ENCERR
            self.resultado = e.value
            return ("halt", e.value)
        except Exception as e:
            self.estado = EstadoTarefa.ENCERR
            self.erro = e
            return ("error", e)

    def __repr__(self) -> str:
        return f"Tarefa(id={self.id}, nome='{self.nome}', estado={self.estado.value})"


# ---------------------------------------------------------------------------
# Channel — canal simples
# ---------------------------------------------------------------------------
class Channel:
    """
    Canal de comunicação entre tarefas.

    - ``enviar(valor)``: acorda receptor estacionado, se houver; caso
      contrário, adiciona ao buffer.
    - ``receber()`` / ``receber(timeout=None)``: se o buffer tem dados,
      retorna imediatamente; caso contrário retorna um yield-tuple que
      o Escalonador interpreta para estacionar a tarefa.
    - ``receber(timeout=0)``: não-bloqueante, retorna ``None`` se vazio
      (comportamento original).
    """

    def __init__(self, nome: str = ""):
        self.nome: str = nome
        self._buffer: Deque[Any] = deque()
        self._recebedores: Deque[Callable[[Any], None]] = deque()

    def enviar(self, valor: Any) -> None:
        """Envia um valor para o canal.  Acorda receptor estacionado, se houver."""
        if self._recebedores:
            callback = self._recebedores.popleft()
            callback(valor)
        else:
            self._buffer.append(valor)

    def receber(self, timeout: Any = None) -> Any:
        """
        Recebe um valor do canal.

        - Se o buffer tem dados → retorna imediatamente (FIFO).
        - ``timeout=0`` → retorna ``None`` se vazio (não-bloqueante).
        - ``timeout=None`` → retorna yield-tuple para o scheduler bloquear
          a tarefa até que ``enviar`` chegue.
        """
        if self._buffer:
            return self._buffer.popleft()
        if timeout == 0:
            return None
        return ("await_channel", self, timeout)

    def tamanho(self) -> int:
        """Quantidade de itens no buffer."""
        return len(self._buffer)

    def vazio(self) -> bool:
        return len(self._buffer) == 0

    def __repr__(self) -> str:
        return f"Channel('{self.nome}', tamanho={self.tamanho()})"


# ---------------------------------------------------------------------------
# Escalonador round-robin
# ---------------------------------------------------------------------------
class Escalonador:
    """
    Escalonador cooperativo round-robin.

    Gerencia tarefas, distribui execução em ciclos.
    Suporta aguardo de futures e canais bloqueantes.
    """

    def __init__(self):
        self._fila: Deque[Tarefa] = deque()
        self._tarefas: Dict[int, Tarefa] = {}
        self._proximo_id: int = 1
        self._passos: int = 0
        self._historico: List[str] = []

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def spawn(self, fn: Callable, args: tuple = (), nome: str = "") -> Tarefa:
        """
        Cria e registra uma nova tarefa.

        Parameters
        ----------
        fn : callable
            Função geradora (deve ser um generator function).
        args : tuple
            Argumentos para a função.
        nome : str
            Nome da tarefa (opcional).

        Returns
        -------
        Tarefa
            Tarefa criada.
        """
        t = Tarefa(self._proximo_id, fn, args)
        if nome:
            t.nome = nome
        self._proximo_id += 1
        self._tarefas[t.id] = t
        self._fila.append(t)
        self._historico.append(f"spawn({t.nome})")
        return t

    def step(self) -> Optional[Any]:
        """
        Executa um passo da tarefa no topo da fila (round-robin).

        Interpreta ``await_future`` e ``await_channel`` para gerenciar
        bloqueio e desbloqueio de tarefas.

        Returns
        -------
        tuple or None
            ``(tipo, payload)`` do yield, ou ``None`` se fila vazia.
        """
        if not self._fila:
            return None

        tarefa = self._fila.popleft()
        if tarefa.estado == EstadoTarefa.ENCERR:
            return None

        self._passos += 1
        resultado = tarefa.step()

        # ------------------------------------------------------------------
        # Interpretação de yields de controle async
        # ------------------------------------------------------------------
        if isinstance(resultado, tuple) and len(resultado) >= 1:
            tipo = resultado[0]

            if tipo == "await_future" and len(resultado) >= 2:
                future = resultado[1]
                if future.poll() == EstadoFuture.PRONTO:
                    # Future já pronta → envia valor e re-enfileira
                    tarefa._valor_retorno = future.valor
                    self._fila.append(tarefa)
                else:
                    # Future pendente → estaciona a tarefa
                    tarefa.estado = EstadoTarefa.BLOQ
                    future._waker = self._criar_waker(tarefa)

            elif tipo == "await_channel" and len(resultado) >= 2:
                ch = resultado[1]
                timeout = resultado[2] if len(resultado) > 2 else None
                if ch.tamanho() > 0:
                    # Canal tem dados → envia e re-enfileira
                    tarefa._valor_retorno = ch._buffer.popleft()
                    self._fila.append(tarefa)
                elif timeout == 0:
                    # Não-bloqueante → retorna None
                    tarefa._valor_retorno = None
                    self._fila.append(tarefa)
                else:
                    # Bloqueante → estaciona a tarefa
                    tarefa.estado = EstadoTarefa.BLOQ
                    ch._recebedores.append(self._criar_callback_receptor(tarefa))

            elif tipo == "recv_immediate" and len(resultado) >= 2:
                ch = resultado[1]
                tarefa._valor_retorno = (
                    ch._buffer.popleft() if ch.tamanho() > 0 else None
                )
                self._fila.append(tarefa)

            else:
                # Yield normal (yield, halt, error, etc.) → re-enfileira se vivo
                if tarefa.estado != EstadoTarefa.ENCERR:
                    self._fila.append(tarefa)

        else:
            # Valor bruto (ex: receber() retornou dado imediato) →
            # envia de volta ao generator no próximo passo
            tarefa._valor_retorno = resultado
            if tarefa.estado != EstadoTarefa.ENCERR:
                self._fila.append(tarefa)

        self._historico.append(f"step({tarefa.nome})={resultado}")
        return resultado

    def run(self, max_passos: int = 10000) -> List[Any]:
        """
        Executa todas as tarefas até a fila esvaziar ou max_passos.

        Parameters
        ----------
        max_passos : int
            Limite máximo de passos.

        Returns
        -------
        list
            Lista de resultados de cada passo.
        """
        resultados: List[Any] = []
        for _ in range(max_passos):
            if not self._fila:
                break
            r = self.step()
            if r is not None:
                resultados.append(r)
        return resultados

    def tarefas_vivas(self) -> List[Tarefa]:
        """Retorna tarefas que não encerraram."""
        return [t for t in self._tarefas.values()
                if t.estado != EstadoTarefa.ENCERR]

    def passos(self) -> int:
        return self._passos

    def historico(self) -> List[str]:
        return list(self._historico)

    def __repr__(self) -> str:
        vivas = len(self.tarefas_vivas())
        return f"Escalonador(tarefas={len(self._tarefas)}, vivas={vivas}, passos={self._passos})"

    # ------------------------------------------------------------------
    # Internos — callbacks para estacionar / acordar
    # ------------------------------------------------------------------
    def _criar_waker(self, tarefa: Tarefa) -> Callable[[Future], None]:
        """Cria callback para acordar tarefa quando future resolver."""
        def waker(future: Future) -> None:
            tarefa._valor_retorno = future.valor
            self._fila.append(tarefa)
        return waker

    def _criar_callback_receptor(self, tarefa: Tarefa) -> Callable[[Any], None]:
        """Cria callback para acordar tarefa quando dado chegar no canal."""
        def callback(valor: Any) -> None:
            tarefa._valor_retorno = valor
            self._fila.append(tarefa)
        return callback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def criar_tarefa_simples(nome: str, valores: List[Any]):
    """
    Cria uma tarefa simples que yielda uma lista de valores.

    Usage::

        t = criar_tarefa_simples("counter", [1, 2, 3])
        sched = Escalonador()
        sched.spawn(lambda: t)
    """
    def _gen():
        for v in valores:
            yield ("yield", v)
        return None
    return _gen


# ---------------------------------------------------------------------------
# Teste rápido
# ---------------------------------------------------------------------------
def _teste_rapido():
    """Teste básico das coroutines."""
    print("=== Teste rápido threads ===")

    def produtor():
        for i in range(5):
            yield ("yield", f"item_{i}")
        return "produtor_fim"

    def consumidor():
        for i in range(3):
            yield ("yield", f"consumindo_{i}")
        return "consumidor_fim"

    sched = Escalonador()
    t1 = sched.spawn(produtor, nome="produtor")
    t2 = sched.spawn(consumidor, nome="consumidor")

    print(f"  Escalonador: {sched}")
    resultados = sched.run()
    print(f"  Resultados: {resultados}")
    print(f"  Tarefas: {[str(t) for t in sched._tarefas.values()]}")
    print(f"  Histórico ({len(sched.historico())} entradas)")
    print("=== OK ===\n")


if __name__ == "__main__":
    _teste_rapido()
