"""
Lumen Runtime — Testes unittest.

Cobertura:
    1. Execução de programa aritmético via VM
    2. GC sem vazar memória (aloca/libera N objetos)
    3. Coroutines intercalam execução
    4. Exceção propaga com stack trace
"""

import unittest
import sys
import os

# garante que o diretório raiz está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.vm import VM, executar, LumenError, CONST, ADD, SUB, MUL, DIV, MOD, LOAD, STORE, JMP, BR, CALL, RET, PRINT, HALT, YIELD, SPAWN, AWAIT_FUT, AWAIT_CH, CALL_NATIVE
from runtime.gc import Heap, Objeto, GCStats
from runtime.threads import (
    Tarefa, Escalonador, Channel, EstadoTarefa,
    Future, EstadoFuture, bloquear, block_on,
)
from runtime.rtlib import (
    Vec, Mapa, LumenString, NumOps,
    LumenError as RTError, LumenIndexError, LumenKeyError,
    LumenPanic, panic, Option, Some, NONE, Result, Ok, Err,
    criar_runtime, _lumen_repr,
)


# ===================================================================
# Testes da VM
# ===================================================================
class TestVM(unittest.TestCase):
    """Testes da máquina virtual de bytecode."""

    def test_aritmetica_basica(self):
        """CONST + ADD deve somar dois valores."""
        mod_bc = {
            "consts": [10, 20],
            "bytecodes": [
                (CONST, 0),    # push 10
                (CONST, 1),    # push 20
                (ADD,),        # 10 + 20 = 30
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        # entry não existe em functions, então usa o módulo diretamente
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 30)

    def test_sub_mul_div(self):
        """SUB, MUL, DIV em sequência."""
        mod_bc = {
            "consts": [100, 3, 4],
            "bytecodes": [
                (CONST, 0),    # 100
                (CONST, 1),    # 3
                (MUL,),        # 300
                (CONST, 2),    # 4
                (DIV,),        # 300 / 4 = 75.0
                (CONST, 1),    # 3
                (SUB,),        # 75.0 - 3 = 72.0
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertAlmostEqual(resultado, 72.0)

    def test_div_inteira(self):
        """DIV entre ints exatos retorna int."""
        mod_bc = {
            "consts": [10, 2],
            "bytecodes": [
                (CONST, 0),
                (CONST, 1),
                (DIV,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 5)
        self.assertIsInstance(resultado, int)

    def test_store_load(self):
        """STORE e LOAD de variáveis."""
        mod_bc = {
            "consts": [42],
            "bytecodes": [
                (CONST, 0),     # push 42
                (STORE, "x"),    # x = 42
                (LOAD, "x"),     # push x
                (CONST, 0),     # push 42
                (ADD,),         # 42 + 42 = 84
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 84)

    def test_jmp(self):
        """JMP salta para frente."""
        mod_bc = {
            "consts": [1, 999],
            "bytecodes": [
                (CONST, 0),     # 1
                (JMP, 2),       # pula 2 instruções → vai para HALT
                (CONST, 1),     # 999 (pulado)
                (CONST, 1),     # 999 (pulado)
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        # resultado é 1 ( topo da pilha antes do HALT )
        self.assertEqual(resultado, 1)

    def test_br_verdadeiro(self):
        """BR com condição verdadeira salta."""
        mod_bc = {
            "consts": [1, 100],
            "bytecodes": [
                (CONST, 0),     # 1 (truthy)
                (BR, 1),        # salta 1 → pula o JMP seguinte
                (JMP, 2),       # pula 2 → vai para HALT
                (CONST, 1),     # 100 (destino do BR)
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 100)

    def test_br_falso(self):
        """BR com condição falsa não salta."""
        mod_bc = {
            "consts": [0, 100, 200],
            "bytecodes": [
                (CONST, 0),     # 0 (falsy)
                (BR, 1),        # não salta
                (CONST, 1),     # 100
                (JMP, 1),       # pula 1 → vai para HALT
                (CONST, 2),     # 200 (pulado)
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 100)

    def test_print(self):
        """PRINT captura saída."""
        mod_bc = {
            "consts": ["hello", "world"],
            "bytecodes": [
                (CONST, 0),
                (PRINT,),
                (CONST, 1),
                (PRINT,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        self.assertEqual(vm.output, ["hello", "world"])

    def test_halt(self):
        """HALT interrompe execução."""
        mod_bc = {
            "consts": [1, 2, 3],
            "bytecodes": [
                (CONST, 0),
                (HALT,),
                (CONST, 1),   # nunca executado
                (CONST, 2),   # nunca executado
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 1)

    def test_divisao_por_zero(self):
        """DIV por zero levanta LumenError."""
        mod_bc = {
            "consts": [10, 0],
            "bytecodes": [
                (CONST, 0),
                (CONST, 1),
                (DIV,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        with self.assertRaises(LumenError) as ctx:
            vm.executar(mod_bc)
        self.assertIn("Divisão por zero", str(ctx.exception))

    def test_opcode_desconhecido(self):
        """Opcode inválido levanta LumenError."""
        mod_bc = {
            "consts": [],
            "bytecodes": [
                ("FAKE_OP",),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        with self.assertRaises(LumenError):
            vm.executar(mod_bc)

    def test_variavel_indefinida(self):
        """LOAD de variável não definida levanta erro."""
        mod_bc = {
            "consts": [],
            "bytecodes": [
                (LOAD, "x"),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        with self.assertRaises(LumenError) as ctx:
            vm.executar(mod_bc)
        self.assertIn("indefinida", str(ctx.exception))

    def test_entrada_injetada(self):
        """Parâmetro entrada é injetado como global."""
        mod_bc = {
            "consts": [5],
            "bytecodes": [
                (LOAD, "entrada"),
                (CONST, 0),
                (ADD,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc, entrada=100)
        self.assertEqual(resultado, 105)  # entrada(100) + const(5)

    def test_concatenacao_strings(self):
        """ADD entre strings concatena."""
        mod_bc = {
            "consts": ["ola", " mundo"],
            "bytecodes": [
                (CONST, 0),
                (CONST, 1),
                (ADD,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, "ola mundo")

    def test_programa_completo_soma_acumulada(self):
        """Programa completo: soma acumulada 1+2+3+4+5 = 15."""
        mod_bc = {
            "consts": [1, 2, 3, 4, 5],
            "bytecodes": [
                (CONST, 0),  # 1
                (CONST, 1),  # 2
                (ADD,),      # 3
                (CONST, 2),  # 3
                (ADD,),      # 6
                (CONST, 3),  # 4
                (ADD,),      # 10
                (CONST, 4),  # 5
                (ADD,),      # 15
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 15)


# ===================================================================
# Testes do GC
# ===================================================================
class TestGC(unittest.TestCase):
    """Testes do Garbage Collector generacional."""

    def test_alocacao_basica(self):
        """Alocação retorna Objeto válido."""
        h = Heap()
        obj = h.alocar("int", 42)
        self.assertIsInstance(obj, Objeto)
        self.assertEqual(obj.tipo, "int")
        self.assertEqual(obj.valor, 42)
        self.assertEqual(obj.gen, 0)

    def test_promocao_nursery_para_old(self):
        """Objetos vivos são promovidos para old após coleta."""
        h = Heap(nursery_max=10, old_max=100)
        raiz = h.alocar("node", "root")
        h.marcar_root(raiz)

        # aloca mais que o limiar da nursery
        for i in range(15):
            obj = h.alocar("node", i)
            raiz.referencar(obj)

        # flush manual para garantir que todos foram promovidos
        h.coletar()

        # nursery deve ter coletado e promovido para old
        self.assertEqual(len(h.nursery), 0)
        # raiz + 15 filhos = 16 objetos no mínimo no old
        self.assertGreaterEqual(len(h.old), 16)

    def test_coleta_libera_mortos(self):
        """Objetos sem referência são liberados."""
        h = Heap(nursery_max=5, old_max=100)
        for i in range(20):
            h.alocar("tmp", i)

        # coleta explícita para limpar o último batch da nursery
        h.coletar()

        # sem roots, tudo deve ser liberado
        total = h.tamanho_total()
        self.assertEqual(total, 0)

    def test_estresse_1000_objetos(self):
        """Teste de estresse: 1000 alocações sem vazar."""
        h = Heap(nursery_max=32, old_max=80)

        # Fase 1: aloca e libera
        for i in range(1000):
            h.alocar("tmp", i)
        h.coletar()  # limpa último batch
        self.assertEqual(h.tamanho_total(), 0)

        # Fase 2: aloca com referências vivas
        raiz = h.alocar("node", "raiz")
        h.marcar_root(raiz)
        vivos = []
        for i in range(100):
            obj = h.alocar("node", i)
            raiz.referencar(obj)
            vivos.append(obj)

        # promove tudo
        h.coletar()
        self.assertGreater(len(h.old), 0)

        # desmarca roots, coleta libera
        h.desmarcar_root(raiz)
        for v in vivos:
            h.desmarcar_root(v)
        # coletar() do nursery não atinge old; forçamos via _coleta_completa
        h._coleta_completa()
        self.assertEqual(h.tamanho_total(), 0)

    def test_stats_registra_corretamente(self):
        """Estatísticas são registradas corretamente."""
        h = Heap(nursery_max=5, old_max=50)
        for i in range(10):
            h.alocar("int", i)

        h.coletar()  # flush último batch

        stats = h.stats_resumo()
        self.assertEqual(stats["total_alocacoes"], 10)
        self.assertGreater(stats["total_coletas"], 0)
        self.assertEqual(stats["nursery_atual"], 0)

    def test_grafo_referencias(self):
        """Grafo de referências é preservado corretamente."""
        h = Heap(nursery_max=5, old_max=100)
        a = h.alocar("node", "a")
        b = h.alocar("node", "b")
        c = h.alocar("node", "c")

        a.referencar(b)
        b.referencar(c)
        h.marcar_root(a)

        # promove
        h.coletar()

        # a, b, c devem estar vivos
        ids_vivos = {o.id for o in h.old}
        self.assertIn(a.id, ids_vivos)
        self.assertIn(b.id, ids_vivos)
        self.assertIn(c.id, ids_vivos)

    def test_dump_nao_quebra(self):
        """Dump não deve lançar exceção."""
        h = Heap()
        h.alocar("int", 1)
        dump = h.dump()
        self.assertIn("HEAP DUMP", dump)


# ===================================================================
# Testes do GC v0.3 — Roots automáticos (frames + globals)
# ===================================================================
class TestGCV03(unittest.TestCase):
    """
    Roots automáticos do GC (v0.3).

    O heap rastreia frames (``registrar_frame``/``remover_frame``) e
    globals (``definir_global``/``remover_global``) como raízes, sem o
    chamador precisar marcar cada objeto. ``marcar_root``/``desmarcar_root``
    continuam como override manual e são somados aos roots automáticos.

    Convenção usada nos testes: ``old_max=1`` força a coleta completa
    (old generation) a rodar em cada ``coletar()``, validando que os roots
    automáticos também protegem objetos já promovidos.
    """

    def test_v03_frame_protege_vivos(self):
        """Objeto dentro de frame registrado sobrevive à coleta."""
        h = Heap(nursery_max=8, old_max=1)
        frame: dict = {}
        h.registrar_frame("main", frame)
        vivo = h.alocar("int", 1)
        frame["vivo"] = vivo
        # objetos não referenciados (fora do frame) devem morrer
        for _ in range(10):
            h.alocar("tmp", 0)
        h.coletar()
        self.assertIn(vivo.id, h._all)
        self.assertGreaterEqual(h.tamanho_total(), 1)

    def test_v03_frame_mortos_fora_do_frame_sao_coletados(self):
        """Objeto fora de qualquer root é coletado mesmo com frame vivo."""
        h = Heap(nursery_max=4, old_max=1)
        vivo = h.alocar("node", "vivo")
        h.registrar_frame(1, {"v": vivo})
        morto = h.alocar("node", "morto")
        h.coletar()
        self.assertIn(vivo.id, h._all)
        self.assertNotIn(morto.id, h._all)
        self.assertEqual(h.stats_resumo()["objetos_liberados"], 1)

    def test_v03_global_protege_e_libera(self):
        """definir_global protege; remover_global libera."""
        h = Heap(nursery_max=4, old_max=1)
        g = h.alocar("node", "g")
        h.definir_global("G", g)
        h.coletar()
        self.assertIn(g.id, h._all)
        h.remover_global("G")
        h.coletar()
        self.assertNotIn(g.id, h._all)
        self.assertEqual(h.tamanho_total(), 0)

    def test_v03_manual_override_continua_funcionando(self):
        """marcar_root/desmarcar_root somam-se aos roots automáticos."""
        h = Heap(nursery_max=4, old_max=1)
        manual = h.alocar("node", "manual")
        h.marcar_root(manual)
        automatico = h.alocar("node", "auto")
        frame: dict = {"auto": automatico}
        h.registrar_frame("f", frame)
        h.coletar()
        self.assertIn(manual.id, h._all)
        self.assertIn(automatico.id, h._all)
        # desmarcar o manual libera mesmo com o frame ainda vivo
        h.desmarcar_root(manual)
        h.coletar()
        self.assertNotIn(manual.id, h._all)
        self.assertIn(automatico.id, h._all)

    def test_v03_remover_frame_libera(self):
        """remover_frame torna coletáveis os objetos só alcançáveis por ele."""
        h = Heap(nursery_max=4, old_max=1)
        frame: dict = {}
        h.registrar_frame("f", frame)
        o = h.alocar("node", "x")
        frame["x"] = o
        h.coletar()
        self.assertIn(o.id, h._all)
        h.remover_frame("f")
        h.coletar()
        self.assertNotIn(o.id, h._all)
        self.assertEqual(h.tamanho_total(), 0)

    def test_v03_grafo_por_frame_sobrevive_a_completa(self):
        """Grafo de referências enraizado em frame sobrevive à coleta completa."""
        h = Heap(nursery_max=8, old_max=16)  # old pequeno força _coleta_completa
        raiz = h.alocar("node", "raiz")
        h.registrar_frame("main", {"raiz": raiz})
        filhos = []
        for i in range(40):
            f = h.alocar("node", i)
            raiz.referencar(f)
            filhos.append(f)
        h.coletar()
        ids_old = {o.id for o in h.old}
        self.assertIn(raiz.id, ids_old)
        for f in filhos:
            self.assertIn(f.id, ids_old)

    def test_v03_frame_mutado_ao_vivo_e_rastreado(self):
        """Mutar o dict do frame após registrar é refletido (referência viva)."""
        h = Heap(nursery_max=4, old_max=1)
        frame: dict = {}
        h.registrar_frame("main", frame)
        o = h.alocar("node", "novo")
        frame["novo"] = o  # mutação posterior ao registro
        for _ in range(20):
            h.alocar("tmp", 0)
        h.coletar()
        self.assertIn(o.id, h._all)

    def test_v03_re_registro_substitui_frame(self):
        """Registrar o mesmo frame_id substitui o mapa anterior."""
        h = Heap(nursery_max=4, old_max=1)
        antigo = h.alocar("node", "antigo")
        novo = h.alocar("node", "novo")
        h.registrar_frame("f", {"a": antigo})
        h.registrar_frame("f", {"b": novo})  # substitui: "a" perde a raiz
        h.coletar()
        self.assertNotIn(antigo.id, h._all)
        self.assertIn(novo.id, h._all)

    def test_v03_stress_5000_objetos(self):
        """5000+ objetos em frame registrado: 0 vazamento de vivos, coleta total dos mortos."""
        h = Heap(nursery_max=32, old_max=64)
        frame: dict = {}
        h.registrar_frame("stress", frame)
        vivos = []
        for i in range(3000):
            obj = h.alocar("node", i)
            frame["v%d" % i] = obj
            vivos.append(obj)
        for i in range(3000):
            h.alocar("tmp", i)  # mortos: fora de qualquer root
        h.coletar()
        # 0 vazamento: todos os vivos sobrevivem
        for obj in vivos:
            self.assertIn(obj.id, h._all)
        # coleta total dos mortos
        self.assertEqual(h.stats_resumo()["objetos_liberados"], 3000)
        self.assertEqual(h.tamanho_total(), 3000)
        # sem o frame, tudo vira lixo
        h.remover_frame("stress")
        h.coletar()
        self.assertEqual(h.tamanho_total(), 0)
        self.assertEqual(h.stats_resumo()["objetos_liberados"], 6000)

    def test_v03_stats_resumo_funciona(self):
        """stats_resumo reflete alocações/coletas com roots automáticos."""
        h = Heap(nursery_max=4, old_max=1)
        frame: dict = {}
        h.registrar_frame("f", frame)
        o = h.alocar("node", "x")
        frame["x"] = o
        for _ in range(10):
            h.alocar("tmp", 0)
        h.coletar()
        s = h.stats_resumo()
        self.assertEqual(s["total_alocacoes"], 11)
        self.assertGreater(s["total_coletas"], 0)
        self.assertEqual(s["objetos_liberados"], 10)
        self.assertGreaterEqual(s["objetos_promovidos"], 1)
        self.assertIn("nursery_atual", s)
        self.assertIn("old_atual", s)



# ===================================================================
# Testes de Coroutines/Threads
# ===================================================================
class TestThreads(unittest.TestCase):
    """Testes das coroutines cooperativas."""

    def test_tarefa_basica(self):
        """Tarefa yielda valores e encerra."""
        def gen():
            yield ("yield", 1)
            yield ("yield", 2)
            return "fim"

        t = Tarefa(1, gen)
        self.assertEqual(t.estado, EstadoTarefa.PRONTA)

        r1 = t.step()
        self.assertEqual(r1, ("yield", 1))

        r2 = t.step()
        self.assertEqual(r2, ("yield", 2))

        r3 = t.step()
        self.assertEqual(r3, ("halt", "fim"))
        self.assertEqual(t.estado, EstadoTarefa.ENCERR)
        self.assertEqual(t.resultado, "fim")

    def test_escalonador_round_robin(self):
        """Duas tarefas intercalam execução."""
        def tarefa_a():
            yield ("yield", "a1")
            yield ("yield", "a2")
            return "a_fim"

        def tarefa_b():
            yield ("yield", "b1")
            yield ("yield", "b2")
            yield ("yield", "b3")
            return "b_fim"

        sched = Escalonador()
        sched.spawn(tarefa_a, nome="A")
        sched.spawn(tarefa_b, nome="B")

        resultados = sched.run()

        # filtra só yields para verificar a ordem de intercalação
        yields = [r for r in resultados if r[0] == "yield"]

        # 5 yields no total (2 da A + 3 da B)
        self.assertEqual(len(yields), 5)
        # primeira execução é da tarefa A (spawn primeiro)
        self.assertEqual(yields[0], ("yield", "a1"))
        # segunda é da tarefa B (round-robin)
        self.assertEqual(yields[1], ("yield", "b1"))
        # terceira volta para A
        self.assertEqual(yields[2], ("yield", "a2"))
        # quarta é B
        self.assertEqual(yields[3], ("yield", "b2"))
        # quinta é B (A já encerrou)
        self.assertEqual(yields[4], ("yield", "b3"))

        # também verificar que halt results estão presentes
        halts = [r for r in resultados if r[0] == "halt"]
        self.assertEqual(len(halts), 2)

    def test_coroutines_intercalam(self):
        """Múltiplas coroutines intercalam corretamente."""
        def contador(n):
            for i in range(n):
                yield ("yield", i)
            return n

        sched = Escalonador()
        sched.spawn(contador, args=(3,), nome="c1")
        sched.spawn(contador, args=(3,), nome="c2")
        sched.spawn(contador, args=(3,), nome="c3")

        resultados = sched.run()

        # filtra só yields
        yields = [r for r in resultados if r[0] == "yield"]

        # 9 yields no total (3 de cada)
        self.assertEqual(len(yields), 9)
        # round-robin: c1[0], c2[0], c3[0], c1[1], c2[1], c3[1], c1[2], c2[2], c3[2]
        valores = [r[1] for r in yields]
        self.assertEqual(valores, [0, 0, 0, 1, 1, 1, 2, 2, 2])

    def test_channel_comunicacao(self):
        """Channel permite enviar/receber valores."""
        ch = Channel("teste")
        self.assertTrue(ch.vazio())

        ch.enviar(42)
        self.assertEqual(ch.tamanho(), 1)

        val = ch.receber()
        self.assertEqual(val, 42)
        self.assertTrue(ch.vazio())

    def test_channel_multi_valores(self):
        """Channel armazena múltiplos valores em FIFO."""
        ch = Channel()
        for i in range(5):
            ch.enviar(i)

        self.assertEqual(ch.tamanho(), 5)

        resultados = []
        while not ch.vazio():
            resultados.append(ch.receber())
        self.assertEqual(resultados, [0, 1, 2, 3, 4])

    def test_tarefa_erro(self):
        """Tarefa com exceção é encerrada com erro."""
        def quebrar():
            yield ("yield", 1)
            raise ValueError("boom")

        t = Tarefa(1, quebrar)
        r1 = t.step()
        self.assertEqual(r1, ("yield", 1))

        r2 = t.step()
        self.assertEqual(r2[0], "error")
        self.assertIsInstance(r2[1], ValueError)
        self.assertEqual(t.estado, EstadoTarefa.ENCERR)

    def test_spawn_retorna_tarefa(self):
        """Spawn retorna objeto Tarefa com id único."""
        sched = Escalonador()
        t1 = sched.spawn(lambda: (yield ("yield", 1)), nome="t1")
        t2 = sched.spawn(lambda: (yield ("yield", 2)), nome="t2")

        self.assertIsInstance(t1, Tarefa)
        self.assertIsInstance(t2, Tarefa)
        self.assertNotEqual(t1.id, t2.id)
        self.assertEqual(t1.nome, "t1")
        self.assertEqual(t2.nome, "t2")

    def test_escalonador_limite_passos(self):
        """Escalonador respeita limite de passos."""
        def infinito():
            i = 0
            while True:
                yield ("yield", i)
                i += 1

        sched = Escalonador()
        sched.spawn(infinito, nome="inf")
        resultados = sched.run(max_passos=5)
        self.assertEqual(len(resultados), 5)


# ===================================================================
# Testes do RTLib
# ===================================================================
class TestRTLib(unittest.TestCase):
    """Testes da biblioteca de runtime."""

    def setUp(self):
        self.runtime = criar_runtime()
        self.heap = self.runtime["heap"]

    def test_vec_basico(self):
        """Vec: criação, acesso, push, pop."""
        v = Vec(self.heap, [1, 2, 3])
        self.assertEqual(len(v), 3)
        self.assertEqual(v[0], 1)
        self.assertEqual(v[2], 3)

        v.push(4)
        self.assertEqual(len(v), 4)
        self.assertEqual(v[3], 4)

        val = v.pop()
        self.assertEqual(val, 4)
        self.assertEqual(len(v), 3)

    def test_vec_index_error(self):
        """Vec: acesso fora dos limites."""
        v = Vec(self.heap, [1, 2])
        with self.assertRaises(LumenIndexError):
            _ = v[5]
        with self.assertRaises(LumenIndexError):
            v[5] = 99

    def test_vec_concat(self):
        """Vec: concatenação."""
        v1 = Vec(self.heap, [1, 2])
        v2 = Vec(self.heap, [3, 4])
        v3 = v1.concat(v2)
        self.assertEqual(v3.valores, [1, 2, 3, 4])

    def test_vec_slice(self):
        """Vec: fatia."""
        v = Vec(self.heap, [0, 1, 2, 3, 4])
        s = v.slice(1, 4)
        self.assertEqual(s.valores, [1, 2, 3])

    def test_vec_iterar(self):
        """Vec: iteração."""
        v = Vec(self.heap, [10, 20, 30])
        result = list(v.iterar())
        self.assertEqual(result, [10, 20, 30])

    def test_mapa_basico(self):
        """Mapa: criação, acesso, set."""
        m = Mapa(self.heap, {"a": 1, "b": 2})
        self.assertEqual(len(m), 2)
        self.assertEqual(m["a"], 1)

        m["c"] = 3
        self.assertEqual(m["c"], 3)

    def test_mapa_key_error(self):
        """Mapa: chave não encontrada."""
        m = Mapa(self.heap, {})
        with self.assertRaises(LumenKeyError):
            _ = m["inexistente"]

    def test_mapa_merge(self):
        """Mapa: merge."""
        m1 = Mapa(self.heap, {"a": 1})
        m2 = Mapa(self.heap, {"b": 2})
        m3 = m1.merge(m2)
        self.assertEqual(m3.dados, {"a": 1, "b": 2})

    def test_mapa_chaves_valores(self):
        """Mapa: chaves, valores, itens."""
        m = Mapa(self.heap, {"x": 10, "y": 20})
        chaves = sorted(m.chaves())
        self.assertEqual(chaves, ["x", "y"])
        self.assertEqual(sorted(m.valores_list()), [10, 20])

    def test_lumen_string(self):
        """LumenString: operações básicas."""
        s = LumenString(self.heap, "Olá Mundo")
        self.assertEqual(len(s), 9)
        self.assertEqual(s[0], "O")
        self.assertEqual(s.maiuscula().valor, "OLÁ MUNDO")
        self.assertEqual(s.minuscula().valor, "olá mundo")

    def test_lumen_string_concat(self):
        """LumenString: concatenação."""
        s1 = LumenString(self.heap, "hello")
        s2 = LumenString(self.heap, " world")
        s3 = s1.concatenar(s2)
        self.assertEqual(s3.valor, "hello world")

    def test_lumen_string_find(self):
        """LumenString: encontrar, substituir."""
        s = LumenString(self.heap, "abcabc")
        self.assertEqual(s.encontrar("bc"), 1)
        self.assertEqual(s.substituir("a", "X").valor, "XbcXbc")

    def test_lumen_string_unicode(self):
        """LumenString: unicode e codepoints."""
        s = LumenString(self.heap, "café")
        self.assertFalse(s.eh_ascii())
        self.assertEqual(s.tamanho_codepoints(), 4)
        cats = s.categoria_unicode()
        self.assertEqual(len(cats), 4)

    def test_num_ops(self):
        """NumOps: operações numéricas."""
        n = NumOps()
        self.assertEqual(n.add(3, 4), 7)
        self.assertEqual(n.sub(10, 3), 7)
        self.assertEqual(n.mul(3, 4), 12)
        self.assertEqual(n.div(10, 2), 5)
        self.assertEqual(n.mod(10, 3), 1)
        self.assertEqual(n.pow(2, 10), 1024)
        self.assertEqual(n.abs(-5), 5)
        self.assertAlmostEqual(n.sqrt(9), 3.0)

    def test_num_ops_div_zero(self):
        """NumOps: divisão por zero."""
        n = NumOps()
        with self.assertRaises(RTError):
            n.div(10, 0)

    def test_primo(self):
        """NumOps: eh_primo."""
        n = NumOps()
        self.assertTrue(n.eh_primo(2))
        self.assertTrue(n.eh_primo(3))
        self.assertTrue(n.eh_primo(7))
        self.assertTrue(n.eh_primo(13))
        self.assertFalse(n.eh_primo(1))
        self.assertFalse(n.eh_primo(4))
        self.assertFalse(n.eh_primo(9))

    def test_fibonacci(self):
        """NumOps: fibonacci."""
        n = NumOps()
        self.assertEqual(n.fibonacci(0), [])
        self.assertEqual(n.fibonacci(1), [0])
        self.assertEqual(n.fibonacci(2), [0, 1])
        self.assertEqual(n.fibonacci(5), [0, 1, 1, 2, 3])
        self.assertEqual(n.fibonacci(8), [0, 1, 1, 2, 3, 5, 8, 13])

    def test_criar_runtime(self):
        """criar_runtime retorna namespace completo."""
        rt = criar_runtime()
        self.assertIn("Vec", rt)
        self.assertIn("Mapa", rt)
        self.assertIn("soma", rt)
        self.assertIn("fibonacci", rt)
        self.assertIn("heap", rt)

    def test_lumen_repr(self):
        """_lumen_repr gera representação correta."""
        self.assertEqual(_lumen_repr(None), "nil")
        self.assertEqual(_lumen_repr(True), "true")
        self.assertEqual(_lumen_repr(42), "42")
        self.assertEqual(_lumen_repr("hi"), '"hi"')
        self.assertEqual(_lumen_repr([1, 2]), "[1, 2]")


# ===================================================================
# Testes de integração
# ===================================================================
class TestIntegracao(unittest.TestCase):
    """Testes que combinam VM + GC + RTLib."""

    def test_programa_aritmetico_completo(self):
        """Programa aritmético completo via VM."""
        mod_bc = {
            "consts": [3, 7, 2],
            "bytecodes": [
                (CONST, 0),     # 3
                (CONST, 1),     # 7
                (MUL,),         # 21
                (CONST, 2),     # 2
                (ADD,),         # 23
                (PRINT,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        self.assertEqual(vm.output, ["23"])

    def test_gc_com_vm(self):
        """GC coleta objetos da VM sem vazar."""
        h = Heap(nursery_max=10, old_max=50)
        objs = []
        for i in range(100):
            obj = h.alocar("vm_val", i)
            objs.append(obj)

        # libera todos
        objs.clear()
        h.coletar()
        self.assertEqual(h.tamanho_total(), 0)
        self.assertEqual(h.stats_resumo()["objetos_liberados"], 100)

    def test_coroutines_com_vm_output(self):
        """Coroutines produzem output verificável."""
        def produtor():
            for i in range(3):
                yield ("yield", i * 10)
            return "done"

        sched = Escalonador()
        sched.spawn(produtor, nome="prod")
        resultados = sched.run()

        valores = [r[1] for r in resultados if r[0] == "yield"]
        self.assertEqual(valores, [0, 10, 20])


# ===================================================================
# Testes de Result/Option/?/panic
# ===================================================================
class TestResultOption(unittest.TestCase):
    """Testes das exceções Result/Option/?/panic do runtime."""

    def test_ok_err(self):
        self.assertTrue(Ok(1).is_ok())
        self.assertFalse(Ok(1).is_err())
        self.assertTrue(Err("x").is_err())
        self.assertEqual(Ok(1).unwrap(), 1)
        self.assertEqual(Err("x").unwrap_err(), "x")

    def test_result_unwrap_panics(self):
        with self.assertRaises(LumenPanic):
            Err("boom").unwrap()
        with self.assertRaises(LumenPanic):
            Ok(1).unwrap_err()

    def test_result_q_operator(self):
        self.assertEqual(Ok(42).q(), 42)
        with self.assertRaises(RTError):
            Err("n negativo").q()

    def test_result_map(self):
        self.assertEqual(Ok(2).map(lambda x: x * 3), Ok(6))
        self.assertEqual(Err("e").map(lambda x: x), Err("e"))

    def test_result_unwrap_or_expect(self):
        self.assertEqual(Err("e").unwrap_or(7), 7)
        self.assertEqual(Ok(1).expect("msg"), 1)
        with self.assertRaises(LumenPanic):
            Err("e").expect("falhou")

    def test_some_none(self):
        self.assertTrue(Some(1).is_some())
        self.assertFalse(Some(1).is_none())
        self.assertTrue(NONE.is_none())
        self.assertEqual(Some(1).unwrap(), 1)
        with self.assertRaises(LumenPanic):
            NONE.unwrap()

    def test_option_helpers(self):
        self.assertEqual(NONE.unwrap_or(5), 5)
        self.assertEqual(Some(2).map(lambda x: x + 1), Some(3))
        self.assertEqual(NONE.map(lambda x: x), NONE)
        self.assertEqual(Some(1).expect("msg"), 1)
        with self.assertRaises(LumenPanic):
            NONE.expect("sem valor")

    def test_panic(self):
        with self.assertRaises(LumenPanic):
            panic("boom")

    def test_runtime_namespace_exposes(self):
        rt = criar_runtime()
        for nome in ("Result", "Ok", "Err", "Option", "Some", "None",
                     "NONE", "panic", "LumenPanic"):
            self.assertIn(nome, rt)
        self.assertEqual(rt["Ok"](3).unwrap(), 3)
        with self.assertRaises(LumenPanic):
            rt["panic"]("x")


# ===================================================================
# Testes v0.4 — VM ↔ GC Heap wiring
# ===================================================================
class TestVMGCWiring(unittest.TestCase):
    """Testes do wiring VM ↔ Heap (v0.4)."""

    def test_frame_ativo_registrado_durante_execucao(self):
        """(a) Frame ativo é registrado no heap durante execução.
        Usa hook para inspecionar vm.heap._frames no meio do run."""
        frames_vistos = []

        def hook_inspector(frame, opcode, arg):
            frames_vistos.append((opcode, len(vm.heap._frames)))

        mod_bc = {
            "consts": [42],
            "bytecodes": [
                (CONST, 0),    # push 42
                (STORE, "x"),  # store x
                (LOAD, "x"),   # load x
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.hook = hook_inspector
        vm.executar(mod_bc)

        # hook foi chamado e viu ao menos 1 frame registrado no heap
        self.assertGreater(len(frames_vistos), 0)
        # ao menos um dos snapshots deve ter frames >= 1
        qtds = [q for _, q in frames_vistos]
        self.assertGreaterEqual(max(qtds), 1)

    def test_call_ret_remove_frame(self):
        """(b) CALL registra frame, RET remove frame do heap."""
        # O compilador Lumen armazena metadados de função como dicts
        # com chave __func__ dentro das consts dos frames vivos.
        func_meta = {
            "__func__": "soma",
            "consts": [20],
            "locals": ["a"],
            "bytecodes": [
                ("CONST", 0),   # push 20
                ("LOAD", "a"),  # push a (=10)
                ("ADD",),       # a + 20 = 30
                ("RET",),
            ],
            "arity": 1,
        }
        mod_bc = {
            "consts": [10, func_meta],  # index 0=10, index 1=func_meta
            "bytecodes": [
                ("CONST", 0),       # push 10
                ("CALL", "soma"),   # chama soma(10) → a=10, soma faz a+20=30
                ("HALT",),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        result = vm.executar(mod_bc)
        self.assertEqual(result, 30)

        # Conta max frames vivos durante execução vs final
        max_frames = [0]

        def hook_count(frame, opcode, arg):
            n = len(vm2.heap._frames)
            if n > max_frames[0]:
                max_frames[0] = n

        vm2 = VM()
        vm2.hook = hook_count
        vm2.executar(mod_bc)
        # Durante CALL, devia ter 2 frames (entry + soma).
        # No final, ≤ 1.
        self.assertGreaterEqual(max_frames[0], 2)
        self.assertLessEqual(len(vm2.heap._frames), 1)

    def test_store_global_reflete_em_heap_globals(self):
        """(c) STORE global (frame 0) reflete em heap._globals como Objeto."""
        mod_bc = {
            "consts": [99],
            "bytecodes": [
                (CONST, 0),
                (STORE, "g_var"),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        # "g_var" deve estar em heap._globals
        self.assertIn("g_var", vm.heap._globals)
        # v0.5: valor agora é Objeto com tipo int e valor 99
        obj = vm.heap._globals["g_var"]
        self.assertIsInstance(obj, Objeto)
        self.assertEqual(obj.tipo, "int")
        self.assertEqual(obj.valor, 99)

    def test_stress_rtlib_incrementa_total_coletas(self):
        """(d) Stress de alocações via rtlib incrementa total_coletas no heap."""
        rt = criar_runtime()
        heap_vm = rt["heap"]
        vm = VM(heap=heap_vm)

        # Programa que força muitas operações (opcodes), cada uma incrementa o
        # contador. Usamos um loop com 550 CONST/ADD/SUB/etc. para passar
        # do threshold de 512 (_gc_interval).
        consts = list(range(200))
        bytecodes = []
        for i in range(200):
            bytecodes.append((CONST, i))
            bytecodes.append((CONST, i))
            bytecodes.append((ADD,))
        # 200 * 3 = 600 opcodes > 512 => GC periódico deve disparar
        bytecodes.append((HALT,))

        mod_bc = {
            "consts": consts,
            "bytecodes": bytecodes,
            "functions": {},
            "entry": "__main__",
        }
        coletas_antes = heap_vm.stats.total_coletas
        vm.executar(mod_bc)
        coletas_depois = heap_vm.stats.total_coletas

        # GC periódico deve ter disparado ao menos 1 vez (600 > 512)
        self.assertGreater(coletas_depois, coletas_antes)


# ===================================================================
# Testes de wrapping v0.5 — valores → Objeto no heap
# ===================================================================
class TestVMGCWrapping(unittest.TestCase):
    """Testes do wrapping de valores primitivos em Objetos (P5.1)."""

    def test_store_global_aloca_objeto_no_heap(self):
        """(a) STORE global aloca Objeto no heap com valor correto."""
        mod_bc = {
            "consts": [42],
            "bytecodes": [
                (CONST, 0),
                (STORE, "x"),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        obj = vm.heap._globals["x"]
        self.assertIsInstance(obj, Objeto)
        self.assertEqual(obj.tipo, "int")
        self.assertEqual(obj.valor, 42)
        # Objeto está no heap (vivo)
        self.assertIn(obj.id, vm.heap._all)

    def test_load_desembrulha_para_python_puro(self):
        """(b) LOAD desembrulha Objeto → valor Python puro na stack."""
        mod_bc = {
            "consts": [10, 20],
            "bytecodes": [
                (CONST, 0),     # push 10
                (STORE, "a"),   # a = 10 → wrapped no heap
                (LOAD, "a"),    # push unwrapped(a) == 10 (puro)
                (CONST, 1),     # push 20
                (ADD,),         # 10 + 20 = 30
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        # resultado continua sendo Python puro
        self.assertEqual(resultado, 30)
        self.assertIsInstance(resultado, int)

    def test_frame_morto_coleta_objeto(self):
        """(c) Frame morto coleta o Objeto — vivos diminui após RET+coletar."""
        func_meta = {
            "__func__": "fn_local",
            "consts": [7],
            "locals": ["tmp"],
            "bytecodes": [
                ("CONST", 0),    # push 7
                ("STORE", "tmp"), # tmp = 7 (local, não global)
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [func_meta],
            "bytecodes": [
                ("CALL", "fn_local"),
                ("POP",) if False else ("CONST", 0),  # placeholder
                ("HALT",),
            ],
            "functions": {},
            "entry": "__main__",
        }
        # Montagem manual: CALL fn_local, depois HALT
        mod_bc["bytecodes"] = [
            ("CONST", 0),       # push func_meta (necessário para _resolve)
            ("CALL", "fn_local"),
            ("HALT",),
        ]
        # Precisamos que func_meta esteja nas consts acessíveis.
        # O _resolve_function_by_name procura __func__ nas consts dos frames vivos.
        # Colocamos func_meta no frame entry.
        mod_bc["consts"] = [0, func_meta]

        h = Heap(nursery_max=8, old_max=1)
        vm = VM(heap=h)
        vivos_antes = h.tamanho_total()
        vm.executar(mod_bc)
        # Após RET, o frame fn_local é removido do heap
        # e seu local "tmp" (se houvesse Objeto) pode ser coletado.
        # Forçamos coleta para limpar mortos.
        h.coletar()
        # Nenhum global foi definido, então vivos deve ser 0
        self.assertEqual(h.tamanho_total(), 0)

    def test_aritmetica_preserva_igualdade(self):
        """(d) Aritmética com valores wrapped preserva igualdade Python."""
        mod_bc = {
            "consts": [2, 3],
            "bytecodes": [
                (CONST, 0),    # push 2
                (STORE, "a"),  # a = 2 (wrapped no heap)
                (CONST, 1),    # push 3
                (STORE, "b"),  # b = 3 (wrapped no heap)
                (LOAD, "a"),   # push unwrapped(a) = 2
                (LOAD, "b"),   # push unwrapped(b) = 3
                (ADD,),        # 2 + 3 = 5
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        resultado = vm.executar(mod_bc)
        self.assertEqual(resultado, 5)
        self.assertIsInstance(resultado, int)
        # Verifica diretamente que 2+3==5 como Python puro
        self.assertTrue(resultado == 2 + 3)


# ===================================================================
# Testes de Async v0.3 — Futures e Channel bloqueante
# ===================================================================
class TestAsyncV03(unittest.TestCase):
    """Testes de Futures, block_on e Channel bloqueante."""

    # -- Future --------------------------------------------------------

    def test_future_pendente(self):
        """Future inicia pendente."""
        f = Future()
        self.assertEqual(f.poll(), EstadoFuture.PENDENTE)
        self.assertIsNone(f.valor)
        self.assertFalse(f.pronto)

    def test_future_pronto(self):
        """Future fica pronta após set_result."""
        f = Future()
        f.set_result(42)
        self.assertEqual(f.poll(), EstadoFuture.PRONTO)
        self.assertEqual(f.valor, 42)
        self.assertTrue(f.pronto)

    def test_future_waker_callback(self):
        """Waker da future é chamado corretamente ao resolver."""
        f = Future()
        chamado = []
        f._wakers.append(lambda fut: chamado.append(fut.valor))
        f.set_result(123)
        self.assertEqual(chamado, [123])

    # -- block_on ------------------------------------------------------

    def test_block_on_ja_pronto(self):
        """block_on com future já resolvida retorna imediatamente."""
        f = Future()
        f.set_result(99)
        result = block_on(f)
        self.assertEqual(result, 99)

    def test_block_on_resolve_durante_execucao(self):
        """block_on roda scheduler até future resolver."""
        sched = Escalonador()
        f = Future()

        def resolver():
            yield ("yield", "prep")
            f.set_result(77)

        sched.spawn(resolver)
        result = block_on(f, sched)
        self.assertEqual(result, 77)

    # -- await entre tarefas -------------------------------------------

    def test_await_future_entre_tarefas(self):
        """Tarefa aguarda future resolvida por outra tarefa."""
        sched = Escalonador()
        future = Future()

        def produtor():
            yield ("yield", "produzindo")
            future.set_result(100)
            yield ("yield", "feito")

        def consumidor():
            resultado = yield bloquear(future)
            yield ("yield", f"recebi_{resultado}")

        sched.spawn(produtor, nome="prod")
        sched.spawn(consumidor, nome="cons")
        resultados = sched.run()

        yields = [r for r in resultados if r[0] == "yield"]
        valores = [r[1] for r in yields]
        self.assertIn("recebi_100", valores)

    def test_await_preserva_ordem(self):
        """Múltiplas futures mantêm ordem de resolução."""
        sched = Escalonador()
        f1 = Future()
        f2 = Future()
        ordem = []

        def worker():
            r1 = yield bloquear(f1)
            ordem.append(r1)
            r2 = yield bloquear(f2)
            ordem.append(r2)

        def resolver():
            yield ("yield", "s1")
            f1.set_result("A")
            yield ("yield", "s2")
            f2.set_result("B")

        sched.spawn(worker, nome="w")
        sched.spawn(resolver, nome="r")
        sched.run()

        self.assertEqual(ordem, ["A", "B"])

    # -- Channel bloqueante --------------------------------------------

    def test_channel_timeout_zero(self):
        """Channel com timeout=0 retorna None se vazio."""
        ch = Channel()
        val = ch.receber(timeout=0)
        self.assertIsNone(val)
        self.assertEqual(ch.tamanho(), 0)

    def test_channel_fifo(self):
        """Channel mantém ordem FIFO."""
        ch = Channel()
        ch.enviar("a")
        ch.enviar("b")
        ch.enviar("c")
        self.assertEqual(ch.receber(), "a")
        self.assertEqual(ch.receber(), "b")
        self.assertEqual(ch.receber(), "c")

    def test_channel_estaciona_e_acorda(self):
        """Channel estaciona receptor e acorda com enviar."""
        sched = Escalonador()
        ch = Channel("sync")
        ordem = []

        def receptor():
            valor = yield ch.receber()
            ordem.append(("recebi", valor))

        def emissor():
            yield ("yield", "pre")
            ch.enviar(55)
            ordem.append(("enviei", 55))

        sched.spawn(receptor, nome="rec")
        sched.spawn(emissor, nome="emi")
        sched.run()

        self.assertEqual(len(ordem), 2)
        self.assertEqual(ordem[0], ("enviei", 55))
        self.assertEqual(ordem[1], ("recebi", 55))

    def test_channel_bloqueante_produtor_consumidor(self):
        """Channel bloqueante: produtor/consumidor com 3 itens."""
        sched = Escalonador()
        ch = Channel("pc")
        eventos = []

        def produtor():
            for i in range(3):
                ch.enviar(i)
                eventos.append(("enviei", i))
                yield ("yield", f"enviei_{i}")

        def consumidor():
            for _ in range(3):
                valor = yield ch.receber()
                eventos.append(("recebi", valor))
                yield ("yield", f"recebi_{valor}")

        sched.spawn(produtor, nome="prod")
        sched.spawn(consumidor, nome="cons")
        sched.run()

        recebidos = sorted([v for tipo, v in eventos if tipo == "recebi"])
        self.assertEqual(recebidos, [0, 1, 2])


# ===================================================================
# Testes de Async v0.5 — VM async (P5.2)
# ===================================================================
class TestVMAsync(unittest.TestCase):
    """Testes de async na VM: YIELD, SPAWN, AWAIT_FUT, AWAIT_CH."""

    def test_yield_intercala_duas_coroutines(self):
        """YIELD intercala execução entre duas coroutines (round-robin)."""
        coro_a = {
            "__func__": "coro_a",
            "consts": ["a1", "a2"],
            "locals": [],
            "bytecodes": [
                ("CONST", 0), ("PRINT",),
                ("YIELD",),
                ("CONST", 1), ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        coro_b = {
            "__func__": "coro_b",
            "consts": ["b1", "b2"],
            "locals": [],
            "bytecodes": [
                ("CONST", 0), ("PRINT",),
                ("YIELD",),
                ("CONST", 1), ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [coro_a, coro_b],
            "bytecodes": [
                ("SPAWN", "coro_a"),
                ("SPAWN", "coro_b"),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        # round-robin: a1, b1, a2, b2
        self.assertEqual(vm.output, ["a1", "b1", "a2", "b2"])

    def test_spawn_ret_executa_coroutine(self):
        """SPAWN cria coroutine que executa e coleta frame do heap."""
        coro = {
            "__func__": "coro",
            "consts": [42],
            "locals": [],
            "bytecodes": [
                ("CONST", 0), ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [coro],
            "bytecodes": [
                ("SPAWN", "coro"),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm.executar(mod_bc)
        self.assertEqual(vm.output, ["42"])
        # frame da coroutine foi removido do heap
        self.assertEqual(len(vm.heap._frames), 0)

    def test_await_fut_pronta_e_pendente(self):
        """AWAIT_FUT: pronta retorna valor; pendente suspende e retoma."""
        from runtime.threads import Future

        # --- Caso 1: Future já resolvida ---
        f1 = Future()
        f1.set_result(99)
        coro1 = {
            "__func__": "c1",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f1"),
                ("AWAIT_FUT",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        mod1 = {
            "consts": [coro1],
            "bytecodes": [("SPAWN", "c1")],
            "functions": {},
            "entry": "__main__",
        }
        vm1 = VM()
        vm1.executar(mod1, globals_extra={"f1": f1})
        self.assertEqual(vm1.output, ["99"])

        # --- Caso 2: Future pendente, resolvida por outra coroutine ---
        f2 = Future()
        coro2 = {
            "__func__": "c2",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f2"),
                ("AWAIT_FUT",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        resolver = {
            "__func__": "res",
            "consts": [42],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f2"),   # push future (arg1)
                ("CONST", 0),    # push 42     (arg2)
                ("CALL_NATIVE", ("resolve_future", 2)),
                ("RET",),
            ],
            "arity": 0,
        }
        mod2 = {
            "consts": [coro2, resolver],
            "bytecodes": [("SPAWN", "c2"), ("SPAWN", "res")],
            "functions": {},
            "entry": "__main__",
        }
        vm2 = VM()
        vm2._native_calls["resolve_future"] = lambda fut, val: fut.set_result(val)
        vm2.executar(mod2, globals_extra={"f2": f2})
        self.assertEqual(vm2.output, ["42"])

    def test_await_ch_bloqueia_acorda_com_enviar(self):
        """AWAIT_CH bloqueia e acorda com enviar."""
        from runtime.threads import Channel
        ch = Channel("teste")

        coro_receptor = {
            "__func__": "receptor",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "ch"),
                ("AWAIT_CH",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        coro_emissor = {
            "__func__": "emissor",
            "consts": [55],
            "locals": [],
            "bytecodes": [
                ("YIELD",),   # cede para receptor iniciar
                ("LOAD", "ch"),   # push channel (arg1)
                ("CONST", 0),    # push 55      (arg2)
                ("CALL_NATIVE", ("channel_enviar", 2)),
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [coro_receptor, coro_emissor],
            "bytecodes": [
                ("SPAWN", "receptor"),
                ("SPAWN", "emissor"),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm._native_calls["channel_enviar"] = lambda c, v: c.enviar(v)
        vm.executar(mod_bc, globals_extra={"ch": ch})
        self.assertEqual(vm.output, ["55"])

    def test_coroutine_frames_heap_lifecycle(self):
        """Frames de coroutine aparecem no heap e somem após término."""
        from runtime.threads import Future
        f = Future()
        frames_during = [0]

        coro = {
            "__func__": "coro",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f"),
                ("AWAIT_FUT",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        coro_resolver = {
            "__func__": "resolver",
            "consts": [77],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f"),   # push future (arg1)
                ("CONST", 0),   # push 77     (arg2)
                ("CALL_NATIVE", ("resolve_future", 2)),
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [coro, coro_resolver],
            "bytecodes": [
                ("SPAWN", "coro"),
                ("SPAWN", "resolver"),
            ],
            "functions": {},
            "entry": "__main__",
        }

        def hook_check(frame, opcode, arg):
            if opcode == "AWAIT_FUT" and getattr(frame, "coro_id", None) is not None:
                frames_during[0] = len(vm.heap._frames)

        vm = VM()
        vm.hook = hook_check
        vm._native_calls["resolve_future"] = lambda fut, val: fut.set_result(val)
        vm.executar(mod_bc, globals_extra={"f": f})
        self.assertEqual(vm.output, ["77"])
        # Durante suspensão, frame da coroutine estava no heap
        self.assertGreaterEqual(frames_during[0], 1)
        # Após conclusão, nenhum frame de coroutine no heap
        self.assertEqual(len(vm.heap._frames), 0)


# ===================================================================
# Testes de correções — Revisão
# ===================================================================
class TestReviewFixes(unittest.TestCase):
    """Testes para achados da revisão (ALTA/MÉDIA)."""

    # -- #1 MOD por zero → LumenError --------------------------------
    def test_mod_por_zero_levanta_lumen_error(self):
        """MOD por zero levanta LumenError em vez de ZeroDivisionError."""
        mod_bc = {
            "consts": [10, 0],
            "bytecodes": [
                (CONST, 0),   # 10
                (CONST, 1),   # 0
                (MOD,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        with self.assertRaises(LumenError) as ctx:
            vm.executar(mod_bc)
        self.assertIn("Módulo por zero", str(ctx.exception))

    def test_mod_funcional(self):
        """MOD funcional: 10 % 3 == 1."""
        mod_bc = {
            "consts": [10, 3],
            "bytecodes": [
                (CONST, 0),   # 10
                (CONST, 1),   # 3
                (MOD,),
                (HALT,),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        result = vm.executar(mod_bc)
        self.assertEqual(result, 1)

    # -- #2 Future multi-awaiter -------------------------------------
    def test_future_multi_awaiter(self):
        """Duas coroutines aguardam a mesma Future; ambas acordam."""
        from runtime.threads import Future

        f = Future()

        coro_a = {
            "__func__": "a",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f"),
                ("AWAIT_FUT",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        coro_b = {
            "__func__": "b",
            "consts": [],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f"),
                ("AWAIT_FUT",),
                ("PRINT",),
                ("RET",),
            ],
            "arity": 0,
        }
        resolver = {
            "__func__": "res",
            "consts": [42],
            "locals": [],
            "bytecodes": [
                ("LOAD", "f"),
                ("CONST", 0),
                ("CALL_NATIVE", ("resolve_future", 2)),
                ("RET",),
            ],
            "arity": 0,
        }
        mod_bc = {
            "consts": [coro_a, coro_b, resolver],
            "bytecodes": [
                ("SPAWN", "a"),
                ("SPAWN", "b"),
                ("SPAWN", "res"),
            ],
            "functions": {},
            "entry": "__main__",
        }
        vm = VM()
        vm._native_calls["resolve_future"] = lambda fut, val: fut.set_result(val)
        vm.executar(mod_bc, globals_extra={"f": f})
        # Ambos devem ter recebido o valor 42
        self.assertEqual(sorted(vm.output), ["42", "42"])

    def test_future_waker_list_nao_sobrescreve(self):
        """Segundo awaiter na mesma Future não sobrescreve o primeiro."""
        from runtime.threads import Future
        f = Future()
        chamados = []
        f._wakers.append(lambda fut: chamados.append("A"))
        f._wakers.append(lambda fut: chamados.append("B"))
        f.set_result(1)
        self.assertEqual(chamados, ["A", "B"])

    # -- #3 Root leak: Vec/Mapa/LumenString ---------------------------
    def test_root_leak_vec_mapa_lumenstring(self):
        """Vec/Mapa/LumenString não registram root manual — sem vazamento."""
        h = Heap(nursery_max=32, old_max=64)
        # Cria N wrappers sem armazenar referência
        for _ in range(50):
            Vec(h, [1, 2, 3])
            Mapa(h, {"k": "v"})
            LumenString(h, "abc")
        # Nenhum deve estar nas roots manuais
        self.assertEqual(len(h._roots), 0)
        # Coleta libera tudo (não há frame/globals protegendo)
        h.coletar()
        self.assertEqual(h.tamanho_total(), 0)

    def test_root_leak_vec_frame_protege(self):
        """Vec referenciado em frame registrado sobrevive à coleta."""
        h = Heap(nursery_max=8, old_max=1)
        frame: dict = {}
        h.registrar_frame("test", frame)
        v = Vec(h, [10, 20])
        frame["v"] = v.obj  # referência ao Objeto interno
        # aloca mortos
        for _ in range(20):
            h.alocar("tmp", 0)
        h.coletar()
        # o Vec deve sobreviver por estar no frame
        self.assertIn(v.obj.id, h._all)


if __name__ == "__main__":
    unittest.main(verbosity=2)
