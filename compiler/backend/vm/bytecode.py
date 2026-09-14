"""Bytecode Lumen (.lbc): formato, (de)serialização, verificador, linker."""
from __future__ import annotations
import struct

MAGIC = b"LBC1"
VERSION = 1
OPCODES = {"CONST":1,"ADD":2,"SUB":3,"MUL":4,"DIV":5,"LOAD":6,"STORE":7,
    "JMP":8,"BR":9,"CALL":10,"RET":11,"PRINT":12,"HALT":13,"MOD":14,"EQ":15,"LT":16,"GT":17}
R_OP = {v:k for k,v in OPCODES.items()}

class ModuloBC:
    def __init__(self, nome="main", consts=None, code=None):
        self.nome = nome; self.consts = consts or []; self.code = code or []

    def to_bytes(self) -> bytes:
        out = bytearray(MAGIC + struct.pack(">H", VERSION))
        nb = self.nome.encode("utf8")
        out += struct.pack(">H", len(nb)) + nb
        out += struct.pack(">H", len(self.consts))
        for c in self.consts:
            if isinstance(c, int): out += b"i" + struct.pack(">q", c)
            elif isinstance(c, float): out += b"f" + struct.pack(">d", c)
            else:
                b = str(c).encode("utf8"); out += b"s" + struct.pack(">H", len(b)) + b
        out += struct.pack(">H", len(self.code))
        for op, arg in self.code:
            out += struct.pack(">B", OPCODES[op]) + struct.pack(">h", arg)
        return bytes(out)

    @staticmethod
    def from_bytes(buf: bytes) -> "ModuloBC":
        assert buf[:4] == MAGIC, "magic inválido"
        ver = struct.unpack(">H", buf[4:6])[0]; assert ver == VERSION
        i = 6
        nl = struct.unpack(">H", buf[i:i+2])[0]; i += 2
        nome = buf[i:i+nl].decode("utf8"); i += nl
        nc = struct.unpack(">H", buf[i:i+2])[0]; i += 2
        consts = []
        for _ in range(nc):
            t = buf[i:i+1]; i += 1
            if t == b"i": consts.append(struct.unpack(">q", buf[i:i+8])[0]); i += 8
            elif t == b"f": consts.append(struct.unpack(">d", buf[i:i+8])[0]); i += 8
            else:
                ln = struct.unpack(">H", buf[i:i+2])[0]; i += 2
                consts.append(buf[i:i+ln].decode("utf8")); i += ln
        ni = struct.unpack(">H", buf[i:i+2])[0]; i += 2
        code = []
        for _ in range(ni):
            op = R_OP[buf[i]]; arg = struct.unpack(">h", buf[i+1:i+3])[0]; i += 3
            code.append((op, arg))
        return ModuloBC(nome, consts, code)

def verificar(m: ModuloBC) -> list[str]:
    """Verificador do `.lbc`: HALT final, consts válidos, operandos em faixa."""
    e = []
    if not m.code or m.code[-1][0] != "HALT": e.append("sem HALT final")
    for idx, (op, a) in enumerate(m.code):
        if op not in OPCODES: e.append(f"opcode desconhecido @{idx}: {op}")
        if op == "CONST" and not (0 <= a < len(m.consts)):
            e.append(f"CONST @{idx} aponta p/ const inexistente ({a})")
        if op in ("LOAD", "STORE") and not (0 <= a < 256):
            e.append(f"operando fora: {op} {a}")
        if op in ("JMP", "BR") and not (-len(m.code) <= a <= len(m.code)):
            e.append(f"salto fora de faixa @{idx}: {op} {a}")
    n_halt = sum(1 for op, _ in m.code if op == "HALT")
    if n_halt > 1: e.append(f"{n_halt} HALTs (esperado 1, no fim)")
    return e


def link(mods: list[ModuloBC]) -> ModuloBC:
    """Linker: une consts (dedup) e código. Saltos relativos são
    preservados como estão; HALTs intermediários são descartados
    (só o último fecha o módulo)."""
    consts, code = [], []
    for mi, m in enumerate(mods):
        cmap = []
        for c in m.consts:
            if c in consts: cmap.append(consts.index(c))
            else: cmap.append(len(consts)); consts.append(c)
        body = m.code
        if mi < len(mods) - 1 and body and body[-1][0] == "HALT":
            body = body[:-1]
        for op, a in body:
            code.append((op, cmap[a] if op == "CONST" else a))
    if not code or code[-1][0] != "HALT":
        code.append(("HALT", 0))
    return ModuloBC("+".join(m.nome for m in mods), consts, code)


def save(path: str, m: ModuloBC) -> None:
    with open(path, "wb") as fh: fh.write(m.to_bytes())


def load(path: str) -> ModuloBC:
    with open(path, "rb") as fh: return ModuloBC.from_bytes(fh.read())
